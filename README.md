# Pro Extrusion — Gestor Nutricional

Sistema de escritorio para armar recetas (BOM), calcular su tabla nutricional, costeo y cumplimiento normativo chileno de etiquetado — sellos, alérgenos, aditivos y requerimientos alimentarios — sin depender de una planilla Excel propensa a errores manuales.

## 🧩 Features principales

### Árbol de recetas (BOM) sin niveles fijos
Un **Producto** puede estar compuesto por Ingredientes puros y/o por otros Productos, mezclados libremente y con la profundidad que se necesite (ingrediente → sub-receta → sub-receta → producto final). No existe distinción entre "subproducto" y "producto terminado": cualquier nodo puede tener su propia tabla nutricional y, al mismo tiempo, ser el componente de otro nodo más arriba en el árbol (ej. una barra de cereal vendible sola que también es la base de una barra con cobertura). Un flag de **clasificación comercial** (`es_vendible`) solo separa visualmente "Productos Vendibles" de "Preparaciones / Uso Interno" en el explorador — no afecta el cálculo.

### Cálculo nutricional en cascada
Al ver la tabla nutricional de cualquier nodo, el sistema recorre su árbol completo y:
- Suma ponderada de macronutrientes y micronutrientes (vitaminas/minerales) según la proporción de cada componente.
- Aplica el **factor de concentración** por merma de humedad (lo que se evapora en el proceso concentra el resto de los nutrientes).
- Todo se recalcula al vuelo — no hay valores cacheados: si se edita un ingrediente compartido por diez recetas, las diez reflejan el cambio la próxima vez que se abren.

### Cumplimiento RSA (D.S. 977/1996) y Res. Ex. 427/2010 MINSAL
- **Sellos y destacadores** (Ley 20.606): Alto en calorías/grasas saturadas/azúcares/sodio, más destacadores Libre/Bajo en grasa, fibra, sodio.
- **Descriptores nutricionales** (Art. 120): "Excelente/Buena fuente de…", "Fortificado en…", según % DDR por porción.
- **Catálogo sanitario completo** por ingrediente: alérgenos oficiales (gluten por cereal, crustáceos, huevo, pescado, maní, soya, leche, frutos secos, sulfitos), colorantes de rotulación destacada, edulcorantes no nutritivos y polialcoholes — cada uno con su código SIN.
- **Leyendas obligatorias automáticas**: aspartamo/su sal disparan "FENILCETONÚRICOS: CONTIENE FENILALANINA", cualquier polialcohol dispara la advertencia de efecto laxante, cafeína/taurina añadida dispara la advertencia para menores y embarazo.
- **Requerimientos alimentarios** (Vegano, Vegetariano, Kosher, Halal, Apto para celíacos) calculados por intersección: el producto final solo hereda el requerimiento si el 100% de sus materias primas lo cumplen — y el sistema indica exactamente qué ingrediente lo rompe.

### Etiqueta lista para imprimir
Genera automáticamente la lista de ingredientes en orden decreciente de proporción, con el formato exacto que exige la norma: colorantes y edulcorantes en **negrita** (edulcorantes además en MAYÚSCULAS), alérgenos entre paréntesis cuando el nombre del ingrediente no los menciona ya (ej. `Caseína (Leche)`, pero `Huevo` sin repetir), y el párrafo cerrado con las leyendas obligatorias y las trazas de contaminación cruzada acumuladas desde cualquier nivel del árbol.

### Desglose sanitario y de requerimientos
Antes de imprimir, un desglose desplegable muestra —solo lo que el árbol realmente activó— cada alérgeno/colorante/edulcorante/polialcohol/leyenda/traza junto con los ingredientes responsables, y una tabla de cada requerimiento alimentario con su estado (✅/❌) y la lista de culpables si no se cumple.

### Caducidad en cascada
La vida útil de un producto es el mínimo entre las de sus componentes directos, propagado recursivamente hacia arriba, con un desglose navegable para bajar nivel por nivel y ver qué materia prima es la que acorta la fecha. Admite sobrescritura manual cuando el proceso mismo (no las materias primas) define la vida útil real.

### Costeo en cascada
Costo base ponderado por receta + una secuencia de pasos operativos (mermas porcentuales, costos fijos por kg) aplicados en orden, para llegar al costo final por kg, por porción y por unidad de empaque.

### Explorador en árbol
Pantalla de inicio con un árbol tipo catálogo (Ingredientes / Productos Vendibles / Preparaciones de Uso Interno / Normativas), buscador en tiempo real que expande automáticamente las ramas con coincidencias, y vistas de detalle de solo lectura para cada ingrediente o producto con accesos directos a Editar y Ver Tabla Nutricional.

### Ficha de ingrediente en 3 pestañas
*General y Macronutrientes* · *Micronutrientes* (vitaminas y minerales con su % DDR) · *Alérgenos, Aditivos y Requerimientos* — separadas para no perder de vista la clasificación sanitaria en medio de una ficha técnica larga, con el estado conservado al cambiar de pestaña.

## 🚀 Arquitectura y Tecnologías
- **Lenguaje:** Python 3.12+
- **Base de datos:** SQLite (`data/nutricion.db`) vía **SQLAlchemy 2.0** (ORM). Las migraciones de esquema (columnas nuevas, renombradas u obsoletas, catálogo de micronutrientes) se aplican solas al iniciar la app — no hace falta borrar la base para actualizar.
- **Interfaz gráfica:** Tkinter
- **Estructura:** patrón "src layout"

### Estructura de carpetas
- `data/`: base de datos local y hojas de cálculo de referencia (ignorados en git).
- `src/models/`: esquemas de base de datos — `Ingrediente` (hoja del árbol), `Producto` (nodo BOM self-referential), `Micronutriente`.
- `src/etiquetado.py`: aplanamiento del árbol BOM a lo que exige la etiqueta — lista de ingredientes, alérgenos/aditivos/leyendas, requerimientos.
- `src/normativas.py`: sellos y destacadores por país/normativa (hoy: Chile Ley 20.606).
- `src/utils/`: utilidades transversales (redondeo normativo Minsal).
- `src/ui/`: interfaz gráfica (explorador, formularios, vistas de detalle, tabla nutricional).
- `src/database.py`: conexión y migraciones automáticas del esquema.
- `main.py`: punto de entrada.

## ⚙️ Instalación (entorno de desarrollo)

1. Crear un entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Linux/Mac
   # venv\Scripts\activate   # En Windows
   ```
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Ejecutar la aplicación:
   ```bash
   python main.py
   ```

## 📦 Compilar a Ejecutable (.exe) para Windows

Para generar un archivo ejecutable que un usuario pueda abrir en Windows sin tener Python instalado:

**Opción A: Vía GitHub Actions (Recomendado)**
Al hacer `push` a la rama `main` en GitHub, se ejecutará automáticamente un flujo que compilará el archivo `.exe`. Podrás descargarlo desde la pestaña "Actions" en tu repositorio.

**Opción B: Compilación Local en Windows**
Si tienes acceso a un PC con Windows y Python instalado, simplemente haz doble clic en el archivo `compilar_windows.bat` o ejecuta:
```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "ProExtrusion_Gestor" main.py
```
El ejecutable aparecerá dentro de la carpeta `dist/`.
