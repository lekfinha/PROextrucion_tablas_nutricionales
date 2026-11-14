import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase


def _directorio_base() -> Path:
    """
    Carpeta que contiene a data/.

    - Ejecutable PyInstaller (--onefile): junto al .exe. La base de datos debe
      persistir entre ejecuciones y viajar con el programa, no quedar en el
      directorio desde donde el usuario haya hecho doble clic.
    - Desarrollo: raíz del proyecto (src/ está un nivel más abajo).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


DATA_DIR = _directorio_base() / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "nutricion.db"

# Motor de conexión a la base de datos local
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


class Base(DeclarativeBase):
    pass


def migrar_columnas_faltantes() -> list[str]:
    """
    Agrega a data/nutricion.db las columnas que el modelo declara y la tabla
    todavía no tiene. create_all() crea tablas nuevas pero nunca altera las
    existentes, así que sin esto una base ya poblada revienta con
    "no such column" al agregar un campo.

    Solo cubre el caso ADD COLUMN. Una columna NOT NULL sin server_default no
    se puede agregar en SQLite y se omite (requiere migración manual).
    Retorna la lista de columnas agregadas, para log.
    """
    agregadas: list[str] = []
    with engine.begin() as con:
        for tabla in Base.metadata.sorted_tables:
            existentes = {fila[1] for fila in
                          con.exec_driver_sql(f'PRAGMA table_info("{tabla.name}")')}
            if not existentes:
                continue                      # tabla nueva: la crea create_all
            for col in tabla.columns:
                if col.name in existentes:
                    continue
                sql = (f'ALTER TABLE "{tabla.name}" ADD COLUMN '
                       f'"{col.name}" {col.type.compile(engine.dialect)}')
                if col.server_default is not None:
                    sql += f" DEFAULT {col.server_default.arg}"
                elif not col.nullable:
                    continue
                con.exec_driver_sql(sql)
                agregadas.append(f"{tabla.name}.{col.name}")
    return agregadas
