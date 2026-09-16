"""
Modelos de Micronutrientes — RSA Art 118 y 115 letra b.

Catálogo de vitaminas y minerales con sus DDR (Dosis Diaria de Referencia)
según el Codex Alimentarius (CAC/GL 2-1985). Para Vitamina E, Biotina,
Ácido Pantoténico, Cobre y Selenio se usan los RDI de la FDA, como
establece el RSA Art 118.

Tablas de asociación para declarar micronutrientes tanto en materias primas
(Ingrediente) como en nodos del BOM (Producto).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Micronutriente(Base):
    """
    Catálogo de vitaminas y minerales con su DDR (valor_ddr).

    Ejemplo: Vitamina A — DDR = 800 µg (Codex), Selenio — DDR = 55 µg (FDA)
    Pre-cargado con valores oficiales.
    """
    __tablename__ = "micronutrientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    unidad: Mapped[str] = mapped_column(String, nullable=False)
    ddr: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<Micronutriente '{self.nombre}' DDR={self.ddr} {self.unidad}>"


class ProductoMicronutriente(Base):
    """
    Micronutrientes específicos declarados en un Producto.

    Reglas de inclusión (RSA Art 118):
    - Un micronutriente se incluye en la tabla nutricional si su valor
      por porción ≥ 5% de su DDR.
    - Si destacado_en_envase=True, se incluye siempre.

    Descriptor (RSA Art 120):
    - es_adicionado=True indica que fue fortificado artificialmente.
      Permite usar el descriptor "Fortificado/Enriquecido en {nombre}"
      si la adición por porción ≥ 10% DDR.
    """
    __tablename__ = "producto_micronutriente"

    producto_id: Mapped[int] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    micronutriente_id: Mapped[int] = mapped_column(
        ForeignKey("micronutrientes.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    cantidad_100g: Mapped[float] = mapped_column(Float, default=0.0)
    destacado_en_envase: Mapped[bool] = mapped_column(Boolean, default=False)
    es_adicionado: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relaciones
    producto: Mapped["Producto"] = relationship(  # noqa: F821
        back_populates="micronutrientes")
    micronutriente: Mapped[Micronutriente] = relationship()

    def __repr__(self) -> str:
        return (f"<ProductoMicronutriente producto_id={self.producto_id} "
                f"micro='{self.micronutriente_id}' "
                f"cant_100g={self.cantidad_100g}>")


class IngredienteMicronutriente(Base):
    """
    Micronutrientes nativos de una materia prima, expresados por 100 g.

    A diferencia de ProductoMicronutriente no lleva flags de etiquetado: un
    ingrediente aporta lo que aporta, y las decisiones de declaración (destacar
    en envase, fortificar) se toman a nivel de Producto.

    Estos valores se propagan hacia arriba por el árbol BOM ponderados por la
    proporción de cada componente y escalados por el factor de concentración,
    igual que los macronutrientes — ver Producto.micronutrientes_agregados_100g().
    """
    __tablename__ = "ingrediente_micronutriente"

    ingrediente_id: Mapped[int] = mapped_column(
        ForeignKey("ingredientes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    micronutriente_id: Mapped[int] = mapped_column(
        ForeignKey("micronutrientes.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    cantidad_100g: Mapped[float] = mapped_column(Float, default=0.0)

    # Relaciones
    ingrediente: Mapped["Ingrediente"] = relationship(  # noqa: F821
        back_populates="micronutrientes")
    micronutriente: Mapped[Micronutriente] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return (f"<IngredienteMicronutriente ingrediente_id={self.ingrediente_id} "
                f"micro={self.micronutriente_id} cant_100g={self.cantidad_100g}>")


# ──────────────────────────────────────────────────────────────────────────────
# Catálogo DDR — Codex Alimentarius + excepciones FDA (RSA Art 118)
#
# Fuentes:
#   - Codex Alimentarius, CAC/GL 2-1985 (NRV para etiquetado nutricional)
#   - FDA 21 CFR 101.9 (Daily Reference Values, 2016 final rule)
#     → Aplica para: Vitamina E, Biotina, Ác. Pantoténico, Cobre, Selenio
# ──────────────────────────────────────────────────────────────────────────────

DDR_RSA_CHILE: list[dict] = [
    # ── Vitaminas ─────────────────────────────────────────────────────────────
    {"nombre": "Vitamina A",                 "unidad": "µg",  "ddr": 800.0},   # Codex
    {"nombre": "Vitamina C",                 "unidad": "mg",  "ddr": 60.0},    # Codex
    {"nombre": "Vitamina D",                 "unidad": "µg",  "ddr": 5.0},     # Codex
    {"nombre": "Vitamina E",                 "unidad": "mg",  "ddr": 10.0},    # FDA RDI
    {"nombre": "Vitamina K",                 "unidad": "µg",  "ddr": 80.0},    # FDA
    {"nombre": "Tiamina (Vitamina B1)",      "unidad": "mg",  "ddr": 1.4},     # Codex
    {"nombre": "Riboflavina (Vitamina B2)",  "unidad": "mg",  "ddr": 1.6},     # Codex
    {"nombre": "Niacina (Vitamina B3)",      "unidad": "mg",  "ddr": 18.0},    # Codex
    {"nombre": "Vitamina B6",                "unidad": "mg",  "ddr": 2.0},     # Codex
    {"nombre": "Ácido Fólico (Vitamina B9)", "unidad": "µg",  "ddr": 200.0},   # Codex
    {"nombre": "Vitamina B12",               "unidad": "µg",  "ddr": 1.0},     # Codex
    {"nombre": "Biotina",                    "unidad": "µg",  "ddr": 30.0},    # FDA RDI
    {"nombre": "Ácido Pantoténico",          "unidad": "mg",  "ddr": 5.0},     # FDA RDI
    # ── Minerales ─────────────────────────────────────────────────────────────
    {"nombre": "Calcio",                     "unidad": "mg",  "ddr": 800.0},   # Codex
    {"nombre": "Hierro",                     "unidad": "mg",  "ddr": 14.0},    # Codex
    {"nombre": "Fósforo",                    "unidad": "mg",  "ddr": 800.0},   # Codex
    {"nombre": "Yodo",                       "unidad": "µg",  "ddr": 150.0},   # Codex
    {"nombre": "Magnesio",                   "unidad": "mg",  "ddr": 300.0},   # Codex
    {"nombre": "Zinc",                       "unidad": "mg",  "ddr": 15.0},    # Codex
    {"nombre": "Selenio",                    "unidad": "µg",  "ddr": 55.0},    # FDA RDI
    {"nombre": "Cobre",                      "unidad": "mg",  "ddr": 0.9},     # FDA RDI
]
