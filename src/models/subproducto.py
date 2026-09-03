"""
Modelos: SubProducto + tablas de asociación + Cascada de Costos Operativos.

Replica exactamente la matemática del Excel de Pro Extrusion:

NUTRICIONAL:
  1. Suma ponderada lineal de nutrientes  (proporción × nutriente de cada ingrediente)
  2. Suma ponderada lineal de humedad     (proporción × humedad de cada ingrediente)
  3. Merma = humedad_ponderada − humedad_final_subproducto
  4. Factor concentración = 1 / (1 − merma)
  5. Nutriente final = suma_lineal × factor_concentración

COSTOS:
  1. Costo base = suma ponderada de costo_kg de ingredientes
  2. Cascada secuencial de CostoOperativo (porcentual o fijo)
     - Porcentual: costo_nuevo = costo_anterior / (1 − porcentaje)
     - Fijo:       costo_nuevo = costo_anterior + valor_fijo
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.ingrediente import Ingrediente


# ──────────────────────────────────────────────────────────────────────────────
# Campos nutricionales que se propagan (misma lista que Ingrediente)
# ──────────────────────────────────────────────────────────────────────────────

NUTRIENTES = [
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


# ──────────────────────────────────────────────────────────────────────────────
# Tabla de asociación: SubProducto ↔ Ingrediente  (con proporción de uso)
# ──────────────────────────────────────────────────────────────────────────────

class SubProductoIngrediente(Base):
    """
    Qué fracción (0.0–1.0) de un Ingrediente forma parte del SubProducto.

    Ejemplo: Harina de Arroz al 35.75% → proporcion = 0.3575
    La suma de todas las proporciones de un SubProducto debe ser 1.0.
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
    # Proporción en peso (0.0–1.0). Ejemplo: 0.3575 = 35.75%
    proporcion: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones ORM
    subproducto: Mapped["SubProducto"] = relationship(
        back_populates="receta_ingredientes")
    ingrediente: Mapped["Ingrediente"] = relationship()


# ──────────────────────────────────────────────────────────────────────────────
# Tabla de asociación: SubProducto ↔ SubProducto  (composición anidada)
# ──────────────────────────────────────────────────────────────────────────────

