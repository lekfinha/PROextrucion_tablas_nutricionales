from sqlalchemy import String, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base

class Ingrediente(Base):
    __tablename__ = "ingredientes"
    __table_args__ = (UniqueConstraint('nombre', 'fabricante', name='_nombre_fabricante_uc'),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String)
    fabricante: Mapped[str] = mapped_column(String)
    costo_kg: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Calorías y Proteínas
    energia_kcal: Mapped[float] = mapped_column(Float, default=0.0)
    proteinas_g: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Desglose de Grasas
    grasa_total_g: Mapped[float] = mapped_column(Float, default=0.0)
    grasa_saturada_g: Mapped[float] = mapped_column(Float, default=0.0)
    grasa_monoinsaturada_g: Mapped[float] = mapped_column(Float, default=0.0)
    grasa_poliinsaturada_g: Mapped[float] = mapped_column(Float, default=0.0)
    acidos_grasos_trans_g: Mapped[float] = mapped_column(Float, default=0.0)
    colesterol_mg: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Desglose de Carbohidratos
    carbohidratos_disp_g: Mapped[float] = mapped_column(Float, default=0.0)
    azucares_totales_g: Mapped[float] = mapped_column(Float, default=0.0)
    sorbitol_g: Mapped[float] = mapped_column(Float, default=0.0)
    maltitol_g: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Desglose de Fibra
    fibra_dietetica_g: Mapped[float] = mapped_column(Float, default=0.0)
    fibra_soluble_g: Mapped[float] = mapped_column(Float, default=0.0)
    fibra_insoluble_g: Mapped[float] = mapped_column(Float, default=0.0)
    
    sodio_mg: Mapped[float] = mapped_column(Float, default=0.0)
    humedad_porcentaje: Mapped[float] = mapped_column(Float, default=0.0)

    @property
    def id_unico(self):
        return f"{self.nombre} - {self.fabricante}"