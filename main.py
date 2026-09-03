from src.database import engine, Base

# Importar TODOS los modelos para que Base.metadata los registre
# y create_all() cree sus tablas en data/nutricion.db
from src.models.ingrediente import Ingrediente           # noqa: F401
from src.models.subproducto import (                     # noqa: F401
    SubProducto,
    SubProductoIngrediente,
    SubProductoComponente,
    CostoOperativo,
)
from src.models.producto_final import (                  # noqa: F401
    ProductoFinal,
    ProductoFinalSubProducto,
    CostoOperativoPT,
)
from src.ui.app import AppNutricion


def inicializar_sistema():
    # Crea todas las tablas que no existen aún en data/nutricion.db
    Base.metadata.create_all(engine)

    # Iniciar la interfaz gráfica
    app = AppNutricion()
    app.mainloop()


if __name__ == "__main__":
    inicializar_sistema()