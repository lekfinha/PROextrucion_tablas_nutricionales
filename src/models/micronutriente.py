"""
Modelos de Micronutrientes — RSA Art 118 y 115 letra b.

Catálogo de vitaminas y minerales con sus DDR (Dosis Diaria de Referencia)
y tabla de asociación para declarar micronutrientes en cada Producto.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Micronutriente(Base):
    """
    Catálogo de vitaminas y minerales con su DDR.

    Ejemplo: Vitamina A — DDR = 600 mcg, Calcio — DDR = 1000 mg
    Pre-cargado con valores del RSA chileno.
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

    Un micronutriente se incluye en la tabla nutricional SOLO si:
    - Su valor por porción ≥ 5% de su DDR (RSA Art 118), O
    - destacado_en_envase = True (ej: "Fortificado con Calcio")
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

    # Relaciones
    producto: Mapped["Producto"] = relationship(  # noqa: F821
        back_populates="micronutrientes")
    micronutriente: Mapped[Micronutriente] = relationship()

    def __repr__(self) -> str:
        return (f"<ProductoMicronutriente producto_id={self.producto_id} "
                f"micro='{self.micronutriente_id}' "
                f"cant_100g={self.cantidad_100g}>")


# ──────────────────────────────────────────────────────────────────────────────
# Catálogo DDR estándar del RSA Chile
# ──────────────────────────────────────────────────────────────────────────────

DDR_RSA_CHILE: list[dict] = [
    {"nombre": "Vitamina A",             "unidad": "mcg",  "ddr": 600.0},
    {"nombre": "Vitamina C",             "unidad": "mg",   "ddr": 45.0},
    {"nombre": "Vitamina D",             "unidad": "mcg",  "ddr": 5.0},
    {"nombre": "Vitamina E",             "unidad": "mg",   "ddr": 10.0},
    {"nombre": "Vitamina K",             "unidad": "mcg",  "ddr": 65.0},
    {"nombre": "Vitamina B1 (Tiamina)",  "unidad": "mg",   "ddr": 1.2},
    {"nombre": "Vitamina B2 (Riboflavina)", "unidad": "mg","ddr": 1.3},
    {"nombre": "Vitamina B3 (Niacina)",  "unidad": "mg",   "ddr": 16.0},
    {"nombre": "Vitamina B6",            "unidad": "mg",   "ddr": 1.3},
    {"nombre": "Vitamina B12",           "unidad": "mcg",  "ddr": 2.4},
    {"nombre": "Ácido Fólico",           "unidad": "mcg",  "ddr": 400.0},
    {"nombre": "Ácido Pantoténico",      "unidad": "mg",   "ddr": 5.0},
    {"nombre": "Biotina",                "unidad": "mcg",  "ddr": 30.0},
    {"nombre": "Calcio",                 "unidad": "mg",   "ddr": 1000.0},
    {"nombre": "Hierro",                 "unidad": "mg",   "ddr": 14.0},
    {"nombre": "Zinc",                   "unidad": "mg",   "ddr": 11.0},
    {"nombre": "Fósforo",                "unidad": "mg",   "ddr": 700.0},
    {"nombre": "Magnesio",               "unidad": "mg",   "ddr": 310.0},
    {"nombre": "Potasio",                "unidad": "mg",   "ddr": 3500.0},
    {"nombre": "Cobre",                  "unidad": "mg",   "ddr": 0.9},
    {"nombre": "Manganeso",              "unidad": "mg",   "ddr": 2.3},
    {"nombre": "Selenio",                "unidad": "mcg",  "ddr": 55.0},
    {"nombre": "Yodo",                   "unidad": "mcg",  "ddr": 150.0},
]
