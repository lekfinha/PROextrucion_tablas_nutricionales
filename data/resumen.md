# PRO Extrusión - Sistema de Gestión Nutricional

Este documento sirve como contexto consolidado del estado actual del proyecto, su arquitectura, y los requerimientos de negocio, ideal para retomar el desarrollo o pasar el contexto a otro entorno/agente.

## 1. Objetivo del Programa
El sistema automatiza el cálculo de tablas nutricionales, costos y evaluación de normativas (Ley de Etiquetado de Chile / RSA) para la empresa de alimentos "PRO Extrusión". Reemplaza un sistema complejo de planillas Excel. 

Su característica central es manejar el proceso de **extrusión**, donde la mezcla de ingredientes sufre una alta pérdida de agua (merma por evaporación). Esta pérdida concentra los nutrientes y afecta los costos finales.

## 2. Tecnologías y Arquitectura
*   **Lenguaje:** Python 3.12+ (Uso estricto de virtual environment en `/home/miauuu/py12/bin/python`).
*   **Base de Datos:** SQLite (`data/nutricion.db`), interactuando mediante SQLAlchemy 2.0 (Patrón ORM moderno con `Mapped` y `mapped_column`).
*   **Interfaz Gráfica:** `tkinter` (UI nativa con `ttk`).
*   **Patrón de Diseño Estructural:** BOM (Bill of Materials) unificado. Permite árboles de recetas recursivos donde un "Producto" puede estar compuesto por "Ingredientes" puros y por otros "Productos" (sub-recetas).

## 3. Estructura de Archivos

```text
/home/miauuu/Codigo/PROextrucion_tablas_nutricionales/
├── main.py                     # Punto de entrada de la aplicación. Inicializa DB y UI.
├── data/                       
│   ├── nutricion.db            # Base de datos SQLite local.
│   ├── resumen.md              # Este archivo de contexto.
│   └── fichas_tecnicas/        # Directorio para almacenar PDFs de fichas técnicas.
├── scripts/
│   └── seed_welliz_canela.py   # Script de poblamiento de DB. Contiene datos reales basados en el Excel original (Productos: Extrusión, Jarabe, Cereal Welliz).
└── src/
    ├── database.py             # Configuración de SQLAlchemy (Engine, Session, Base).
    ├── normativas.py           # Lógica del RSA chileno: cálculo de sellos (Alto en Azúcares, Sodio, etc.) según límites de Art 120.
    ├── models/
    │   ├── ingrediente.py      # Modelo `Ingrediente`. Materia prima pura, nodo hoja del BOM. Trazabilidad y macronutrientes.
    │   ├── producto.py         # Modelo `Producto` (unifica SubProducto y Producto Terminado). Contiene clases M2M `RecetaIngrediente`, `RecetaProducto` y `CostoOperativo`.
    │   └── micronutriente.py   # Catálogo `Micronutriente` (Valores DDR Codex/FDA) y tabla asociativa `ProductoMicronutriente`.
    ├── ui/
    │   └── app.py              # Interfaz completa. Menús de gestión, formularios CRUD, y Toplevels para renderizar las tablas nutricionales.
    └── utils/
        └── redondeo.py         # Reglas matemáticas estrictas de redondeo según el Reglamento Sanitario (Minsal).
```

## 4. Cómo Funciona (Lógica de Negocio)

### A. Matemática de Extrusión y Merma (`producto.py`)
1.  **Suma Ponderada:** Se calcula la suma de nutrientes y humedad basada en la % de participación de cada componente en la receta.
2.  **Merma:** `Humedad_ponderada_inicial - Humedad_final_objetivo`.
3.  **Factor de Concentración:** `1.0 / (1.0 - Merma)`. Todo nutriente (proteínas, grasas, etc.) se multiplica por este factor porque el producto pierde agua pero retiene la masa sólida.

### B. Cálculo de Costos
Se calculan secuencialmente. 
1.  Costo base (suma ponderada de las materias primas).
2.  Cascada de `CostoOperativo` (ej. Mano de obra, Energía, Empaque). Pueden ser porcentuales (`costo / (1 - valor)`) o fijos (`costo + valor`).

### C. Trazabilidad y Caducidad Mixta
La caducidad de un alimento extruido depende del proceso (humedad final, horneado), no de la materia prima más perecedera. 
*   **Oficial:** `Producto.meses_caducidad` asignada manualmente según estudios de vida útil.
*   **Sugerida (BOM):** `caducidad_minima_componentes()` rastrea la caducidad más corta en el árbol de ingredientes como alerta preventiva.
*   **Gestión de Proveedores:** Rastreo de fechas de vencimiento de las Fichas Técnicas (PDFs) asociadas a cada ingrediente.

### D. Normativa Chilena y Descriptores
*   **Sellos:** Evalúa límites de Calorías, Sodio, Azúcares y Grasas Saturadas para determinar si aplica sello "Alto en...".
*   **Descriptores de Micronutrientes (Art 120 RSA):** Determina frases legales como "Excelente fuente de...", "Buena fuente de..." o "Fortificado en..." basándose en los % de DDR (Dosis Diaria de Referencia del Codex Alimentarius).

## 5. Tareas Pendientes / Siguientes Pasos

1.  **Micronutrientes en Ingredientes Individuales:** 
    *   *Estado:* Actualmente los micronutrientes solo se pueden asociar a un `Producto` final/subproducto.
    *   *Requerimiento:* Crear una tabla `IngredienteMicronutriente` para que las materias primas (ej. Harina) puedan declarar sus micronutrientes nativos.
    *   *Lógica:* Modificar la matemática del árbol BOM en `Producto` para que recolecte y escale automáticamente los micronutrientes provenientes de sus ingredientes subyacentes, aplicando las proporciones y la merma. Actualizar UI para gestionarlo.
2.  **Manejo de Repositorio (Git):**
    *   *Estado:* El código local tiene inicializado un repositorio Git con commits locales hasta el refactor actual.
    *   *Requerimiento:* El usuario debe crear el repositorio en GitHub (o similar), generar su Personal Access Token (PAT), configurar el origin y hacer push de la rama `main`.
3.  **Exportación a Excel / PDF (Opcional a futuro):**
    *   Poder exportar la Ficha Técnica final completa generada por la UI a un archivo compartible.
