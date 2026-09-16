@echo off
echo ==========================================
echo   Compilador Pro Extrusion - Windows
echo ==========================================
echo.
echo Instalando dependencias de runtime...
pip install -r requirements-build.txt
pip install pyinstaller
echo.
echo Compilando ejecutable...
pyinstaller --noconfirm --onefile --windowed ^
  --name "ProExtrusion_Gestor" ^
  --hidden-import sqlalchemy.dialects.sqlite ^
  --exclude-module pandas ^
  --exclude-module scipy ^
  --exclude-module streamlit ^
  --exclude-module numpy ^
  --exclude-module matplotlib ^
  --exclude-module openpyxl ^
  main.py
echo.
echo ==========================================
echo COMPILACION TERMINADA
echo El ejecutable esta en la carpeta "dist\"
echo La base de datos se creara en "dist\data\nutricion.db"
echo ==========================================
pause
