"""
Check de consolidar_etiquetado() sobre un árbol BOM de 3 niveles.

Ejecutar:  python -m tests.test_etiquetado
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.ingrediente import Ingrediente
from src.models.producto import Producto, RecetaIngrediente, RecetaProducto
from src.models import micronutriente  # noqa: F401  (registra los mappers)
from src.etiquetado import consolidar_etiquetado


def _arbol(s: Session) -> Producto:
    """
    Final ─ 60% Extrusión ─ 50% Harina de Trigo
          │                └ 50% Azúcar
          └ 40% Jarabe    ─ 20% Leche en Polvo
                           └ 80% Azúcar
    """
    harina = Ingrediente(nombre="Harina de Trigo", fabricante="Molino A",
                         alergenos=["trigo"], halal=True, kosher=True,
                         vegetariano=True, vegano=True, apto_celiacos=True)
    leche = Ingrediente(nombre="Leche en Polvo", fabricante="Lácteos B",
                        alergenos=["leche"], halal=True, kosher=True,
                        vegetariano=True, vegano=False, apto_celiacos=True,
                        trazas="Puede contener soya.")
    azucar = Ingrediente(nombre="Azúcar", fabricante="Ingenio C",
                         halal=True, kosher=True, vegetariano=True,
                         vegano=True, apto_celiacos=True)
    s.add_all([harina, leche, azucar])
    s.flush()

    extrusion = Producto(nombre="Extrusión", tipo="subproducto",
                         trazas="Elaborado en líneas que procesan maní.")
    extrusion.receta_ingredientes = [
        RecetaIngrediente(ingrediente=harina, proporcion=0.5),
        RecetaIngrediente(ingrediente=azucar, proporcion=0.5),
    ]
    jarabe = Producto(nombre="Jarabe", tipo="subproducto")
    jarabe.receta_ingredientes = [
        RecetaIngrediente(ingrediente=leche, proporcion=0.2),
        RecetaIngrediente(ingrediente=azucar, proporcion=0.8),
    ]
    final = Producto(nombre="Cereal Final", tipo="producto_final")
    s.add_all([extrusion, jarabe, final])
    s.flush()

    final.receta_productos = [
        RecetaProducto(hijo=extrusion, proporcion=0.6),
        RecetaProducto(hijo=jarabe, proporcion=0.4),
    ]
    s.commit()
    return final


def test_consolidar_etiquetado():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as s:
        final = _arbol(s)
        ficha = consolidar_etiquetado(final)

        # Cascada: azúcar 0.6*0.5 + 0.4*0.8, harina 0.6*0.5, leche 0.4*0.2
        plano = [(l.nombre, round(l.porcentaje, 4)) for l in ficha.ingredientes]
        assert plano == [("Azúcar", 62.0), ("Harina de Trigo", 30.0),
                         ("Leche en Polvo", 8.0)], plano
        assert round(ficha.total_porcentaje, 6) == 100.0

        # Unión de alérgenos, en orden de catálogo
        assert [d.codigo for d in ficha.alergenos_directos] == ["leche", "trigo"]
        assert ficha.texto_contiene() == "Contiene: Leche, Trigo (gluten)."
        assert ficha.colorantes == []

        # Las trazas suben desde un nodo intermedio y desde una hoja
        assert sorted(ficha.trazas_advertencias) == [
            "Elaborado en líneas que procesan maní.", "Puede contener soya."]

        # AND: la leche rompe vegano; el trigo rompe celíacos pese al True
        assert ficha.requerimientos == {
            "halal": True, "kosher": True, "vegetariano": True,
            "vegano": False, "apto_celiacos": False}, ficha.requerimientos

        # Una fila en 0% no arrastra su alérgeno a la etiqueta
        huevo = Ingrediente(nombre="Huevo en Polvo", fabricante="D",
                            alergenos=["huevo"])
        s.add(huevo)
        s.flush()
        final.receta_ingredientes.append(
            RecetaIngrediente(ingrediente=huevo, proporcion=0.0))
        s.commit()
        assert "huevo" not in {d.codigo for d in
                               consolidar_etiquetado(final).alergenos_directos}

        # Receta cíclica: error claro en vez de RecursionError
        final.receta_productos.append(
            RecetaProducto(hijo=final, proporcion=0.1))
        s.commit()
        try:
            consolidar_etiquetado(final)
        except ValueError as exc:
            assert "cíclica" in str(exc), exc
        else:
            raise AssertionError("no detectó el ciclo")

    print("OK — consolidar_etiquetado")


if __name__ == "__main__":
    test_consolidar_etiquetado()
