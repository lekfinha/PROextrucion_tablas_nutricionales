"""
Consolidación de etiquetado: aplana el árbol BOM a lo que exige la etiqueta.

Recorre el árbol de un Producto de arriba hacia abajo acumulando el factor de
cascada (producto de las proporciones del camino) y consolida en un solo
objeto las reglas de herencia legal:

  - Ingredientes       → suma      (% acumulado, agrupado por nombre, orden desc)
  - Alérgenos/aditivos → unión  (OR)  — basta un ingrediente para heredarlos
  - Trazas             → unión  (OR)  — suben desde cualquier nodo de la rama
  - Leyendas obligatorias → unión (OR) — se disparan si CUALQUIER hoja las activa
  - Requerimientos     → intersección (AND) — todas las hojas deben cumplirlo

Referencias: Reglamento Sanitario de los Alimentos (D.S. N° 977/1996) y
Resolución Exenta N° 427/2010 del MINSAL —
  - Art. 107 letra h: lista de ingredientes en orden decreciente y declaración
    de alérgenos oficiales.
  - Art. 136: colorantes de rotulación destacada (negrilla).
  - Art. 146: edulcorantes no nutritivos (negrilla) y advertencia de
    fenilcetonúricos cuando hay aspartamo.
  - Art. 151: polialcoholes y advertencia de efecto laxante.

NOTA sobre porcentajes: se usan los pesos "tal como se agregan" a la mezcla,
sin aplicar el factor de concentración por merma de humedad. Es lo que pide
el Art. 107 — la lista declara la fórmula, no el producto deshidratado.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.producto import Producto


TIPO_ALERGENO     = "alergeno"
TIPO_COLORANTE    = "colorante"
TIPO_EDULCORANTE  = "edulcorante"
TIPO_POLIALCOHOL  = "polialcohol"
TIPO_ADVERTENCIA  = "advertencia"
TIPO_TRAZA        = "traza"

# Cómo se nombra cada tipo en el desglose sanitario de la UI.
ETIQUETAS_TIPO: dict[str, str] = {
    TIPO_ALERGENO:    "Alérgeno Directo",
    TIPO_COLORANTE:   "Colorante Destacado",
    TIPO_EDULCORANTE: "Edulcorante No Nutritivo",
    TIPO_POLIALCOHOL: "Polialcohol",
    TIPO_ADVERTENCIA: "Advertencia Obligatoria",
    TIPO_TRAZA:       "Traza / Contaminación",
}

# ──────────────────────────────────────────────────────────────────────────────
# Catálogo oficial RSA/Res. 427 — un solo dict para las 4 categorías que se
# marcan con checkbox en la ficha del ingrediente y se declaran igual en el
# desglose sanitario: código → (nombre impreso, tipo).
#
# El orden de este dict es el orden en que se imprimen. Los cereales con
# gluten se declaran por separado porque la norma exige nombrar el cereal
# específico (Art. 107 letra h, ítem 1).
# ──────────────────────────────────────────────────────────────────────────────

DECLARABLES: dict[str, tuple[str, str]] = {
    # ── A. Alérgenos oficiales (Res. Ex. 427/2010, Art. 107 letra h) ──
    "trigo":                ("Trigo",                          TIPO_ALERGENO),
    "avena":                ("Avena",                          TIPO_ALERGENO),
    "cebada":               ("Cebada",                         TIPO_ALERGENO),
    "centeno":              ("Centeno",                        TIPO_ALERGENO),
    "espelta":              ("Espelta",                        TIPO_ALERGENO),
    "crustaceos":           ("Crustáceos",                     TIPO_ALERGENO),
    "huevo":                ("Huevo",                          TIPO_ALERGENO),
    "pescado":              ("Pescado",                        TIPO_ALERGENO),
    "mani":                 ("Maní",                           TIPO_ALERGENO),
    "soya":                 ("Soya",                           TIPO_ALERGENO),
    "leche":                ("Leche",                          TIPO_ALERGENO),
    "frutos_secos":         ("Frutos Secos",                   TIPO_ALERGENO),
    "sulfitos":             ("Sulfitos",                       TIPO_ALERGENO),

    # ── B. Colorantes de rotulación destacada (Art. 136) ──
    "tartrazina":           ("Tartrazina",                     TIPO_COLORANTE),
    "amarillo_ocaso":       ("Amarillo Crepúsculo",            TIPO_COLORANTE),
    "rojo_allura":          ("Rojo Allura AC",                 TIPO_COLORANTE),

    # ── C. Edulcorantes no nutritivos (Art. 146) ──
    "acesulfamo_k":         ("Acesulfamo de Potasio",          TIPO_EDULCORANTE),
    "aspartamo":            ("Aspartamo",                      TIPO_EDULCORANTE),
    "ciclamato":            ("Ciclamato",                      TIPO_EDULCORANTE),
    "sacarina":             ("Sacarina",                       TIPO_EDULCORANTE),
    "sucralosa":            ("Sucralosa",                      TIPO_EDULCORANTE),
    "alitamo":              ("Alitamo",                        TIPO_EDULCORANTE),
    "taumatina":            ("Taumatina",                      TIPO_EDULCORANTE),
    "esteviol":             ("Glucósidos de Esteviol",         TIPO_EDULCORANTE),
    "neotamo":              ("Neotamo",                        TIPO_EDULCORANTE),
    "aspartamo_acesulfamo": ("Sal de Aspartamo y Acesulfamo",  TIPO_EDULCORANTE),
    "advantamo":            ("Advantamo",                      TIPO_EDULCORANTE),

    # ── D. Polialcoholes / polioles (Art. 151) ──
    "sorbitol":             ("Sorbitol",                       TIPO_POLIALCOHOL),
    "manitol":              ("Manitol",                        TIPO_POLIALCOHOL),
    "isomalt":              ("Isomalt",                        TIPO_POLIALCOHOL),
    "maltitol":             ("Maltitol",                       TIPO_POLIALCOHOL),
    "lactitol":             ("Lactitol",                       TIPO_POLIALCOHOL),
    "xilitol":              ("Xilitol",                        TIPO_POLIALCOHOL),
    "eritritol":            ("Eritritol",                      TIPO_POLIALCOHOL),
    "polidextrosa":         ("Polidextrosa",                   TIPO_POLIALCOHOL),
}

# Código SIN de cada aditivo, solo para mostrarlo junto al nombre en el
# formulario (evita ambigüedad si el usuario conoce el ingrediente por su
# código internacional — "SIN 951" / "E-951" — y no por su nombre comercial).
# Los alérgenos no llevan código SIN: son compuestos, no aditivos.
SIN_CODES: dict[str, str] = {
    "tartrazina": "102", "amarillo_ocaso": "110", "rojo_allura": "129",
    "acesulfamo_k": "950", "aspartamo": "951", "ciclamato": "952",
    "sacarina": "954", "sucralosa": "955", "alitamo": "956",
    "taumatina": "957", "esteviol": "960", "neotamo": "961",
    "aspartamo_acesulfamo": "962", "advantamo": "969",
    "sorbitol": "420", "manitol": "421", "isomalt": "953",
    "maltitol": "965", "lactitol": "966", "xilitol": "967",
    "eritritol": "968", "polidextrosa": "1200",
}

# Códigos que implican gluten: anulan el requerimiento "apto para celíacos"
# (Art. 107 letra h, ítem 1: trigo, avena, cebada, centeno, espelta).
CODIGOS_GLUTEN = {"trigo", "avena", "cebada", "centeno", "espelta"}

# Códigos que disparan la advertencia de fenilcetonuria (Art. 146).
CODIGOS_FENILALANINA = {"aspartamo", "aspartamo_acesulfamo"}

# ── Leyendas obligatorias (texto exacto exigido por la norma) ──
LEYENDA_FENILALANINA = "FENILCETONÚRICOS: CONTIENE FENILALANINA"
LEYENDA_LAXANTE = "Un consumo excesivo puede producir efecto laxante."
LEYENDA_CAFEINA = ("ALTO CONTENIDO DE CAFEÍNA. NO RECOMENDABLE PARA MENORES "
                   "DE 15 AÑOS, EN EMBARAZO NI LACTANCIA.")

# Requerimientos alimentarios (lógica AND sobre las hojas del árbol).
REQUERIMIENTOS: dict[str, str] = {
    "halal":         "Halal",
    "kosher":        "Kosher",
    "vegetariano":   "Vegetariano",
    "vegano":        "Vegano",
    "apto_celiacos": "Apto para celíacos",
}


def _normalizar(texto: str) -> str:
    """minúsculas, sin tildes y con espacios colapsados, para comparar nombres."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto)
                         if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


