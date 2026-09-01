"""
Modelos: ProductoFinal, ProductoFinalSubProducto

Representa el producto empaquetado final (raíz del árbol BOM).
Puede contener SubProductos con sus porcentajes de uso y expone
métodos para generar la tabla nutricional en base a 100 g y por porción.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.subproducto import SubProducto

# ──────────────────────────────────────────────────────────────────────────────
# Tabla de asociación: ProductoFinal ↔ SubProducto
# ──────────────────────────────────────────────────────────────────────────────

class ProductoFinalSubProducto(Base):
    """
    Relaciona un ProductoFinal con sus SubProductos componentes,
    indicando qué porcentaje (en peso) aporta cada uno.

    Ejemplo: "Cereal Welliz Canela" contiene
        60% "Base Extruida" + 30% "Jarabe Canela" + 10% "Sazonador".
    """
    __tablename__ = "productofinal_subproducto"

    productofinal_id: Mapped[int] = mapped_column(
        ForeignKey("productos_finales.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subproducto_id: Mapped[int] = mapped_column(
        ForeignKey("subproductos.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    # Porcentaje en peso que este sub-producto aporta al producto final (0–100)
    porcentaje_uso: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones ORM
    producto_final: Mapped["ProductoFinal"] = relationship(
        back_populates="relaciones_subproductos")
    subproducto: Mapped["SubProducto"] = relationship()


# ──────────────────────────────────────────────────────────────────────────────
# Campos nutricionales propagados (misma lista que SubProducto)
# ──────────────────────────────────────────────────────────────────────────────

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

# Etiquetas legibles para mostrar en la tabla nutricional imprimible
ETIQUETAS_NUTRIENTES: dict[str, str] = {
    "energia_kcal":             "Energía (kcal)",
    "proteinas_g":              "Proteínas (g)",
    "grasa_total_g":            "Grasa Total (g)",
    "grasa_saturada_g":         "  - Grasa Saturada (g)",
    "grasa_monoinsaturada_g":   "  - Grasa Monoinsaturada (g)",
    "grasa_poliinsaturada_g":   "  - Grasa Poliinsaturada (g)",
    "acidos_grasos_trans_g":    "  - Ácidos Grasos Trans (g)",
    "colesterol_mg":            "Colesterol (mg)",
    "carbohidratos_disp_g":     "H. de Carbono Disponibles (g)",
    "azucares_totales_g":       "  - Azúcares Totales (g)",
    "sorbitol_g":               "  - Sorbitol (g)",
    "maltitol_g":               "  - Maltitol (g)",
    "fibra_dietetica_g":        "Fibra Dietética (g)",
    "fibra_soluble_g":          "  - Fibra Soluble (g)",
    "fibra_insoluble_g":        "  - Fibra Insoluble (g)",
    "sodio_mg":                 "Sodio (mg)",
}


# ──────────────────────────────────────────────────────────────────────────────
# Modelo principal: ProductoFinal
# ──────────────────────────────────────────────────────────────────────────────

class ProductoFinal(Base):
    """
    Producto empaquetado terminado (raíz del árbol BOM).

    Atributos clave
    ---------------
    porcion_g   : gramos por porción declarada en el etiquetado (ej. 25 g).
    gramaje_g   : gramaje total del empaque (ej. 200 g).
    """
    __tablename__ = "productos_finales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text, default="")

    # Gramaje para etiquetado
    porcion_g: Mapped[float] = mapped_column(Float, default=25.0)
    gramaje_g: Mapped[float] = mapped_column(Float, default=200.0)

    # Relación con SubProductos
    relaciones_subproductos: Mapped[list[ProductoFinalSubProducto]] = relationship(
        back_populates="producto_final",
        cascade="all, delete-orphan",
    )

    # ── Métodos de cálculo nutricional ──────────────────────────────────────

    def _tabla_base(self) -> dict[str, float]:
        """
        Nutrientes por 100 g del producto final, ponderando la
        contribución de cada SubProducto según su porcentaje de uso.
        """
        acumulado: dict[str, float] = {n: 0.0 for n in _NUTRIENTES}
        for rel in self.relaciones_subproductos:
            sp_tabla = rel.subproducto.tabla_nutricional()
            factor = rel.porcentaje_uso / 100.0
            for nutriente in _NUTRIENTES:
                acumulado[nutriente] += sp_tabla[nutriente] * factor
        return acumulado

    def tabla_nutricional_100g(self) -> dict[str, float]:
        """Retorna la tabla nutricional por **100 g** del producto final."""
        return self._tabla_base()

    def tabla_nutricional_porcion(self) -> dict[str, float]:
        """
        Retorna la tabla nutricional por **porción** (self.porcion_g g).
        Todos los valores se escalan linealmente desde la base de 100 g.
        """
        base = self._tabla_base()
        factor = self.porcion_g / 100.0
        return {n: round(v * factor, 4) for n, v in base.items()}

    def tabla_nutricional_formateada(self) -> list[dict]:
        """
        Retorna una lista de dicts lista para mostrar en Streamlit o
        exportar a Excel, con columnas:
          Nutriente | Por 100 g | Por porción (X g)
        """
        base_100 = self.tabla_nutricional_100g()
        base_porcion = self.tabla_nutricional_porcion()
        filas = []
        for key in _NUTRIENTES:
            filas.append({
                "Nutriente": ETIQUETAS_NUTRIENTES.get(key, key),
                "Por 100 g": round(base_100[key], 2),
                f"Por porción ({self.porcion_g:.0f} g)": round(base_porcion[key], 2),
            })
        return filas

    # ── Métodos de costeo ───────────────────────────────────────────────────

    def costo_total_kg(self) -> float:
        """
        Costo en pesos de producir 1 kg del producto final,
        ponderando el costo de cada SubProducto por su fracción de uso.
        """
        total = 0.0
        for rel in self.relaciones_subproductos:
            fraccion = rel.porcentaje_uso / 100.0
            # costo_total(kg=fraccion) = costo de producir `fraccion` kg del SP
            total += rel.subproducto.costo_total(kg=fraccion)
        return total

    def costo_por_porcion(self) -> float:
        """Costo en pesos de una porción (self.porcion_g g)."""
        return self.costo_total_kg() * (self.porcion_g / 1000.0)

    def costo_empaque(self) -> float:
        """Costo en pesos del gramaje completo del empaque."""
        return self.costo_total_kg() * (self.gramaje_g / 1000.0)

    def __repr__(self) -> str:
        return (f"<ProductoFinal id={self.id} nombre='{self.nombre}' "
                f"porcion={self.porcion_g}g gramaje={self.gramaje_g}g>")