class SubProductoComponente(Base):
    """
    Permite que un SubProducto (padre) contenga otro SubProducto (hijo)
    como componente de su receta.

    Ejemplo: "PT Granel" contiene 70% de "Extrusión" y 30% de "Jarabe".
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
    # Proporción en peso (0.0–1.0). Ejemplo: 0.7 = 70%
    proporcion: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones ORM
    padre: Mapped["SubProducto"] = relationship(
        "SubProducto",
        foreign_keys=[padre_id],
        back_populates="receta_componentes",
    )
    hijo: Mapped["SubProducto"] = relationship(
        "SubProducto",
        foreign_keys=[hijo_id],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Cascada de Costos Operativos
# ──────────────────────────────────────────────────────────────────────────────

class CostoOperativo(Base):
    """
    Un paso en la cascada de costos de un SubProducto.

    Cada paso se aplica secuencialmente (ordenado por `orden`) al costo
    acumulado anterior:

    - tipo = "porcentual":
        costo_nuevo = costo_anterior / (1 − valor)
        Ejemplo: Tamizado pierde 1% → valor = 0.01
                 Extrusión pierde 6.6277% → valor = 0.066277

    - tipo = "fijo":
        costo_nuevo = costo_anterior + valor
        Ejemplo: Energía suma $200 CLP/kg → valor = 200
                 Envase suma $14 CLP/kg  → valor = 14
    """
    __tablename__ = "costos_operativos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    subproducto_id: Mapped[int] = mapped_column(
        ForeignKey("subproductos.id", ondelete="CASCADE"),
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)  # "porcentual" | "fijo"
    valor: Mapped[float] = mapped_column(Float, default=0.0)
    # Orden de aplicación en la cascada (1, 2, 3...)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    # Relación ORM
    subproducto: Mapped["SubProducto"] = relationship(
        back_populates="costos_operativos")

    def aplicar(self, costo_entrada: float) -> float:
        """Aplica este paso al costo de entrada y retorna el costo de salida."""
        if self.tipo == "porcentual":
            if self.valor >= 1.0:
                raise ValueError(
                    f"CostoOperativo '{self.nombre}': valor porcentual {self.valor} "
                    f"debe ser < 1.0 (es una fracción, no un porcentaje).")
            return costo_entrada / (1.0 - self.valor)
        elif self.tipo == "fijo":
            return costo_entrada + self.valor
        else:
            raise ValueError(
                f"CostoOperativo '{self.nombre}': tipo '{self.tipo}' no reconocido. "
                f"Use 'porcentual' o 'fijo'.")

    def __repr__(self) -> str:
        return (f"<CostoOperativo '{self.nombre}' tipo={self.tipo} "
                f"valor={self.valor} orden={self.orden}>")


# ──────────────────────────────────────────────────────────────────────────────
# Modelo principal: SubProducto
# ──────────────────────────────────────────────────────────────────────────────

class SubProducto(Base):
    """
    Fase de proceso (nodo BOM).

    Puede contener Ingredientes directos y/o otros SubProductos como
    componentes.  Expone métodos para calcular la tabla nutricional
    (con concentración por merma) y el costo (con cascada operativa).

    Atributos clave:
    - humedad_final: fracción (0.0–1.0) de humedad que tiene el
      subproducto DESPUÉS del proceso. Ejemplo: 0.03 = 3%.
      La merma se calcula automáticamente como:
          merma = humedad_ponderada_ingredientes − humedad_final
    """
    __tablename__ = "subproductos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text, default="")
    critico: Mapped[bool] = mapped_column(Boolean, default=False)

    # Humedad final del subproducto como fracción (0.0–1.0).
    # Ejemplo: extruido sale con 3% de humedad → humedad_final = 0.03
    humedad_final: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Relaciones ORM ──────────────────────────────────────────────────────
    receta_ingredientes: Mapped[list[SubProductoIngrediente]] = relationship(
        back_populates="subproducto",
        cascade="all, delete-orphan",
    )
    receta_componentes: Mapped[list[SubProductoComponente]] = relationship(
        "SubProductoComponente",
        foreign_keys=[SubProductoComponente.padre_id],
        back_populates="padre",
        cascade="all, delete-orphan",
    )
    costos_operativos: Mapped[list[CostoOperativo]] = relationship(
        back_populates="subproducto",
        cascade="all, delete-orphan",
        order_by="CostoOperativo.orden",
    )

    # ── Cálculos Nutricionales ──────────────────────────────────────────────

    def _humedad_ponderada(self) -> float:
        """
        Calcula la humedad lineal ponderada de todos los componentes.
        Es la suma: Σ (proporción_i × humedad_i) para cada ingrediente
        y sub-componente.
        """
        humedad = 0.0

        for rel in self.receta_ingredientes:
            humedad += rel.proporcion * rel.ingrediente.humedad_porcentaje

        for comp in self.receta_componentes:
            # Para un sub-componente, su "humedad" es su humedad_final
            # (ya pasó por su propio proceso)
            humedad += comp.proporcion * comp.hijo.humedad_final

        return humedad

    def merma(self) -> float:
        """
        Merma de humedad del proceso.

        merma = humedad_ponderada_ingredientes − humedad_final

        Ejemplo: ingredientes mezclan a 9.63% de humedad, extrusión
        seca hasta 3% → merma = 0.0963 − 0.03 = 0.0663 (6.63%)
        """
        return max(0.0, self._humedad_ponderada() - self.humedad_final)

    def factor_concentracion(self) -> float:
        """
        Factor por el cual se concentran los nutrientes al perder humedad.

        factor = 1 / (1 − merma)

        Ejemplo: merma = 0.0663 → factor = 1.071 (nutrientes suben ~7.1%)
        """
        m = self.merma()
        if m >= 1.0:
            raise ValueError(
                f"SubProducto '{self.nombre}': merma {m} >= 1.0 es imposible.")
        return 1.0 / (1.0 - m) if m > 0 else 1.0

    def tabla_nutricional(self) -> dict[str, float]:
        """
        Retorna los nutrientes por **100 g** del SubProducto producido.

        Algoritmo (replica el Excel exactamente):
        1. Suma ponderada lineal: Σ (proporción_i × nutriente_i)
        2. Merma = humedad_ponderada − humedad_final
        3. Factor = 1 / (1 − merma)
        4. Nutriente_final = suma_lineal × factor
        """
        acumulado: dict[str, float] = {n: 0.0 for n in NUTRIENTES}

        # Aporte de Ingredientes directos
        for rel in self.receta_ingredientes:
            ing = rel.ingrediente
            for nutriente in NUTRIENTES:
                acumulado[nutriente] += rel.proporcion * getattr(ing, nutriente, 0.0)

        # Aporte de SubProductos hijos (sus tablas ya tienen concentración aplicada)
        for comp in self.receta_componentes:
            hijo_tabla = comp.hijo.tabla_nutricional()
            for nutriente in NUTRIENTES:
                acumulado[nutriente] += comp.proporcion * hijo_tabla[nutriente]

        # Aplicar concentración por merma de humedad
        factor = self.factor_concentracion()
        if factor != 1.0:
            for nutriente in NUTRIENTES:
                acumulado[nutriente] *= factor

        return acumulado

    def tabla_nutricional_porcion(self, porcion_g: float = 25.0) -> dict[str, float]:
        """Retorna los nutrientes escalados a una porción de `porcion_g` gramos."""
        base = self.tabla_nutricional()
        factor = porcion_g / 100.0
        return {n: v * factor for n, v in base.items()}

    # ── Cálculos de Costos ──────────────────────────────────────────────────

    def costo_base_kg(self) -> float:
        """
        Costo base por kg: suma ponderada de los costos de ingredientes
        y sub-componentes (antes de la cascada operativa).
        """
        costo = 0.0

        for rel in self.receta_ingredientes:
            costo += rel.proporcion * rel.ingrediente.costo_kg

        for comp in self.receta_componentes:
            # El costo del sub-componente ya incluye su cascada operativa
            costo += comp.proporcion * comp.hijo.costo_final_kg()

        return costo

    def costo_final_kg(self) -> float:
        """
        Costo final por kg después de aplicar la cascada de costos
        operativos en orden secuencial.

        Ejemplo cascada de Extrusión:
          Base: $905.72 → Partida/Parada (÷0.972) → $931.86
          → Extrusión (÷0.934) → $998.00 → Tamizado (÷0.99) → $1008.08
          → Energía (+200) → $1208.08 → Envase (+14) → $1222.08
        """
        costo = self.costo_base_kg()
        for paso in self.costos_operativos:
            costo = paso.aplicar(costo)
        return costo

    def __repr__(self) -> str:
        return (f"<SubProducto id={self.id} nombre='{self.nombre}' "
                f"humedad_final={self.humedad_final}>")