def _nombra_al_alergeno(nombre_ingrediente: str, nombre_alergeno: str) -> bool:
    """
    ¿El nombre del ingrediente ya menciona el alérgeno? Evita el redundante
    "Huevo (Huevo)" o "Harina de Trigo (Trigo)" y deja "Caseína (Leche)".
    """
    return re.search(rf"\b{re.escape(_normalizar(nombre_alergeno))}\b",
                     _normalizar(nombre_ingrediente)) is not None


@dataclass(frozen=True)
class Alerta:
    """
    Una alerta sanitaria que el producto hereda del árbol, con los nombres de
    los nodos que la provocan. Cubre alérgenos, colorantes, edulcorantes,
    polialcoholes, leyendas obligatorias y trazas porque las seis se leen
    igual en el desglose: qué se declara y por culpa de quién.
    """
    nombre: str                       # "Leche", "Aspartamo", o la frase legal/traza
    tipo: str
    responsables: tuple[str, ...] = ()
    codigo: str = ""                  # vacío en leyendas y trazas: no vienen del catálogo

    @property
    def etiqueta_tipo(self) -> str:
        return ETIQUETAS_TIPO.get(self.tipo, self.tipo)


@dataclass
class LineaIngrediente:
    """Una línea de la lista de ingredientes ya aplanada."""
    nombre: str
    porcentaje: float
    # Códigos declarables que aporta esta línea: permiten destacar el nombre
    # dentro de la propia lista de ingredientes, además del desglose sanitario.
    declarables: list[str] = field(default_factory=list)

    def formateada(self) -> str:
        """
        El nombre tal como va en la lista impresa (Art. 107, 136 y 146):
        - alérgeno que el nombre no menciona → entre paréntesis al lado
        - edulcorante no nutritivo → EN MAYÚSCULAS y **en negrilla**
        - colorante destacado → **en negrilla** (sin forzar mayúsculas)

        "Caseína" + leche        → "Caseína (Leche)"
        "Huevo"   + huevo        → "Huevo"              (no se repite)
        "Amarillo Crepúsculo" + tartrazina → "**Amarillo Crepúsculo**"
        "Aspartamo" + aspartamo  → "**ASPARTAMO**"
        """
        texto = self.nombre
        faltantes = [DECLARABLES[c][0] for c in self.declarables
                     if DECLARABLES.get(c, ("", ""))[1] == TIPO_ALERGENO
                     and not _nombra_al_alergeno(self.nombre, DECLARABLES[c][0])]
        if faltantes:
            texto += f" ({', '.join(faltantes)})"

        tipos = {DECLARABLES[c][1] for c in self.declarables if c in DECLARABLES}
        if TIPO_EDULCORANTE in tipos:
            texto = texto.upper()
        if tipos & {TIPO_COLORANTE, TIPO_EDULCORANTE}:
            texto = f"**{texto}**"
        return texto


