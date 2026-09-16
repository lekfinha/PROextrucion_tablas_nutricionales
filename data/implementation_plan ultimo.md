# Refactorización Arquitectónica — Modelo Unificado + RSA Chile

## Contexto

Se requieren 6 modificaciones: unificar el BOM, agregar campos de trazabilidad, corregir lógica de sellos, implementar redondeo Minsal, ajustar la estructura nutricional, y agregar micronutrientes dinámicos.

## User Review Required

> [!IMPORTANT]
> **Pérdida de datos:** La base de datos se borrará y recreará (SQLite + SQLAlchemy `create_all` no altera tablas existentes). Los datos se re-insertan con el seed script actualizado.

> [!WARNING]
> **Campo `critico`:** Actualmente usamos `critico` como un simple boolean. El RSA Art 120 bis en realidad define como "alimentos críticos" aquellos **a los que se les ha añadido** azúcares, sodio o grasas saturadas. Tu Excel usa "Critico: No" de forma global. ¿Lo mantenemos como boolean manual, o prefieres que se detecte automáticamente? → **Propongo mantenerlo como boolean manual** por ahora, ya que la empresa sabe si le añadió ingredientes críticos.

## Open Questions

> [!IMPORTANT]
> **Micronutrientes DDR:** ¿Tienes una lista específica de micronutrientes y sus valores DDR que usan en Pro Extrusion? Si no, pre-cargo la lista estándar del RSA chileno (Vitamina A, C, D, E, K, B1-B12, Ácido fólico, Calcio, Hierro, Zinc, Fósforo, Magnesio, Potasio, etc.). Puedes agregar/editar después desde la app.

> [!NOTE]
> **Sazonador vacío:** El subproducto "Sazonador" del Excel actual no tiene ingredientes (todo 0). No se creará como SubProducto en el seed. Cuando tenga ingredientes reales, se puede crear desde la UI.

---

## Proposed Changes

### 1. Modelo Unificado `Producto` (Refactorización BOM)

**Problema actual:** `SubProducto` y `ProductoFinal` duplican toda la lógica (merma, concentración, cascada de costos). Un producto terminado no puede ser ingrediente de otro.

**Solución:** Un solo modelo `Producto` con relación self-referential many-to-many.

#### [DELETE] [subproducto.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/src/models/subproducto.py)
#### [DELETE] [producto_final.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/src/models/producto_final.py)

#### [NEW] [producto.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/src/models/producto.py)

Modelo unificado con:

```python
class Producto(Base):
    """Nodo del árbol BOM. Puede ser SubProducto, PT, o cualquier nivel."""
    __tablename__ = "productos"

    id: Mapped[int]
    nombre: Mapped[str]           # unique
    descripcion: Mapped[str|None]
    critico: Mapped[bool]         # ¿aplican sellos?

    # Tipo de producto para la UI (no cambia la lógica matemática)
    tipo: Mapped[str]             # "subproducto" | "producto_final"

    # Datos de etiquetado (solo relevante para tipo="producto_final")
    porcion_g: Mapped[float]      # default 25.0
    gramaje_g: Mapped[float]      # default 200.0

    # Humedad y merma
    humedad_final: Mapped[float]  # fracción (0.0-1.0)

    # Trazabilidad (punto 2)
    fecha_creacion: Mapped[datetime]   # default=now
    meses_caducidad: Mapped[int|None]  # para calcular fecha vencimiento

    # Relaciones
    receta_ingredientes → RecetaIngrediente (M2M con Ingrediente)
    receta_productos    → RecetaProducto    (M2M self-referential)
    costos_operativos   → CostoOperativo    (1:N, cascada secuencial)

class RecetaIngrediente(Base):
    """Qué fracción de un Ingrediente usa este Producto."""
    __tablename__ = "receta_ingrediente"
    producto_id: FK → productos.id
    ingrediente_id: FK → ingredientes.id
    proporcion: float  # 0.0-1.0

class RecetaProducto(Base):
    """Composición: Producto padre contiene otro Producto hijo."""
    __tablename__ = "receta_producto"
    padre_id: FK → productos.id
    hijo_id: FK → productos.id
    proporcion: float  # 0.0-1.0

class CostoOperativo(Base):
    """Paso en la cascada de costos (una sola tabla para todos los productos)."""
    __tablename__ = "costos_operativos"
    id, producto_id, nombre, tipo, valor, orden
```

**La lógica matemática es idéntica** a la actual (merma, factor, concentración, cascada de costos). La diferencia es que ahora un `Producto(tipo="producto_final")` puede ser usado como hijo en otro `RecetaProducto` — ej. "Barra de Cereal" bañada en chocolate.

