"""
Consolidación de etiquetado: aplana el árbol BOM a lo que exige la etiqueta.

Recorre el árbol de un Producto de arriba hacia abajo acumulando el factor de
cascada (producto de las proporciones del camino) y consolida en un solo
objeto las tres reglas de herencia legal:

  - Ingredientes  → suma      (% acumulado, agrupado por nombre, orden desc)
  - Alérgenos     → unión  (OR)  — basta un ingrediente para heredarlos
  - Trazas        → unión  (OR)  — suben desde cualquier nodo de la rama
  - Requerimientos→ intersección (AND) — todas las hojas deben cumplirlo

Referencias: RSA Art. 107 (lista de ingredientes en orden decreciente de la
proporción usada en la fabricación) y Art. 107 bis / Ley 20.606 (declaración
de alérgenos y colorantes de rotulación destacada).

NOTA sobre porcentajes: se usan los pesos "tal como se agregan" a la mezcla,
sin aplicar el factor de concentración por merma de humedad. Es lo que pide
el Art. 107 — la lista declara la fórmula, no el producto deshidratado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.producto import Producto


TIPO_ALERGENO  = "alergeno"
TIPO_COLORANTE = "colorante"

# ──────────────────────────────────────────────────────────────────────────────
# Catálogo de declaraciones destacadas (negrilla + cuerpo mayor en la etiqueta)
#
# El orden de este dict es el orden en que se imprimen. Los cereales con gluten
# se declaran por separado porque la norma exige nombrar el cereal específico.
# ──────────────────────────────────────────────────────────────────────────────

DECLARABLES: dict[str, tuple[str, str]] = {
    # código            nombre impreso en la etiqueta       tipo
    "leche":           ("Leche",                            TIPO_ALERGENO),
    "huevo":           ("Huevo",                            TIPO_ALERGENO),
    "trigo":           ("Trigo (gluten)",                   TIPO_ALERGENO),
    "centeno":         ("Centeno (gluten)",                 TIPO_ALERGENO),
    "cebada":          ("Cebada (gluten)",                  TIPO_ALERGENO),
    "avena":           ("Avena (gluten)",                   TIPO_ALERGENO),
    "nueces":          ("Nueces y otros frutos secos",      TIPO_ALERGENO),
    "tartrazina":      ("Tartrazina",                       TIPO_COLORANTE),
    "amarillo_ocaso":  ("Amarillo ocaso FCF",               TIPO_COLORANTE),
    "rojo_allura":     ("Rojo allura AC",                   TIPO_COLORANTE),
}

# Códigos que implican gluten: anulan el requerimiento "apto para celíacos".
CODIGOS_GLUTEN = {"trigo", "centeno", "cebada", "avena"}

# Requerimientos alimentarios (lógica AND sobre las hojas del árbol).
REQUERIMIENTOS: dict[str, str] = {
    "halal":         "Halal",
    "kosher":        "Kosher",
    "vegetariano":   "Vegetariano",
    "vegano":        "Vegano",
    "apto_celiacos": "Apto para celíacos",
}


@dataclass(frozen=True)
class Declaracion:
    """Un alérgeno o colorante que el producto hereda de alguna hoja."""
    codigo: str
    nombre: str
    tipo: str          # TIPO_ALERGENO | TIPO_COLORANTE


@dataclass
class LineaIngrediente:
    """Una línea de la lista de ingredientes ya aplanada."""
    nombre: str
    porcentaje: float
    # Códigos declarables que aporta esta línea: permiten destacar el alérgeno
    # dentro de la propia lista de ingredientes, además de la viñeta "Contiene".
    alergenos: list[str] = field(default_factory=list)


@dataclass
class FichaEtiquetado:
    """
    Resultado consolidado del árbol. Las dos listas de declaraciones están
    separadas a propósito: `alergenos_directos` exige negrilla y cuerpo mayor,
    `trazas_advertencias` son frases de contaminación cruzada que van agrupadas
    al final del párrafo y en tipografía normal.
    """
    producto: str
    ingredientes: list[LineaIngrediente]
    total_porcentaje: float
    alergenos_directos: list[Declaracion]
    trazas_advertencias: list[str]
    requerimientos: dict[str, bool]

    @property
    def alergenos(self) -> list[Declaracion]:
        return [d for d in self.alergenos_directos if d.tipo == TIPO_ALERGENO]

    @property
    def colorantes(self) -> list[Declaracion]:
        return [d for d in self.alergenos_directos if d.tipo == TIPO_COLORANTE]

    def texto_contiene(self) -> str:
        """Viñeta «Contiene: …» (va en negrilla y cuerpo mayor)."""
        nombres = [d.nombre for d in self.alergenos]
        return f"Contiene: {', '.join(nombres)}." if nombres else ""

    def texto_colorantes(self) -> str:
        """Los colorantes destacados se declaran en su propia frase."""
        nombres = [d.nombre for d in self.colorantes]
        if not nombres:
            return ""
        etiqueta = "colorante" if len(nombres) == 1 else "colorantes"
        return f"Contiene {etiqueta}: {', '.join(nombres)}."

    def texto_trazas(self) -> str:
        """Advertencias de contaminación cruzada, en un solo párrafo."""
        return " ".join(self.trazas_advertencias)


def consolidar_etiquetado(producto: "Producto") -> FichaEtiquetado:
    """
    Aplana el árbol BOM de `producto` y consolida su información de etiquetado.

    Los componentes con proporción <= 0 se ignoran: una fila en cero es un
    residuo de edición, no un ingrediente del producto, y arrastraría alérgenos
    inexistentes a la etiqueta.

    Lanza ValueError si la receta tiene un ciclo (un producto que se contiene
    a sí mismo, directa o indirectamente).
    """
    lineas: dict[str, LineaIngrediente] = {}
    codigos: set[str] = set()
    trazas: dict[str, str] = {}          # texto normalizado → texto original
    requerimientos = dict.fromkeys(REQUERIMIENTOS, True)
    hojas = 0

    def _anotar_traza(texto: str | None) -> None:
        if texto and texto.strip():
            trazas.setdefault(" ".join(texto.split()).lower(), texto.strip())

    def _visitar(nodo: "Producto", factor: float, ruta: tuple[int, ...]) -> None:
        nonlocal hojas
        if nodo.id is not None and nodo.id in ruta:
            raise ValueError(
                f"Receta cíclica: '{nodo.nombre}' se contiene a sí mismo "
                f"(ruta de productos: {' → '.join(map(str, ruta + (nodo.id,)))}).")
        ruta = ruta + (nodo.id,)

        # Las trazas de un nodo intermedio son de proceso/planta y suben igual.
        _anotar_traza(getattr(nodo, "trazas", None))

        for rel in nodo.receta_ingredientes:
            if rel.proporcion <= 0:
                continue
            ing = rel.ingrediente
            hojas += 1

            clave = " ".join(ing.nombre.split()).lower()
            linea = lineas.setdefault(
                clave, LineaIngrediente(nombre=ing.nombre.strip(), porcentaje=0.0))
            linea.porcentaje += factor * rel.proporcion * 100.0

            for codigo in (ing.alergenos or []):
                codigos.add(codigo)
                if codigo not in linea.alergenos:
                    linea.alergenos.append(codigo)

            _anotar_traza(ing.trazas)

            for campo in requerimientos:
                requerimientos[campo] &= bool(getattr(ing, campo, False))

        for comp in nodo.receta_productos:
            if comp.proporcion <= 0:
                continue
            _visitar(comp.hijo, factor * comp.proporcion, ruta)

    _visitar(producto, 1.0, ())

    # Un producto sin hojas no cumple nada: all() sobre vacío daría True y
    # terminaría declarando "vegano" una receta sin ingredientes.
    if hojas == 0:
        requerimientos = dict.fromkeys(REQUERIMIENTOS, False)

    # Un cereal con gluten en la fórmula invalida el "apto para celíacos"
    # aunque la ficha de alguna materia prima venga marcada por error.
    if codigos & CODIGOS_GLUTEN:
        requerimientos["apto_celiacos"] = False

    # Orden del catálogo; un código desconocido (dato antiguo o norma nueva)
    # nunca se descarta: se muestra tal cual al final.
    conocidos = [Declaracion(c, *DECLARABLES[c]) for c in DECLARABLES if c in codigos]
    otros = [Declaracion(c, c.replace("_", " ").capitalize(), TIPO_ALERGENO)
             for c in sorted(codigos - DECLARABLES.keys())]

    ingredientes = sorted(lineas.values(), key=lambda l: (-l.porcentaje, l.nombre))

    return FichaEtiquetado(
        producto=producto.nombre,
        ingredientes=ingredientes,
        total_porcentaje=sum(l.porcentaje for l in ingredientes),
        alergenos_directos=conocidos + otros,
        trazas_advertencias=list(trazas.values()),
        requerimientos=requerimientos,
    )