@dataclass
class FichaEtiquetado:
    """
    Resultado consolidado del árbol. Las alertas conviven en una sola lista
    pero la vista las separa por tipo: alérgenos/colorantes/edulcorantes van
    bajo "Contiene:" o en negrilla dentro de la lista, las leyendas
    obligatorias y las trazas cierran el párrafo en tipografía normal.
    """
    producto: str
    ingredientes: list[LineaIngrediente]
    total_porcentaje: float
    # Alérgenos, colorantes, edulcorantes, polialcoholes, leyendas y trazas
    # presentes, en orden de catálogo. Solo aparece lo que el árbol realmente
    # activó: una alerta sin responsables no existe.
    alertas: list[Alerta]
    # requisito → ingredientes hoja que lo incumplen (vacío = se cumple).
    # Guardar los culpables y no un bool permite explicar en la UI *por qué*
    # un producto no es vegano, que es la pregunta que siempre sigue.
    requerimientos: dict[str, list[str]]
    n_hojas: int = 0

    def cumple(self, campo: str) -> bool:
        """Un producto sin hojas no cumple nada: no hay nada que verificar."""
        return self.n_hojas > 0 and not self.requerimientos.get(campo)

    @property
    def alergenos(self) -> list[Alerta]:
        return [a for a in self.alertas if a.tipo == TIPO_ALERGENO]

    @property
    def colorantes(self) -> list[Alerta]:
        return [a for a in self.alertas if a.tipo == TIPO_COLORANTE]

    @property
    def alergenos_directos(self) -> list[Alerta]:
        """Lo que va bajo «Contiene:»/«Contiene colorante:»."""
        return [a for a in self.alertas if a.tipo in (TIPO_ALERGENO, TIPO_COLORANTE)]

    @property
    def leyendas_obligatorias(self) -> list[str]:
        """Frases exactas exigidas por la norma (fenilalanina, laxante, cafeína)."""
        return [a.nombre for a in self.alertas if a.tipo == TIPO_ADVERTENCIA]

    @property
    def trazas_advertencias(self) -> list[str]:
        return [a.nombre for a in self.alertas if a.tipo == TIPO_TRAZA]

    def texto_ingredientes(self) -> str:
        """
        Texto completo listo para el envase: la lista de ingredientes de
        mayor a menor (colorantes/edulcorantes en negrilla, alérgenos entre
        paréntesis), cerrada por las leyendas obligatorias y las trazas.

        Ej: "Harina de garbanzos, Azúcar, **Amarillo Crepúsculo**,
             Caseína (Leche). Un consumo excesivo puede producir efecto
             laxante. Puede contener trazas de soya."
        """
        base = ", ".join(l.formateada() for l in self.ingredientes)
        cierre = [f if f.endswith((".", "!", "?")) else f + "."
                 for f in (*self.leyendas_obligatorias, *self.trazas_advertencias)]
        if not cierre:
            return base
        return f"{base}. {' '.join(cierre)}" if base else " ".join(cierre)

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
    residuo de edición, no un ingrediente del producto, y arrastraría alertas
    inexistentes a la etiqueta.

    Lanza ValueError si la receta tiene un ciclo (un producto que se contiene
    a sí mismo, directa o indirectamente).
    """
    lineas: dict[str, LineaIngrediente] = {}
    # código del catálogo → {nombre del ingrediente que lo aporta: None}
    responsables: dict[str, dict[str, None]] = {}
    # ingredientes con cafeína/taurina añadida: dispara su propia leyenda
    cafeina: dict[str, None] = {}
    # frase normalizada → {"texto": frase original, "origen": {nodo: None}}
    trazas: dict[str, dict] = {}
    # requisito → {nombre del ingrediente que lo incumple: None} (set ordenado)
    incumplen: dict[str, dict[str, None]] = {r: {} for r in REQUERIMIENTOS}
    hojas = 0

    def _anotar_traza(texto: str | None, origen: str) -> None:
        """La misma advertencia desde dos ramas es una sola fila, dos orígenes."""
        if texto and texto.strip():
            reg = trazas.setdefault(_normalizar(texto),
                                    {"texto": texto.strip(), "origen": {}})
            reg["origen"][origen] = None

    def _visitar(nodo: "Producto", factor: float, ruta: tuple[int, ...]) -> None:
        nonlocal hojas
        if nodo.id is not None and nodo.id in ruta:
            raise ValueError(
                f"Receta cíclica: '{nodo.nombre}' se contiene a sí mismo "
                f"(ruta de productos: {' → '.join(map(str, ruta + (nodo.id,)))}).")
        ruta = ruta + (nodo.id,)

        # Las trazas de un nodo intermedio son de proceso/planta y suben igual;
        # el responsable es el producto mismo, no una materia prima.
        _anotar_traza(getattr(nodo, "trazas", None), nodo.nombre)

        for rel in nodo.receta_ingredientes:
            if rel.proporcion <= 0:
                continue
            ing = rel.ingrediente
            hojas += 1

            clave = " ".join(ing.nombre.split()).lower()
            linea = lineas.setdefault(
                clave, LineaIngrediente(nombre=ing.nombre.strip(), porcentaje=0.0))
            linea.porcentaje += factor * rel.proporcion * 100.0

            codigos_ing = ing.declarables or []
            for codigo in codigos_ing:
                responsables.setdefault(codigo, {})[linea.nombre] = None
                if codigo not in linea.declarables:
                    linea.declarables.append(codigo)

            if getattr(ing, "cafeina_taurina", False):
                cafeina[linea.nombre] = None

            _anotar_traza(ing.trazas, linea.nombre)

            for campo in incumplen:
                # Un cereal con gluten invalida el "apto para celíacos" aunque
                # la ficha de la materia prima venga marcada por error.
                falla = not getattr(ing, campo, False) or (
                    campo == "apto_celiacos"
                    and bool(set(codigos_ing) & CODIGOS_GLUTEN))
                if falla:
                    incumplen[campo][linea.nombre] = None

        for comp in nodo.receta_productos:
            if comp.proporcion <= 0:
                continue
            _visitar(comp.hijo, factor * comp.proporcion, ruta)

    _visitar(producto, 1.0, ())

    ingredientes = sorted(lineas.values(), key=lambda l: (-l.porcentaje, l.nombre))

    # Los culpables/responsables se listan en el mismo orden que la lista
    # impresa: primero el que más pesa en la receta.
    posicion = {l.nombre: i for i, l in enumerate(ingredientes)}
    por_peso = lambda nombres: tuple(sorted(nombres, key=lambda n: posicion.get(n, 0)))
    requerimientos = {campo: list(por_peso(nombres))
                      for campo, nombres in incumplen.items()}

    # Declaraciones directas del catálogo (alérgenos, colorantes, edulcorantes,
    # polialcoholes): orden del catálogo; un código desconocido (dato antiguo
    # o norma nueva) nunca se descarta, se declara igual como alérgeno al final.
    alertas = [Alerta(DECLARABLES[c][0], DECLARABLES[c][1],
                      por_peso(responsables[c]), c)
               for c in DECLARABLES if c in responsables]
    alertas += [Alerta(c.replace("_", " ").capitalize(), TIPO_ALERGENO,
                       por_peso(responsables[c]), c)
                for c in sorted(responsables.keys() - DECLARABLES.keys())]

    # Leyendas obligatorias: una sola fila por leyenda, aunque varios
    # ingredientes distintos la disparen (Art. 146 y 151).
    fenil = {}
    for c in CODIGOS_FENILALANINA:
        fenil.update(responsables.get(c, {}))
    if fenil:
        alertas.append(Alerta(LEYENDA_FENILALANINA, TIPO_ADVERTENCIA, por_peso(fenil)))

    poli = {}
    for c, (_, tipo) in DECLARABLES.items():
        if tipo == TIPO_POLIALCOHOL:
            poli.update(responsables.get(c, {}))
    if poli:
        alertas.append(Alerta(LEYENDA_LAXANTE, TIPO_ADVERTENCIA, por_peso(poli)))

    if cafeina:
        alertas.append(Alerta(LEYENDA_CAFEINA, TIPO_ADVERTENCIA, por_peso(cafeina)))

    # Trazas al final: son advertencias de proceso, no declaraciones del
    # producto en sí.
    alertas += [Alerta(reg["texto"], TIPO_TRAZA, tuple(reg["origen"]))
                for reg in trazas.values()]

    return FichaEtiquetado(
        producto=producto.nombre,
        ingredientes=ingredientes,
        total_porcentaje=sum(l.porcentaje for l in ingredientes),
        alertas=alertas,
        requerimientos=requerimientos,
        n_hojas=hojas,
    )
