"""
Modelos: SubProducto, SubProductoIngrediente, SubProductoComponente

Representa una fase de proceso (Extrusión, Jarabe, Sazonador, etc.).
Un SubProducto puede contener:
  - Ingredientes  (materia prima pura, via SubProductoIngrediente)
  - Otros SubProductos como sub-componentes (auto-referencia, via SubProductoComponente)

Cálculos:
  - tabla_nutricional(): nutrientes por 100 g del sub-producto,
    considerando la concentración por merma de humedad.
  - costo_total(kg): costo de producir `kg` kg del sub-producto.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.ingrediente import Ingrediente

# ──────────────────────────────────────────────────────────────────────────────
# Tabla de asociación: SubProducto ↔ Ingrediente  (con porcentaje de uso)
# ──────────────────────────────────────────────────────────────────────────────

class SubProductoIngrediente(Base):
    """
    Representa qué porcentaje (en peso) de un Ingrediente forma parte
    de un SubProducto antes de la merma.

    Ejemplo: 45% de maíz en el proceso de extrusión.
    """
    __tablename__ = "subproducto_ingrediente"

    subproducto_id: Mapped[int] = mapped_column(
        ForeignKey("subproductos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ingrediente_id: Mapped[int] = mapped_column(
        ForeignKey("ingredientes.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    # Porcentaje en peso (0–100) que este ingrediente aporta a la receta
    # antes de cualquier proceso. La suma de todos los ingredientes +
    # sub-componentes de un SubProducto debería ser 100.
    porcentaje_uso: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones ORM
    subproducto: Mapped["SubProducto"] = relationship(
        back_populates="relaciones_ingredientes")
    ingrediente: Mapped["Ingrediente"] = relationship()


# ──────────────────────────────────────────────────────────────────────────────
# Tabla de asociación: SubProducto ↔ SubProducto  (composición anidada)
# ──────────────────────────────────────────────────────────────────────────────

class SubProductoComponente(Base):
    """
    Permite que un SubProducto (padre) contenga otro SubProducto (hijo)
    como componente de su receta, con un porcentaje de uso.

    Ejemplo: "Mezcla Final" contiene 30% de "Jarabe" y 70% de "Base Extruida".
    """
    __tablename__ = "subproducto_componente"

    padre_id: Mapped[int] = mapped_column(
        ForeignKey("subproductos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hijo_id: Mapped[int] = mapped_column(
        ForeignKey("subproductos.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    porcentaje_uso: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones ORM
    padre: Mapped["SubProducto"] = relationship(
        "SubProducto",
        foreign_keys=[padre_id],
        back_populates="relaciones_componentes_padre",
    )
    hijo: Mapped["SubProducto"] = relationship(
        "SubProducto",
        foreign_keys=[hijo_id],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Modelo principal: SubProducto
# ──────────────────────────────────────────────────────────────────────────────

# Campos nutricionales que se propagan (misma lista que Ingrediente)
_NUTRIENTES = [
    "energia_kcal",
    "proteinas_g",
    "grasa_total_g",
    "grasa_saturada_g",
    "grasa_monoinsaturada_g",
    "grasa_poliinsaturada_g",
    "acidos_grasos_trans_g",
    "colesterol_mg",
    "carbohidratos_disp_g",
    "azucares_totales_g",
    "sorbitol_g",
    "maltitol_g",
    "fibra_dietetica_g",
    "fibra_soluble_g",
    "fibra_insoluble_g",
    "sodio_mg",
]


class SubProducto(Base):
    """
    Fase de proceso (nodo BOM).  Puede contener Ingredientes y/o
    otros SubProductos.  Expone métodos para calcular costos y
    la tabla nutricional concentrada (post-merma).
    """
    __tablename__ = "subproductos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text, default="")

    # % de humedad que se evapora durante el proceso (0–100).
    # Ejemplo: extrusión pierde 14 % de humedad → merma_humedad_porcentaje = 14
    merma_humedad_porcentaje: Mapped[float] = mapped_column(Float, default=0.0)

    # Costo operativo adicional en pesos por kg DE PRODUCTO PRODUCIDO.
    # Incluye energía, partida/parada, tamizado, etc.
    # Si el costo es fijo por lote, dividirlo por el kg promedio del lote.
    costo_operativo_kg: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Relaciones ORM ──────────────────────────────────────────────────────
    relaciones_ingredientes: Mapped[list[SubProductoIngrediente]] = relationship(
        back_populates="subproducto",
        cascade="all, delete-orphan",
    )
    relaciones_componentes_padre: Mapped[list[SubProductoComponente]] = relationship(
        "SubProductoComponente",
        foreign_keys=[SubProductoComponente.padre_id],
        back_populates="padre",
        cascade="all, delete-orphan",
    )

    # ── Métodos de cálculo ──────────────────────────────────────────────────

    def tabla_nutricional(self) -> dict[str, float]:
        """
        Retorna los nutrientes por **100 g** del SubProducto producido,
        considerando la merma de humedad.

        Algoritmo
        ---------
        1. Para cada componente (ingrediente o sub-componente) se pondera
           su aporte nutricional por su porcentaje de uso (en base 100 g
           de entrada).
        2. Si hay merma de humedad, los nutrientes se concentran:
               factor_concentracion = 100 / (100 - merma_humedad_porcentaje)
           Es decir, al perder agua el peso disminuye pero los sólidos
           permanecen, por lo que la concentración sube.
        3. El resultado final es en base a 100 g del producto POST-merma.
        """
        acumulado: dict[str, float] = {n: 0.0 for n in _NUTRIENTES}

        # Aporte de Ingredientes directos
        for rel in self.relaciones_ingredientes:
            ing = rel.ingrediente
            factor = rel.porcentaje_uso / 100.0
            for nutriente in _NUTRIENTES:
                acumulado[nutriente] += getattr(ing, nutriente, 0.0) * factor

        # Aporte de SubProductos hijos (recursivo)
        for comp in self.relaciones_componentes_padre:
            hijo_tabla = comp.hijo.tabla_nutricional()
            factor = comp.porcentaje_uso / 100.0
            for nutriente in _NUTRIENTES:
                acumulado[nutriente] += hijo_tabla[nutriente] * factor

        # Concentración por merma de humedad
        if 0 < self.merma_humedad_porcentaje < 100:
            factor_concentracion = 100.0 / (100.0 - self.merma_humedad_porcentaje)
            for nutriente in _NUTRIENTES:
                acumulado[nutriente] *= factor_concentracion

        return acumulado

    def costo_total(self, kg: float = 1.0) -> float:
        """
        Costo en pesos de producir ``kg`` kg del SubProducto.

        Incluye:
        - Costo proporcional de ingredientes (ponderado por porcentaje de uso).
        - Costo proporcional de sub-componentes (recursivo).
        - Costo operativo adicional (costo_operativo_kg × kg producidos).

        El kg de entrada se refiere al peso POST-merma (producto final
        del proceso), por lo que se ajusta el peso de entrada necesario.
        """
        # kg de materia prima necesaria para obtener `kg` de producto final
        if 0 < self.merma_humedad_porcentaje < 100:
            kg_entrada = kg / (1.0 - self.merma_humedad_porcentaje / 100.0)
        else:
            kg_entrada = kg

        costo_materias = 0.0

        # Ingredientes directos (costo_kg ya es por kg de ingrediente puro)
        for rel in self.relaciones_ingredientes:
            fraccion = rel.porcentaje_uso / 100.0
            costo_materias += rel.ingrediente.costo_kg * fraccion * kg_entrada

        # Sub-componentes (costo recursivo, en base a kg de entrada del hijo)
        for comp in self.relaciones_componentes_padre:
            fraccion = comp.porcentaje_uso / 100.0
            kg_hijo = fraccion * kg_entrada
            costo_materias += comp.hijo.costo_total(kg=kg_hijo)

        return costo_materias + self.costo_operativo_kg * kg

    def __repr__(self) -> str:
        return (f"<SubProducto id={self.id} nombre='{self.nombre}' "
                f"merma={self.merma_humedad_porcentaje}%>")
