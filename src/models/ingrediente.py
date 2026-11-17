from datetime import datetime, date
from typing import TYPE_CHECKING

from sqlalchemy import (String, Float, Integer, Boolean, DateTime, Date, JSON,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base

if TYPE_CHECKING:
    from src.models.micronutriente import IngredienteMicronutriente


class Ingrediente(Base):
    """
    Materia prima pura (nodo hoja del BOM).

    Almacena la composición nutricional por cada 100g (macronutrientes como
    columnas fijas, micronutrientes como filas en ingrediente_micronutriente),
    costo por kg y datos de trazabilidad del proveedor.
    """
    __tablename__ = "ingredientes"
    __table_args__ = (
        UniqueConstraint('nombre', 'fabricante', name='_nombre_fabricante_uc'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String)
    fabricante: Mapped[str] = mapped_column(String)
    critico: Mapped[bool] = mapped_column(Boolean, default=False)
    costo_kg: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Trazabilidad ──────────────────────────────────────────────────────────
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False)
    # Las fichas técnicas no caducan: son válidas hasta que el proveedor emita
    # una nueva versión. Solo se registra cuándo ingresó la ficha al sistema.
    fecha_ingreso_ficha: Mapped[date | None] = mapped_column(
        Date, nullable=True, default=date.today)
    ruta_pdf_ficha: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None)
    # Vida útil de la materia prima, en semanas (hoja del árbol de caducidad)
    semanas_caducidad: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None)

    # ── Etiquetado: alérgenos, colorantes, edulcorantes, polialcoholes ────────
    # Códigos del catálogo src.etiquetado.DECLARABLES: alérgenos oficiales
    # (Res. Ex. 427/2010), colorantes de rotulación destacada (Art. 136),
    # edulcorantes no nutritivos (Art. 146) y polialcoholes (Art. 151).
    # Reasignar la lista completa al editar — SQLAlchemy no detecta
    # mutaciones in-place de una columna JSON.
    declarables: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False, server_default="'[]'")
    # Cafeína añadida o taurina (bebidas energéticas/fantasía, Art. 106 bis):
    # dispara la leyenda de advertencia, no es parte del catálogo anterior
    # porque no tiene un "nombre declarado" propio en la lista de ingredientes.
    cafeina_taurina: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0")
    # Advertencia de contaminación cruzada, tal como irá impresa.
    # Ej: "Puede contener maní." / "Elaborado en líneas que procesan leche."
    trazas: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Requerimientos alimentarios. El producto final solo los hereda si TODAS
    # sus materias primas los cumplen, por eso el default conservador es False.
    halal:         Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    kosher:        Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    vegetariano:   Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    vegano:        Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    apto_celiacos: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # ── Calorías y Proteínas ──────────────────────────────────────────────────
    energia_kcal: Mapped[float] = mapped_column(Float, default=0.0)
    proteinas_g: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Desglose de Grasas ────────────────────────────────────────────────────
    grasa_total_g: Mapped[float] = mapped_column(Float, default=0.0)
    grasa_saturada_g: Mapped[float] = mapped_column(Float, default=0.0)
    grasa_monoinsaturada_g: Mapped[float] = mapped_column(Float, default=0.0)
    grasa_poliinsaturada_g: Mapped[float] = mapped_column(Float, default=0.0)
    acidos_grasos_trans_g: Mapped[float] = mapped_column(Float, default=0.0)
    colesterol_mg: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Desglose de Carbohidratos ─────────────────────────────────────────────
    carbohidratos_disp_g: Mapped[float] = mapped_column(Float, default=0.0)
    azucares_totales_g: Mapped[float] = mapped_column(Float, default=0.0)
    sorbitol_g: Mapped[float] = mapped_column(Float, default=0.0)
    maltitol_g: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Desglose de Fibra ─────────────────────────────────────────────────────
    fibra_dietetica_g: Mapped[float] = mapped_column(Float, default=0.0)
    fibra_soluble_g: Mapped[float] = mapped_column(Float, default=0.0)
    fibra_insoluble_g: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Otros ─────────────────────────────────────────────────────────────────
    sodio_mg: Mapped[float] = mapped_column(Float, default=0.0)
    humedad_porcentaje: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Micronutrientes nativos (vitaminas y minerales por 100g) ─────────────
    micronutrientes: Mapped[list["IngredienteMicronutriente"]] = relationship(
        back_populates="ingrediente",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def id_unico(self) -> str:
        return f"{self.nombre} - {self.fabricante}"

    def __repr__(self) -> str:
        return f"<Ingrediente '{self.nombre}' ({self.fabricante})>"