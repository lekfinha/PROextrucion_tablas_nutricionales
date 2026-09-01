# Pro Extrusion - Gestor Nutricional

Sistema MVP para la automatización de generación de tablas nutricionales, costeo y optimización de recetas para la empresa Pro Extrusion.

## 🚀 Arquitectura y Tecnologías
- **Lenguaje:** Python 3.12+
- **Base de Datos:** SQLite (`data/nutricion.db`) gestionado con **SQLAlchemy 2.0** (ORM)
- **Interfaz Gráfica:** Tkinter (MVP actual)
- **Estructura:** Patrón "src layout"

### Estructura de Carpetas
- `data/`: Almacena la base de datos local y hojas de cálculo (ignorados en git).
- `src/models/`: Contiene la lógica de negocio y esquemas de base de datos (`Ingrediente`, `SubProducto`, `ProductoFinal`).
- `src/ui/`: Vistas de la aplicación gráfica.
- `main.py`: Punto de entrada de la aplicación.

## ⚙️ Instalación (Entorno de Desarrollo)

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
