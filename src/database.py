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