---

### 2. Campos de Trazabilidad

#### [MODIFY] [ingrediente.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/src/models/ingrediente.py)

Agregar:
```python
fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=func.now)
fecha_vencimiento_ficha: Mapped[date|None] = mapped_column(Date, nullable=True)
ruta_pdf_ficha: Mapped[str|None] = mapped_column(String, nullable=True)
```

#### [NEW] `data/fichas_tecnicas/` — carpeta para PDFs de fichas técnicas de proveedores

En el modelo `Producto`:
- `fecha_creacion` (DateTime, default now) — ya incluido arriba
- `meses_caducidad` (Integer, nullable) — ya incluido arriba

---

### 3. Lógica de Sellos — RSA Art 120 bis

#### [MODIFY] [normativas.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/src/normativas.py)

La lógica actual es **correcta** respecto a los umbrales:
- Calorías ≥ 275 kcal/100g
- Grasas saturadas ≥ 4 g/100g
- Azúcares totales ≥ 10 g/100g
- Sodio ≥ 400 mg/100g

**Corrección necesaria:** El RSA establece que el sello de **sodio también depende de si se añadió** sodio (Art 120 bis). Actualmente nuestro código exime sodio del check `critico`, cuando debería seguir la misma lógica.

Cambio: `calcular_sellos()` ahora recibirá `critico` como dict con flags individuales:
```python
# Antes: critico: bool
# Después: acepta ambos formatos para compatibilidad
critico: bool | dict  
# dict forma: {"azucares_añadidos": True, "sodio_añadido": True, "grasas_sat_añadidas": True}
# Si bool: True = todos añadidos, False = ninguno añadido
```

Esto permite que en el futuro el operador indique exactamente qué se añadió. Por ahora usamos el boolean simple como antes.

---

### 4. Redondeo Minsal — RSA Art 115

#### [NEW] [redondeo.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/src/utils/redondeo.py)

```python
def redondear_minsal(valor: float) -> str:
    """Aplica regla de redondeo RSA Art 115."""
    from decimal import Decimal, ROUND_HALF_UP
    if valor >= 100:
        return str(int(Decimal(str(valor)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)))
    elif valor >= 10:
        return str(Decimal(str(valor)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
    else:  # valor < 10 (incluye < 1)
        return str(Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
```

Se aplica en la **visualización** (Toplevel de tabla nutricional), no en el cálculo interno.

---

### 5. Estructura Nutricional — Colesterol y Humedad

#### Cambio en `ETIQUETAS_NUTRIENTES` y en la visualización:

- **Colesterol (mg)** se agrupa dentro de la sección de grasas (indentado bajo grasa total), justo después de ácidos grasos trans.
- **Humedad (%)** se muestra **separada** en la parte superior de la tabla (cabecera informativa), fuera de la tabla de macronutrientes.

Esto se implementa en:
1. Constante `ETIQUETAS_NUTRIENTES` en `producto.py` — reordenar colesterol
2. `_mostrar_toplevel_nutricional()` en `app.py` — mostrar humedad arriba como dato de proceso

#### Nuevo orden de la tabla:

```
┌ Información de proceso ─────────────────────────┐
│ Humedad: 3.00%  |  Merma: 6.63%  |  Factor: ×1.07 │
└──────────────────────────────────────────────────┘

Nutriente                    | Por 100g | Por 25g
─────────────────────────────┼──────────┼────────
Energía (kcal)               |          |
Proteínas (g)                |          |
Grasa Total (g)              |          |
    Grasa Saturada (g)       |          |
    Grasa Monoinsaturada (g) |          |
    Grasa Poliinsaturada (g) |          |
    Ácidos Grasos Trans (g)  |          |
    Colesterol (mg)          |          |   ← MOVIDO aquí
H. de Carbono Disp. (g)     |          |
    Azúcares Totales (g)     |          |
    Sorbitol (g)             |          |
    Maltitol (g)             |          |
Fibra Dietética (g)          |          |
    Fibra Soluble (g)        |          |
    Fibra Insoluble (g)      |          |
Sodio (mg)                   |          |
```

---

### 6. Micronutrientes Dinámicos — RSA Art 118

#### [NEW] [micronutriente.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/src/models/micronutriente.py)

