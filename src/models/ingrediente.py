from datetime import datetime, date
from sqlalchemy import String, Float, Integer, Boolean, DateTime, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class Ingrediente(Base):
    """
    Materia prima pura (nodo hoja del BOM).

    Almacena la composición nutricional por cada 100g, costo por kg,
    y datos de trazabilidad del proveedor.
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
    fecha_vencimiento_ficha: Mapped[date | None] = mapped_column(
        Date, nullable=True, default=None)
    ruta_pdf_ficha: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None)
    meses_caducidad: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None)

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

    @property
    def id_unico(self) -> str:
        return f"{self.nombre} - {self.fabricante}"

    def __repr__(self) -> str:
        return f"<Ingrediente '{self.nombre}' ({self.fabricante})>"