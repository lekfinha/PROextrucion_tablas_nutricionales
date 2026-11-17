"""
Check de consolidar_etiquetado() sobre un árbol BOM de 3 niveles con receta
mixta (ingredientes + productos en el mismo nodo) y sobre las leyendas
obligatorias del RSA/Res. 427 (fenilalanina, laxante, cafeína).

Ejecutar:  python -m tests.test_etiquetado
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.ingrediente import Ingrediente
from src.models.producto import Producto, RecetaIngrediente, RecetaProducto
from src.models import micronutriente  # noqa: F401  (registra los mappers)
from src.etiquetado import (consolidar_etiquetado, TIPO_ALERGENO,
                            TIPO_COLORANTE, TIPO_EDULCORANTE, TIPO_POLIALCOHOL,
                            TIPO_ADVERTENCIA, TIPO_TRAZA, LEYENDA_FENILALANINA,
                            LEYENDA_LAXANTE, LEYENDA_CAFEINA)


def _arbol(s: Session) -> Producto:
    """
    Final ─ 50% Extrusión ─ 50% Harina de Trigo
          │                └ 50% Azúcar
          ├ 40% Jarabe    ─ 20% Caseína
          │                └ 80% Azúcar
          └ 10% Amarillo Crepúsculo   ← ingrediente directo en el mismo nodo
    """
    harina = Ingrediente(nombre="Harina de Trigo", fabricante="Molino A",
                         declarables=["trigo"], halal=True, kosher=True,
                         vegetariano=True, vegano=True, apto_celiacos=True)
    caseina = Ingrediente(nombre="Caseína", fabricante="Lácteos B",
                          declarables=["leche"], halal=True, kosher=True,
                          vegetariano=True, vegano=False, apto_celiacos=True,
                          trazas="Puede contener soya.")
    colorante = Ingrediente(nombre="Amarillo Crepúsculo", fabricante="Aditivos D",
                            declarables=["amarillo_ocaso"], halal=True, kosher=True,
                            vegetariano=True, vegano=True, apto_celiacos=True)
    azucar = Ingrediente(nombre="Azúcar", fabricante="Ingenio C",
                         halal=True, kosher=True, vegetariano=True,
                         vegano=True, apto_celiacos=True)
    s.add_all([harina, caseina, azucar, colorante])
    s.flush()

    extrusion = Producto(nombre="Extrusión",
                         trazas="Elaborado en líneas que procesan maní.")
    extrusion.receta_ingredientes = [
        RecetaIngrediente(ingrediente=harina, proporcion=0.5),
        RecetaIngrediente(ingrediente=azucar, proporcion=0.5),
    ]
    jarabe = Producto(nombre="Jarabe")
    jarabe.receta_ingredientes = [
        RecetaIngrediente(ingrediente=caseina, proporcion=0.2),
        RecetaIngrediente(ingrediente=azucar, proporcion=0.8),
    ]
    final = Producto(nombre="Cereal Final")
    s.add_all([extrusion, jarabe, final])
    s.flush()

    # Receta mixta en el nodo raíz: dos productos y un ingrediente suelto
    final.receta_productos = [
        RecetaProducto(hijo=extrusion, proporcion=0.5),
        RecetaProducto(hijo=jarabe, proporcion=0.4),
    ]
    final.receta_ingredientes = [
        RecetaIngrediente(ingrediente=colorante, proporcion=0.1),
    ]
    s.commit()
    return final


def test_consolidar_etiquetado():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as s:
        final = _arbol(s)
        ficha = consolidar_etiquetado(final)

        # Cascada: azúcar 0.5*0.5 + 0.4*0.8, harina 0.5*0.5, caseína 0.4*0.2
        plano = [(l.nombre, round(l.porcentaje, 4)) for l in ficha.ingredientes]
        assert plano == [("Azúcar", 57.0), ("Harina de Trigo", 25.0),
                         ("Amarillo Crepúsculo", 10.0), ("Caseína", 8.0)], plano
        assert round(ficha.total_porcentaje, 6) == 100.0

        # Unión de alérgenos y colorantes, en orden de catálogo (cereales con
        # gluten primero, luego el resto de alérgenos, luego colorantes)
        assert [d.codigo for d in ficha.alergenos_directos] == [
            "trigo", "leche", "amarillo_ocaso"]
        assert ficha.texto_contiene() == "Contiene: Trigo, Leche."
        assert ficha.texto_colorantes() == "Contiene colorante: Amarillo Crepúsculo."

        # String del envase: colorante en negrilla; "Caseína (Leche)" lleva el
        # alérgeno al lado, "Harina de Trigo" no lo repite porque ya lo nombra;
        # cierra con las trazas acumuladas (sin leyendas: no hay edulcorantes
        # ni polialcoholes en este árbol)
        assert ficha.texto_ingredientes() == (
            "Azúcar, Harina de Trigo, **Amarillo Crepúsculo**, Caseína (Leche). "
            "Elaborado en líneas que procesan maní. Puede contener soya."
        ), ficha.texto_ingredientes()

        # Desglose sanitario: solo lo presente, con sus responsables. Las
        # trazas suben desde un nodo intermedio (Extrusión) y desde una hoja.
        assert [(a.nombre, a.tipo, a.responsables) for a in ficha.alertas] == [
            ("Trigo", TIPO_ALERGENO, ("Harina de Trigo",)),
            ("Leche", TIPO_ALERGENO, ("Caseína",)),
            ("Amarillo Crepúsculo", TIPO_COLORANTE, ("Amarillo Crepúsculo",)),
            ("Elaborado en líneas que procesan maní.", TIPO_TRAZA, ("Extrusión",)),
            ("Puede contener soya.", TIPO_TRAZA, ("Caseína",)),
        ], ficha.alertas
        assert ficha.trazas_advertencias == [
            "Elaborado en líneas que procesan maní.", "Puede contener soya."]
        assert ficha.leyendas_obligatorias == []

        # AND con culpables: la caseína rompe vegano, el trigo rompe celíacos
        # (pese a venir con apto_celiacos=True en la ficha del proveedor)
        assert ficha.requerimientos == {
            "halal": [], "kosher": [], "vegetariano": [],
            "vegano": ["Caseína"],
            "apto_celiacos": ["Harina de Trigo"]}, ficha.requerimientos
        assert ficha.cumple("halal") and not ficha.cumple("vegano")

        # Una fila en 0% no arrastra su alérgeno a la etiqueta
        huevo = Ingrediente(nombre="Huevo en Polvo", fabricante="E",
                            declarables=["huevo"])
        s.add(huevo)
        s.flush()
        final.receta_ingredientes.append(
            RecetaIngrediente(ingrediente=huevo, proporcion=0.0))
        s.commit()
        assert "huevo" not in {d.codigo for d in
                               consolidar_etiquetado(final).alergenos_directos}

        # Un producto sin alérgenos ni trazas no declara nada
        limpio = Producto(nombre="Jarabe Simple")
        limpio.receta_ingredientes = [
            RecetaIngrediente(ingrediente=s.query(Ingrediente)
                              .filter_by(nombre="Azúcar").one(), proporcion=1.0)]
        s.add(limpio)
        s.commit()
        assert consolidar_etiquetado(limpio).alertas == []

        # Dos ingredientes con el mismo alérgeno se agrupan en una fila
        suero = Ingrediente(nombre="Suero de leche", fabricante="F",
                            declarables=["leche"])
        s.add(suero)
        s.flush()
        jarabe = s.query(Producto).filter_by(nombre="Jarabe").one()
        jarabe.receta_ingredientes.append(
            RecetaIngrediente(ingrediente=suero, proporcion=0.1))
        s.commit()
        leche = [a for a in consolidar_etiquetado(final).alertas
                 if a.codigo == "leche"][0]
        assert leche.responsables == ("Caseína", "Suero de leche"), leche

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

    print("OK — consolidar_etiquetado (alérgenos/colorantes/trazas)")


def test_leyendas_obligatorias():
    """
    Edulcorantes y polialcoholes (Art. 146/151) y cafeína/taurina: cada uno
    dispara su leyenda exacta, además de su propia fila en el desglose como
    sustancia nombrada. El aspartamo además se bold+mayúscula en la lista.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as s:
        agua = Ingrediente(nombre="Agua", fabricante="A")
        aspartamo = Ingrediente(nombre="Aspartamo", fabricante="B",
                                declarables=["aspartamo"])
        sorbitol = Ingrediente(nombre="Sorbitol", fabricante="C",
                               declarables=["sorbitol"])
        guarana = Ingrediente(nombre="Guaraná", fabricante="D",
                              cafeina_taurina=True)
        s.add_all([agua, aspartamo, sorbitol, guarana])
        s.flush()

        bebida = Producto(nombre="Bebida Energética")
        bebida.receta_ingredientes = [
            RecetaIngrediente(ingrediente=agua, proporcion=0.7),
            RecetaIngrediente(ingrediente=aspartamo, proporcion=0.1),
            RecetaIngrediente(ingrediente=sorbitol, proporcion=0.1),
            RecetaIngrediente(ingrediente=guarana, proporcion=0.1),
        ]
        s.add(bebida)
        s.commit()

        ficha = consolidar_etiquetado(bebida)

        # Fila propia por sustancia (Edulcorante / Polialcohol), más la fila
        # de la leyenda que cada una dispara (Advertencia Obligatoria).
        por_tipo = {(a.nombre, a.tipo) for a in ficha.alertas}
        assert ("Aspartamo", TIPO_EDULCORANTE) in por_tipo
        assert ("Sorbitol", TIPO_POLIALCOHOL) in por_tipo
        assert (LEYENDA_FENILALANINA, TIPO_ADVERTENCIA) in por_tipo
        assert (LEYENDA_LAXANTE, TIPO_ADVERTENCIA) in por_tipo
        assert (LEYENDA_CAFEINA, TIPO_ADVERTENCIA) in por_tipo

        aspartamo_alerta = next(a for a in ficha.alertas if a.nombre == "Aspartamo")
        assert aspartamo_alerta.responsables == ("Aspartamo",)
        cafeina_alerta = next(a for a in ficha.alertas if a.nombre == LEYENDA_CAFEINA)
        assert cafeina_alerta.responsables == ("Guaraná",)

        assert ficha.leyendas_obligatorias == [
            LEYENDA_FENILALANINA, LEYENDA_LAXANTE, LEYENDA_CAFEINA]

        # Negrita + mayúsculas para el edulcorante; el polialcohol no se
        # destaca en la lista (solo dispara la leyenda)
        assert ficha.texto_ingredientes() == (
            "Agua, **ASPARTAMO**, Guaraná, Sorbitol. "
            f"{LEYENDA_FENILALANINA}. {LEYENDA_LAXANTE} {LEYENDA_CAFEINA}"
        ), ficha.texto_ingredientes()

    print("OK — consolidar_etiquetado (leyendas obligatorias)")


if __name__ == "__main__":
    test_consolidar_etiquetado()
    test_leyendas_obligatorias()
