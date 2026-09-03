"""
Modelos: ProductoFinal y ProductoFinalSubProducto.

El ProductoFinal es la raíz del árbol BOM. Es conceptualmente idéntico
a un SubProducto que contiene otros SubProductos, con la misma fórmula
de concentración y cascada de costos.

Expone además métodos para el formato dual (100g + porción) y el
formato de tabla formateado listo para Streamlit/Excel.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.subproducto import (
    NUTRIENTES,
    CostoOperativo,
    SubProducto,
)


# ──────────────────────────────────────────────────────────────────────────────
# Tabla de asociación: ProductoFinal ↔ SubProducto
# ──────────────────────────────────────────────────────────────────────────────

class ProductoFinalSubProducto(Base):
    """
    Relaciona un ProductoFinal con sus SubProductos componentes.

    Ejemplo: "Cereal Welliz Canela" =
        70% "Extrusión" + 30% "Jarabe" + 0% "Sazonador".
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
    # Proporción en peso (0.0–1.0). Ejemplo: 0.7 = 70%
    proporcion: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones ORM
    producto_final: Mapped["ProductoFinal"] = relationship(
        back_populates="receta_subproductos")
    subproducto: Mapped["SubProducto"] = relationship()


# ──────────────────────────────────────────────────────────────────────────────
# Etiquetas legibles para la tabla nutricional imprimible
# ──────────────────────────────────────────────────────────────────────────────

ETIQUETAS_NUTRIENTES: dict[str, str] = {
    "energia_kcal":             "Energía (kcal)",
    "proteinas_g":              "Proteínas (g)",
    "grasa_total_g":            "Grasa Total (g)",
    "grasa_saturada_g":         "    Grasa Saturada (g)",
    "grasa_monoinsaturada_g":   "    Grasa Monoinsaturada (g)",
    "grasa_poliinsaturada_g":   "    Grasa Poliinsaturada (g)",
    "acidos_grasos_trans_g":    "    Ácidos Grasos Trans (g)",
    "colesterol_mg":            "Colesterol (mg)",
    "carbohidratos_disp_g":     "H. de Carbono Disponibles (g)",
    "azucares_totales_g":       "    Azúcares Totales (g)",
    "sorbitol_g":               "    Sorbitol (g)",
    "maltitol_g":               "    Maltitol (g)",
    "fibra_dietetica_g":        "Fibra Dietética (g)",
    "fibra_soluble_g":          "    Fibra Soluble (g)",
    "fibra_insoluble_g":        "    Fibra Insoluble (g)",
    "sodio_mg":                 "Sodio (mg)",
}


# ──────────────────────────────────────────────────────────────────────────────
# Modelo principal: ProductoFinal
# ──────────────────────────────────────────────────────────────────────────────

