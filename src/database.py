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


# Columnas que el modelo dejó de usar y hay que quitar de bases antiguas.
# Se listan a mano: borrar "todo lo que no esté en el modelo" convertiría un
# typo en pérdida de datos.
#   productos.tipo — era "subproducto"|"producto_final"; la distinción ya no
#   existe (todos son Producto) y la columna es NOT NULL, así que dejarla
#   rompería cualquier INSERT nuevo.
COLUMNAS_OBSOLETAS: list[tuple[str, str]] = [("productos", "tipo")]

# Columnas que cambiaron de nombre sin cambiar de contenido: se renombran en
# vez de agregar+perder, para no vaciar lo que el usuario ya clasificó.
#   ingredientes.alergenos → declarables — ahora cubre también colorantes,
#   edulcorantes y polialcoholes (Art. 136/146/151), no solo alérgenos.
COLUMNAS_RENOMBRADAS: list[tuple[str, str, str]] = [
    ("ingredientes", "alergenos", "declarables"),
]


def migrar_columnas_faltantes() -> list[str]:
    """
    Agrega a data/nutricion.db las columnas que el modelo declara y la tabla
    todavía no tiene. create_all() crea tablas nuevas pero nunca altera las
    existentes, así que sin esto una base ya poblada revienta con
    "no such column" al agregar un campo.

    También elimina las columnas de COLUMNAS_OBSOLETAS y renombra las de
    COLUMNAS_RENOMBRADAS (antes de agregar columnas nuevas, para que el
    renombre no quede enmascarado por un ADD COLUMN vacío con el nombre
    nuevo). Una columna NOT NULL sin server_default no se puede agregar en
    SQLite y se omite (requiere migración manual). Retorna la lista de
    cambios, para log.
    """
    agregadas: list[str] = []
    with engine.begin() as con:
        for nombre_tabla, columna in COLUMNAS_OBSOLETAS:
            presentes = {fila[1] for fila in
                         con.exec_driver_sql(f'PRAGMA table_info("{nombre_tabla}")')}
            if columna in presentes:
                con.exec_driver_sql(
                    f'ALTER TABLE "{nombre_tabla}" DROP COLUMN "{columna}"')
                agregadas.append(f"−{nombre_tabla}.{columna}")

        for nombre_tabla, viejo, nuevo in COLUMNAS_RENOMBRADAS:
            presentes = {fila[1] for fila in
                         con.exec_driver_sql(f'PRAGMA table_info("{nombre_tabla}")')}
            if viejo in presentes and nuevo not in presentes:
                con.exec_driver_sql(
                    f'ALTER TABLE "{nombre_tabla}" RENAME COLUMN "{viejo}" TO "{nuevo}"')
                agregadas.append(f"{nombre_tabla}.{viejo}→{nuevo}")

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


def sincronizar_catalogo_micronutrientes() -> list[str]:
    """
    Asegura que data/nutricion.db tenga todas las entradas del catálogo de
    referencia DDR_RSA_CHILE. Antes solo se cargaba al correr
    scripts/seed_welliz_canela.py — si el catálogo gana una entrada nueva
    (ej. Potasio) en una versión posterior, una base ya en uso se quedaba
    sin ella hasta que alguien recordara re-correr el script de demo. Las
    entradas existentes no se tocan; import diferido para evitar el ciclo
    database → micronutriente → database.
    """
    from src.models.micronutriente import DDR_RSA_CHILE

    agregados: list[str] = []
    with engine.begin() as con:
        tabla_existe = con.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='micronutrientes'"
        ).first()
        if not tabla_existe:
            return agregados                  # tabla nueva: la puebla create_all + este mismo paso después
        existentes = {fila[0] for fila in
                      con.exec_driver_sql("SELECT nombre FROM micronutrientes")}
        for datos in DDR_RSA_CHILE:
            if datos["nombre"] in existentes:
                continue
            con.exec_driver_sql(
                "INSERT INTO micronutrientes (nombre, unidad, ddr) VALUES (?, ?, ?)",
                (datos["nombre"], datos["unidad"], datos["ddr"]))
            agregados.append(datos["nombre"])
    return agregados
