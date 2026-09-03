"""
Módulo de normativas de etiquetado nutricional.

Cada normativa es una función que recibe:
  - tabla_100g:   dict nutriente→valor por 100g
  - tabla_porcion: dict nutriente→valor por porción
  - critico:      bool — ¿producto es "crítico"? (afecta sellos)

Retorna una lista de dicts:
  [{"categoria": "Sello"|"Destacador", "nombre": str, "resultado": str}, ...]
"""

from __future__ import annotations


# ══════════════════════════════════════════════════════════════════════════════
# CHILE — Ley 20.606 / RSA Art. 120
# ══════════════════════════════════════════════════════════════════════════════

def _chile_ley_20606(
    tabla_100g: dict[str, float],
    tabla_porcion: dict[str, float],
    critico: bool,
) -> list[dict]:
    """
    Calcula sellos y destacadores según normativa chilena.

    Sellos: aplican por 100 g.
    Destacadores: aplican por porción (o por 50 g si energía/porción < 30 kcal).
    """
    resultados: list[dict] = []

    # ── Abreviaturas ──────────────────────────────────────────────────────────
    d = tabla_100g       # "D" = por 100g
    e = tabla_porcion    # "E" = por porción

    # ══════════════════════════════════════════════════════════════════════════
    # SELLOS (etiquetas de advertencia, por 100g)
    # ══════════════════════════════════════════════════════════════════════════

    # Alto en Calorías
    if not critico:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Calorías",
                           "resultado": "Sin sello"})
    elif d.get("energia_kcal", 0) >= 275:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Calorías",
                           "resultado": "Con Sello"})
    else:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Calorías",
                           "resultado": "Sin Sello"})

    # Alto en Grasas Saturadas
    if not critico:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Grasas Saturadas",
                           "resultado": "Sin sello"})
    elif d.get("grasa_saturada_g", 0) >= 4:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Grasas Saturadas",
                           "resultado": "Con Sello"})
    else:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Grasas Saturadas",
                           "resultado": "Sin Sello"})

    # Alto en Azúcares
    if not critico:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Azúcares",
                           "resultado": "Sin sello"})
    elif d.get("azucares_totales_g", 0) >= 10:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Azúcares",
                           "resultado": "Con Sello"})
    else:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Azúcares",
                           "resultado": "Sin Sello"})

    # Alto en Sodio (NO depende de "Crítico")
    if d.get("sodio_mg", 0) >= 400:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Sodio",
                           "resultado": "Con Sello"})
    else:
        resultados.append({"categoria": "Sello", "nombre": "Alto en Sodio",
                           "resultado": "Sin Sello"})

    # ══════════════════════════════════════════════════════════════════════════
    # DESTACADORES (claims positivos)
    # ══════════════════════════════════════════════════════════════════════════

    # Si energía por porción < 30 kcal → se usan valores "por 50g" (= 100g × 0.5)
    energia_porcion = e.get("energia_kcal", 0)
    bajo_30_kcal = energia_porcion < 30

    # ── Libre / Bajo en Grasa Total ──────────────────────────────────────────
    if bajo_30_kcal:
        grasa_ref = d.get("grasa_total_g", 0) * 0.5     # por 50g
        col_ref   = d.get("colesterol_mg", 0) * 0.5     # por 50g
    else:
        grasa_ref = e.get("grasa_total_g", 0)            # por porción
        col_ref   = e.get("colesterol_mg", 0)            # por porción

    if grasa_ref < 0.5 and col_ref < 0.5:
        res_grasa = "Libre"
    elif grasa_ref <= 3:
        res_grasa = "Bajo"
    else:
        res_grasa = ""
    resultados.append({"categoria": "Destacador", "nombre": "Grasa Total",
                       "resultado": res_grasa})

    # ── Libre / Bajo en Grasa Saturada ───────────────────────────────────────
    if bajo_30_kcal:
        gsat_ref = d.get("grasa_saturada_g", 0) * 0.5
        col_ref2 = d.get("colesterol_mg", 0) * 0.5
    else:
        gsat_ref = e.get("grasa_saturada_g", 0)
        col_ref2 = e.get("colesterol_mg", 0)

    if gsat_ref < 0.5 and col_ref2 < 0.5:
        res_gsat = "Libre"
    elif gsat_ref <= 3:
        res_gsat = "Bajo"
    else:
        res_gsat = ""
    resultados.append({"categoria": "Destacador", "nombre": "Grasa Saturada",
                       "resultado": res_gsat})

    # ── Libre de Ácidos Grasos Trans ─────────────────────────────────────────
    trans_p = e.get("acidos_grasos_trans_g", 0)
    sat_p   = e.get("grasa_saturada_g", 0)
    if trans_p < 0.2 and sat_p < 2:
        res_trans = "Libre"
    else:
        res_trans = ""
    resultados.append({"categoria": "Destacador", "nombre": "Ácidos Grasos Trans",
                       "resultado": res_trans})

    # ── Excelente / Buena Fuente de Fibra Dietética ──────────────────────────
    fibra_p = e.get("fibra_dietetica_g", 0)
    if fibra_p >= 5:
        res_fibra = "Excelente fuente"
    elif fibra_p >= 2.5:
        res_fibra = "Buena fuente"
    else:
        res_fibra = ""
    resultados.append({"categoria": "Destacador", "nombre": "Fibra Dietética",
                       "resultado": res_fibra})

    # ── Prebiótico (fibra soluble) ───────────────────────────────────────────
    fibra_sol_p = e.get("fibra_soluble_g", 0)
    if fibra_sol_p >= 1.5:
        res_prebio = "Prebiótico"
    else:
        res_prebio = ""
    resultados.append({"categoria": "Destacador", "nombre": "Fibra Soluble (Prebiótico)",
                       "resultado": res_prebio})

    # ── Sodio: Libre / Muy bajo / Bajo ───────────────────────────────────────
    sodio_p = e.get("sodio_mg", 0)
    if sodio_p < 5:
        res_sodio = "Libre"
    elif sodio_p <= 35:
        res_sodio = "Muy bajo aporte"
    elif sodio_p <= 140:
        res_sodio = "Bajo"
    else:
        res_sodio = ""
    resultados.append({"categoria": "Destacador", "nombre": "Sodio",
                       "resultado": res_sodio})

    return resultados


# ══════════════════════════════════════════════════════════════════════════════
# Registro de normativas disponibles
# ══════════════════════════════════════════════════════════════════════════════

NORMATIVAS_DISPONIBLES: dict[str, dict] = {
    "Chile — Ley 20.606 / RSA Art. 120": {
        "pais": "Chile",
        "descripcion": (
            "Sellos de advertencia (Alto en calorías/grasas saturadas/azúcares/sodio) "
            "y destacadores (Libre/Bajo en grasa, fibra, prebiótico, sodio). "
            "Referencia: Ley 20.606, RSA Art. 120."
        ),
        "funcion": _chile_ley_20606,
    },
}


def calcular_sellos(
    normativa_nombre: str,
    tabla_100g: dict[str, float],
    tabla_porcion: dict[str, float],
    critico: bool,
) -> list[dict]:
    """Calcula sellos y destacadores para una normativa dada."""
    info = NORMATIVAS_DISPONIBLES.get(normativa_nombre)
    if info is None:
        return []
    return info["funcion"](tabla_100g, tabla_porcion, critico)


def listar_normativas() -> list[str]:
    """Retorna los nombres de todas las normativas registradas."""
    return list(NORMATIVAS_DISPONIBLES.keys())