class ProductoFinal(Base):
    """
    Producto empaquetado terminado (raíz del árbol BOM).

    Usa la MISMA fórmula de concentración que SubProducto:
      1. Suma ponderada de tablas nutricionales de sus SubProductos
      2. humedad_ponderada = Σ (proporción_i × humedad_final_i del SP)
      3. merma = humedad_ponderada − humedad_final
      4. factor = 1 / (1 − merma)
      5. nutriente_final = suma_lineal × factor

    Atributos:
    - porcion_g: gramos por porción declarada en el etiquetado (ej. 25 g)
    - gramaje_g: gramaje total del empaque (ej. 200 g)
    - humedad_final: humedad del producto terminado como fracción (ej. 0.04)
    """
    __tablename__ = "productos_finales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text, default="")

    # Gramaje para etiquetado
    porcion_g: Mapped[float] = mapped_column(Float, default=25.0)
    gramaje_g: Mapped[float] = mapped_column(Float, default=200.0)

    # Humedad final del producto terminado como fracción (0.0–1.0)
    humedad_final: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones
    receta_subproductos: Mapped[list[ProductoFinalSubProducto]] = relationship(
        back_populates="producto_final",
        cascade="all, delete-orphan",
    )
    costos_operativos: Mapped[list["CostoOperativoPT"]] = relationship(
        back_populates="producto_final",
        cascade="all, delete-orphan",
        order_by="CostoOperativoPT.orden",
    )

    # ── Cálculos Nutricionales ──────────────────────────────────────────────

    def _humedad_ponderada(self) -> float:
        """Humedad ponderada de los SubProductos componentes."""
        return sum(
            rel.proporcion * rel.subproducto.humedad_final
            for rel in self.receta_subproductos
        )

    def merma(self) -> float:
        """Merma = humedad_ponderada − humedad_final."""
        return max(0.0, self._humedad_ponderada() - self.humedad_final)

    def factor_concentracion(self) -> float:
        """Factor = 1 / (1 − merma)."""
        m = self.merma()
        if m >= 1.0:
            raise ValueError(
                f"ProductoFinal '{self.nombre}': merma {m} >= 1.0 es imposible.")
        return 1.0 / (1.0 - m) if m > 0 else 1.0

    def tabla_nutricional_100g(self) -> dict[str, float]:
        """
        Composición nutricional por 100 g del producto final.

        Misma fórmula que SubProducto:
        1. Suma ponderada lineal de las tablas de cada SubProducto
        2. Multiplicar por factor de concentración
        """
        acumulado: dict[str, float] = {n: 0.0 for n in NUTRIENTES}

        for rel in self.receta_subproductos:
            sp_tabla = rel.subproducto.tabla_nutricional()
            for nutriente in NUTRIENTES:
                acumulado[nutriente] += rel.proporcion * sp_tabla[nutriente]

        factor = self.factor_concentracion()
        if factor != 1.0:
            for nutriente in NUTRIENTES:
                acumulado[nutriente] *= factor

        return acumulado

    def tabla_nutricional_porcion(self) -> dict[str, float]:
        """Nutrientes por porción (self.porcion_g gramos)."""
        base = self.tabla_nutricional_100g()
        factor = self.porcion_g / 100.0
        return {n: v * factor for n, v in base.items()}

    def tabla_nutricional_formateada(self) -> list[dict]:
        """
        Lista de dicts lista para Streamlit o exportar a Excel:
          Nutriente | Por 100 g | Por porción (X g)
        """
        base_100 = self.tabla_nutricional_100g()
        base_porcion = self.tabla_nutricional_porcion()
        filas = []
        for key in NUTRIENTES:
            filas.append({
                "Nutriente": ETIQUETAS_NUTRIENTES.get(key, key),
                "Por 100 g": round(base_100[key], 2),
                f"Por porción ({self.porcion_g:.0f} g)": round(base_porcion[key], 2),
            })
        return filas

    # ── Cálculos de Costos ──────────────────────────────────────────────────

    def costo_base_kg(self) -> float:
        """Costo base: suma ponderada de costo_final_kg de cada SubProducto."""
        return sum(
            rel.proporcion * rel.subproducto.costo_final_kg()
            for rel in self.receta_subproductos
        )

    def costo_final_kg(self) -> float:
        """Costo final por kg después de la cascada de costos operativos."""
        costo = self.costo_base_kg()
        for paso in self.costos_operativos:
            costo = paso.aplicar(costo)
        return costo

    def costo_por_porcion(self) -> float:
        """Costo en pesos de una porción (self.porcion_g gramos)."""
        return self.costo_final_kg() * (self.porcion_g / 1000.0)

    def costo_empaque(self) -> float:
        """Costo en pesos del gramaje completo del empaque."""
        return self.costo_final_kg() * (self.gramaje_g / 1000.0)

    def __repr__(self) -> str:
        return (f"<ProductoFinal id={self.id} nombre='{self.nombre}' "
                f"porcion={self.porcion_g}g gramaje={self.gramaje_g}g>")


# ──────────────────────────────────────────────────────────────────────────────
# Cascada de Costos Operativos para ProductoFinal
# ──────────────────────────────────────────────────────────────────────────────

class CostoOperativoPT(Base):
    """
    Idéntico a CostoOperativo pero para ProductoFinal.

    Ejemplo cascada de PT Granel:
      Base: $2167.69 → Cobertura (÷0.97) → $2234.73
      → Energía (+30) → $2264.73 → Envase (+21.23) → $2285.96
    """
    __tablename__ = "costos_operativos_pt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    productofinal_id: Mapped[int] = mapped_column(
        ForeignKey("productos_finales.id", ondelete="CASCADE"),
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)  # "porcentual" | "fijo"
    valor: Mapped[float] = mapped_column(Float, default=0.0)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    # Relación ORM
    producto_final: Mapped["ProductoFinal"] = relationship(
        back_populates="costos_operativos")

    def aplicar(self, costo_entrada: float) -> float:
        """Aplica este paso al costo de entrada."""
        if self.tipo == "porcentual":
            return costo_entrada / (1.0 - self.valor)
        elif self.tipo == "fijo":
            return costo_entrada + self.valor
        else:
            raise ValueError(f"Tipo '{self.tipo}' no reconocido.")

    def __repr__(self) -> str:
        return (f"<CostoOperativoPT '{self.nombre}' tipo={self.tipo} "
                f"valor={self.valor} orden={self.orden}>")
