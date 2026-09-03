"""
Script de seed: inserta todos los ingredientes y subproductos del Excel
"Cereal Welliz Canela v1 p4 - 26-08-26 - Estuche Normal.xlsx"

Ejecutar desde la raíz del proyecto:
    /home/miauuu/py12/bin/python scripts/seed_welliz_canela.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from src.database import engine, Base
from src.models.ingrediente import Ingrediente
from src.models.subproducto import (
    SubProducto, SubProductoIngrediente, CostoOperativo
)
from src.models.producto_final import (
    ProductoFinal, ProductoFinalSubProducto, CostoOperativoPT
)

# Asegurar que todas las tablas existan
Base.metadata.create_all(engine)

# ══════════════════════════════════════════════════════════════════════════════
# INGREDIENTES
# Fuente: tabla nutricional por 100g de cada ingrediente (columnas del Excel)
# Formato: dict con todos los campos del modelo Ingrediente
# ══════════════════════════════════════════════════════════════════════════════

INGREDIENTES = [
    # ── Extrusión ─────────────────────────────────────────────────────────────
    {
        "nombre":                 "Harina de Arroz",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               550.0,
        "energia_kcal":           368.0,
        "proteinas_g":            7.2,
        "grasa_total_g":          0.5,
        "grasa_saturada_g":       0.0,
        "grasa_monoinsaturada_g": 0.0,
        "grasa_poliinsaturada_g": 0.0,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   77.8,
        "azucares_totales_g":     2.2,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      0.5,
        "fibra_soluble_g":        0.0,
        "fibra_insoluble_g":      0.5,
        "sodio_mg":               1.6,
        "humedad_porcentaje":     0.07,   # fracción
    },
    {
        "nombre":                 "Harina de Maíz",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               470.0,
        "energia_kcal":           365.0,
        "proteinas_g":            7.13,
        "grasa_total_g":          0.66,
        "grasa_saturada_g":       0.18,
        "grasa_monoinsaturada_g": 0.206,
        "grasa_poliinsaturada_g": 0.177,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   79.95,
        "azucares_totales_g":     0.12,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      1.3,
        "fibra_soluble_g":        0.0,
        "fibra_insoluble_g":      1.3,
        "sodio_mg":               5.0,
        "humedad_porcentaje":     0.1162,
    },
    {
        "nombre":                 "Harina de Zapallo",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               5500.0,
        "energia_kcal":           340.0,
        "proteinas_g":            6.5,
        "grasa_total_g":          4.0,
        "grasa_saturada_g":       0.0,
        "grasa_monoinsaturada_g": 0.0,
        "grasa_poliinsaturada_g": 0.0,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   69.6,
        "azucares_totales_g":     40.0,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      15.0,
        "fibra_soluble_g":        0.0,
        "fibra_insoluble_g":      13.4,
        "sodio_mg":               4.1,
        "humedad_porcentaje":     0.04,
    },
    {
        "nombre":                 "Carbonato de Calcio",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               600.0,
        "energia_kcal":           0.0,
        "proteinas_g":            0.0,
        "grasa_total_g":          0.0,
        "grasa_saturada_g":       0.0,
        "grasa_monoinsaturada_g": 0.0,
        "grasa_poliinsaturada_g": 0.0,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   0.0,
        "azucares_totales_g":     0.0,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      0.0,
        "fibra_soluble_g":        0.0,
        "fibra_insoluble_g":      0.0,
        "sodio_mg":               0.0,
        "humedad_porcentaje":     0.002,
    },
    {
        "nombre":                 "Alulosa",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               4162.5,
        "energia_kcal":           172.0,
        "proteinas_g":            0.0,
        "grasa_total_g":          0.0,
        "grasa_saturada_g":       0.0,
        "grasa_monoinsaturada_g": 0.0,
        "grasa_poliinsaturada_g": 0.0,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   99.5,
        "azucares_totales_g":     0.0,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      0.0,
        "fibra_soluble_g":        0.0,
        "fibra_insoluble_g":      0.0,
        "sodio_mg":               0.0,
        "humedad_porcentaje":     0.01,
    },
    {
        "nombre":                 "Harina de Garbanzos",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               824.7422680412371,
        "energia_kcal":           387.0,
        "proteinas_g":            22.4,
        "grasa_total_g":          6.7,
        "grasa_saturada_g":       0.7,
        "grasa_monoinsaturada_g": 1.5,
        "grasa_poliinsaturada_g": 3.0,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   47.0,
        "azucares_totales_g":     10.9,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      10.8,
        "fibra_soluble_g":        0.0,
        "fibra_insoluble_g":      10.8,
        "sodio_mg":               64.0,
        "humedad_porcentaje":     0.14,
    },
    # ── Jarabe ────────────────────────────────────────────────────────────────
    {
        "nombre":                 "Oligofructosa",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               3424.0,
        "energia_kcal":           170.0,
        "proteinas_g":            0.0,
        "grasa_total_g":          0.0,
        "grasa_saturada_g":       0.0,
        "grasa_monoinsaturada_g": 0.0,
        "grasa_poliinsaturada_g": 0.0,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   10.0,
        "azucares_totales_g":     10.0,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      65.0,
        "fibra_soluble_g":        65.0,
        "fibra_insoluble_g":      0.0,
        "sodio_mg":               0.0,
        "humedad_porcentaje":     0.25,
    },
    {
        "nombre":                 "Harina de Plátano",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               7723.75,
        "energia_kcal":           364.0,
        "proteinas_g":            3.7,
        "grasa_total_g":          0.3,
        "grasa_saturada_g":       0.0,
        "grasa_monoinsaturada_g": 0.0,
        "grasa_poliinsaturada_g": 0.0,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   83.7,
        "azucares_totales_g":     65.6,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      5.8,
        "fibra_soluble_g":        0.0,
        "fibra_insoluble_g":      5.8,
        "sodio_mg":               4.0,
        "humedad_porcentaje":     0.04,
    },
    {
        "nombre":                 "Agua",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               10.0,
        "energia_kcal":           0.0,
        "proteinas_g":            0.0,
        "grasa_total_g":          0.0,
        "grasa_saturada_g":       0.0,
        "grasa_monoinsaturada_g": 0.0,
        "grasa_poliinsaturada_g": 0.0,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   0.0,
        "azucares_totales_g":     0.0,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      0.0,
        "fibra_soluble_g":        0.0,
        "fibra_insoluble_g":      0.0,
        "sodio_mg":               2.0,
        "humedad_porcentaje":     1.0,   # 100% agua
    },
    {
        "nombre":                 "Canela en polvo",
        "fabricante":             "Pro Extrusion",
        "critico":                False,
        "costo_kg":               16956.0,
        "energia_kcal":           247.0,
        "proteinas_g":            3.99,
        "grasa_total_g":          1.24,
        "grasa_saturada_g":       0.345,
        "grasa_monoinsaturada_g": 0.246,
        "grasa_poliinsaturada_g": 0.068,
        "acidos_grasos_trans_g":  0.0,
        "colesterol_mg":          0.0,
        "carbohidratos_disp_g":   80.59,
        "azucares_totales_g":     2.17,
        "sorbitol_g":             0.0,
        "maltitol_g":             0.0,
        "fibra_dietetica_g":      53.1,
        "fibra_soluble_g":        0.0,
        "fibra_insoluble_g":      53.1,
        "sodio_mg":               10.0,
        "humedad_porcentaje":     0.1058,
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# SUBPRODUCTOS
# ══════════════════════════════════════════════════════════════════════════════

# Recetas: { nombre_ingrediente: % }
SUBPRODUCTOS = [
    {
        "nombre":        "Extrusión",
        "descripcion":   "Cereal extruido base — Welliz Canela",
        "humedad_final": 0.03,   # 3% — fracción
        "critico":       False,
        "receta": {
            # nombre_ingrediente → % (se convierte a fracción al guardar)
            "Harina de Arroz":     35.75,
            "Harina de Maíz":      35.75,
            "Harina de Zapallo":    3.00,
            "Carbonato de Calcio":  0.50,
            "Alulosa":              5.00,
            "Harina de Garbanzos": 20.00,
        },
        "costos": [
            # (nombre, tipo, valor_ui)
            # tipo "porcentual" → valor en % (ej: 2.8% = 0.028 fracción)
            # tipo "fijo"       → valor en $/kg
            ("Partida/Parada",          "porcentual",  2.8047343916531107),
            ("Extrusión de Harinas",    "porcentual",  6.627650000000002),
            ("Tamizado",                "porcentual",  1.0),
            ("Energia",                 "fijo",        200.0),
            ("Envase Interno",          "fijo",         14.0),
        ],
    },
    {
        "nombre":        "Jarabe",
        "descripcion":   "Jarabe de oligofructosa con canela — Welliz Canela",
        "humedad_final": 0.279395,  # = humedad ponderada ingredientes → merma=0, factor=1
        "critico":       False,
        "receta": {
            "Oligofructosa":    67.5,
            "Harina de Plátano": 20.0,
            "Agua":             10.0,
            "Canela en polvo":   2.5,
        },
        "costos": [
            ("Dosificado",      "porcentual",  1.0),
            ("Concentración",   "porcentual",  0.0),   # 0% en el Excel
            ("Energia",         "fijo",        50.0),
            ("Envase Interno",  "fijo",         0.0),
        ],
    },
    {
        "nombre":        "Sazonador",
        "descripcion":   "Sazonador — Welliz Canela (sin ingredientes activos en esta versión)",
        "humedad_final": 0.0,
        "critico":       False,
        "receta": {},      # vacío en el Excel
        "costos": [],
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# PT GRANEL
# ══════════════════════════════════════════════════════════════════════════════

PT_GRANEL = {
    "nombre":        "Cereal Welliz Canela — PT Granel",
    "descripcion":   "Producto terminado granel v1 p4 — Estuche Normal",
    "porcion_g":     25.0,
    "gramaje_g":     200.0,
    "humedad_final": 0.04,   # 4% — fracción
    "critico":       False,
    "receta": {
        # subproducto → %
        "Extrusión": 70.0,
        "Jarabe":    30.0,
    },
    "costos": [],   # PT Granel no tiene costos adicionales en el Excel visible
}


# ══════════════════════════════════════════════════════════════════════════════
# EJECUCIÓN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    with Session(engine) as s:
        # ── 1. Insertar ingredientes ──────────────────────────────────────────
        ing_map: dict[str, int] = {}   # nombre → id
        for datos in INGREDIENTES:
            # Verificar si ya existe
            existente = (s.query(Ingrediente)
                          .filter_by(nombre=datos["nombre"], fabricante=datos["fabricante"])
                          .first())
            if existente:
                print(f"  [SKIP] Ingrediente ya existe: {datos['nombre']}")
                ing_map[datos["nombre"]] = existente.id
                continue
            ing = Ingrediente(**datos)
            s.add(ing)
            s.flush()
            ing_map[datos["nombre"]] = ing.id
            print(f"  [OK]   Ingrediente insertado: {datos['nombre']}")

        # ── 2. Insertar SubProductos ──────────────────────────────────────────
        sp_map: dict[str, int] = {}    # nombre → id
        for sp_datos in SUBPRODUCTOS:
            if not sp_datos["receta"]:
                print(f"  [SKIP] SubProducto sin receta: {sp_datos['nombre']}")
                continue

            existente = (s.query(SubProducto)
                          .filter_by(nombre=sp_datos["nombre"])
                          .first())
            if existente:
                print(f"  [SKIP] SubProducto ya existe: {sp_datos['nombre']}")
                sp_map[sp_datos["nombre"]] = existente.id
                continue

            sp = SubProducto(
                nombre=sp_datos["nombre"],
                descripcion=sp_datos["descripcion"],
                humedad_final=sp_datos["humedad_final"],
                critico=sp_datos["critico"],
            )
            s.add(sp)
            s.flush()
            sp_map[sp_datos["nombre"]] = sp.id

            # Receta de ingredientes
            total_pct = sum(sp_datos["receta"].values())
            assert abs(total_pct - 100.0) < 0.01, (
                f"Receta de {sp_datos['nombre']} no suma 100%: {total_pct}")

            for nombre_ing, pct in sp_datos["receta"].items():
                ing_id = ing_map.get(nombre_ing)
                assert ing_id, f"Ingrediente no encontrado: {nombre_ing}"
                s.add(SubProductoIngrediente(
                    subproducto_id=sp.id,
                    ingrediente_id=ing_id,
                    proporcion=pct / 100.0,
                ))

            # Costos operativos
            for orden, (nombre_c, tipo, valor_ui) in enumerate(sp_datos["costos"], 1):
                valor_db = valor_ui / 100.0 if tipo == "porcentual" else valor_ui
                s.add(CostoOperativo(
                    subproducto_id=sp.id,
                    nombre=nombre_c,
                    tipo=tipo,
                    valor=valor_db,
                    orden=orden,
                ))

            print(f"  [OK]   SubProducto insertado: {sp_datos['nombre']} "
                  f"({len(sp_datos['receta'])} ingredientes, {len(sp_datos['costos'])} costos)")

        # ── 3. Insertar PT Granel ─────────────────────────────────────────────
        existente_pf = (s.query(ProductoFinal)
                         .filter_by(nombre=PT_GRANEL["nombre"])
                         .first())
        if existente_pf:
            print(f"  [SKIP] ProductoFinal ya existe: {PT_GRANEL['nombre']}")
        else:
            pf = ProductoFinal(
                nombre=PT_GRANEL["nombre"],
                descripcion=PT_GRANEL["descripcion"],
                porcion_g=PT_GRANEL["porcion_g"],
                gramaje_g=PT_GRANEL["gramaje_g"],
                humedad_final=PT_GRANEL["humedad_final"],
                critico=PT_GRANEL["critico"],
            )
            s.add(pf)
            s.flush()

            total_pct_pf = sum(PT_GRANEL["receta"].values())
            assert abs(total_pct_pf - 100.0) < 0.01

            for nombre_sp, pct in PT_GRANEL["receta"].items():
                sp_id = sp_map.get(nombre_sp)
                assert sp_id, f"SubProducto no encontrado para PT: {nombre_sp}"
                s.add(ProductoFinalSubProducto(
                    productofinal_id=pf.id,
                    subproducto_id=sp_id,
                    proporcion=pct / 100.0,
                ))

            print(f"  [OK]   ProductoFinal insertado: {PT_GRANEL['nombre']}")

        s.commit()

    # ── 4. Verificar cálculo nutricional ──────────────────────────────────────
    print("\n=== VERIFICACIÓN — Tabla nutricional Extrusión (100g) ===")
    from sqlalchemy.orm import selectinload

    with Session(engine) as s:
        sp = (s.query(SubProducto)
               .filter_by(nombre="Extrusión")
               .options(
                   selectinload(SubProducto.receta_ingredientes)
                       .selectinload(SubProductoIngrediente.ingrediente),
                   selectinload(SubProducto.costos_operativos),
               )
               .first())

        tabla = sp.tabla_nutricional()
        merma = sp.merma() * 100
        factor = sp.factor_concentracion()
        costo  = sp.costo_final_kg()

        print(f"  Merma:  {merma:.6f}%  (esperado: 6.627650%)")
        print(f"  Factor: {factor:.6f}  (esperado: 1.071073...)")
        print(f"  Costo:  ${costo:,.4f} /kg  (esperado: $1,222.0847)")
        print(f"  Energía: {tabla['energia_kcal']:.4f} kcal  (esperado: 383.6762)")
        print(f"  Proteínas: {tabla['proteinas_g']:.4f} g  (esperado: 10.4934)")
        print(f"  Sodio: {tabla['sodio_mg']:.4f} mg  (esperado: 16.3673)")
        print()
        print("  Verificación Jarabe:")
        sp_j = (s.query(SubProducto)
                 .filter_by(nombre="Jarabe")
                 .options(
                     selectinload(SubProducto.receta_ingredientes)
                         .selectinload(SubProductoIngrediente.ingrediente),
                     selectinload(SubProducto.costos_operativos),
                 )
                 .first())
        tj = sp_j.tabla_nutricional()
        cj = sp_j.costo_final_kg()
        print(f"  Energía Jarabe: {tj['energia_kcal']:.4f} kcal  (esperado: 193.7250)")
        print(f"  Fibra Jarabe:   {tj['fibra_dietetica_g']:.4f} g   (esperado: 46.3625)")
        print(f"  Costo Jarabe:   ${cj:,.4f} /kg  (esperado: $4,374.0909)")


if __name__ == "__main__":
    print("Insertando datos del Excel — Cereal Welliz Canela...")
    main()
    print("\n✅ Seed completado exitosamente.")
