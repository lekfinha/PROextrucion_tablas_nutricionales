import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

# Aseguramos que la carpeta data/ exista
os.makedirs("data", exist_ok=True)

# Motor de conexión a la base de datos local
engine = create_engine("sqlite:///data/nutricion.db", echo=False)

class Base(DeclarativeBase):
    pass