```python
class Micronutriente(Base):
    """Catálogo de vitaminas y minerales con su DDR."""
    __tablename__ = "micronutrientes"
    id: int
    nombre: str                    # "Vitamina A", "Calcio", etc.
    unidad: str                    # "mcg", "mg", "UI"
    ddr: float                     # Dosis Diaria de Referencia

class ProductoMicronutriente(Base):
    """Micronutrientes específicos de un Producto."""
    __tablename__ = "producto_micronutriente"
    producto_id: FK → productos.id
    micronutriente_id: FK → micronutrientes.id
    cantidad_100g: float           # valor por 100g
    destacado_en_envase: bool      # "Fortificado con X"
```

**Lógica de filtrado (RSA Art 118):** Un micronutriente se incluye en la tabla nutricional impresa **solo si:**
1. Su valor por porción ≥ 5% de su DDR, **O**
2. `destacado_en_envase == True`

Esto se implementa en el método `tabla_nutricional_formateada()` del modelo `Producto`.

**Pre-carga del catálogo RSA Chile** (en el seed):
| Micronutriente | DDR | Unidad |
|---|---|---|
| Vitamina A | 600 | mcg |
| Vitamina C | 45 | mg |
| Vitamina D | 5 | mcg |
| Vitamina E | 10 | mg |
| Vitamina B1 (Tiamina) | 1.2 | mg |
| Vitamina B2 (Riboflavina) | 1.3 | mg |
| Vitamina B6 | 1.3 | mg |
| Vitamina B12 | 2.4 | mcg |
| Niacina | 16 | mg |
| Ácido fólico | 400 | mcg |
| Calcio | 1000 | mg |
| Hierro | 14 | mg |
| Zinc | 11 | mg |
| Fósforo | 700 | mg |
| Magnesio | 310 | mg |
| Potasio | 3500 | mg |

---

### Cambios en la UI

#### [MODIFY] [app.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/src/ui/app.py)

Cambios principales:
1. **Menú:** Reemplazar "Gestionar SubProductos" + "Gestionar Producto Final" por un solo "Gestionar Productos" con filtros de tipo
2. **Formulario Producto:** unificado — si `tipo="producto_final"` muestra campos porción/gramaje; si `tipo="subproducto"` los oculta. La composición permite agregar tanto Ingredientes como otros Productos.
3. **Formulario Ingrediente:** agregar campos de trazabilidad (fecha vencimiento ficha, botón para seleccionar PDF)
4. **Tabla nutricional (Toplevel):**
   - Humedad separada arriba como dato de proceso
   - Colesterol agrupado bajo grasas
   - Valores formateados con `redondear_minsal()`
   - Sección de micronutrientes (solo los que superan 5% DDR o están destacados)
5. **Nuevo CRUD de micronutrientes** dentro del formulario de Producto (tab/sección para agregar vitaminas/minerales)

### Otros archivos

#### [MODIFY] [main.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/main.py)
Actualizar imports al nuevo modelo unificado.

#### [MODIFY] [seed_welliz_canela.py](file:///home/miauuu/Codigo/PROextrucion_tablas_nutricionales/scripts/seed_welliz_canela.py)
Adaptar al modelo unificado `Producto` y pre-cargar catálogo de micronutrientes.

---

## Verification Plan

### Automated Tests
```bash
# Verificar sintaxis
/home/miauuu/py12/bin/python -m py_compile src/models/producto.py
/home/miauuu/py12/bin/python -m py_compile src/models/ingrediente.py
/home/miauuu/py12/bin/python -m py_compile src/models/micronutriente.py
/home/miauuu/py12/bin/python -m py_compile src/utils/redondeo.py
/home/miauuu/py12/bin/python -m py_compile src/normativas.py
/home/miauuu/py12/bin/python -m py_compile src/ui/app.py

# Recrear BD y ejecutar seed con verificación
rm data/nutricion.db
/home/miauuu/py12/bin/python scripts/seed_welliz_canela.py

# Test redondeo Minsal
/home/miauuu/py12/bin/python -c "
from src.utils.redondeo import redondear_minsal
assert redondear_minsal(383.676) == '384'        # >= 100 → entero
assert redondear_minsal(10.493) == '10.5'         # 10-100 → 1 decimal
assert redondear_minsal(2.007) == '2.01'          # 1-10 → 2 decimales
assert redondear_minsal(0.218) == '0.22'          # < 1 → 2 decimales
print('✅ Redondeo Minsal OK')
"

# Verificar que Extrusión sigue dando los mismos números
# (regresión contra Excel)
```

### Manual Verification
- Probar la app completa con `main.py`
- Crear un Producto "Barra de Cereal bañada" que contenga "PT Granel" como componente → verificar que la composición recursiva funciona
- Verificar que los micronutrientes aparecen/se ocultan correctamente según el umbral 5% DDR
