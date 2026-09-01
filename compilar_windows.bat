@echo off
echo ==========================================
echo   Compilador Pro Extrusion - Windows
echo ==========================================
echo.
echo Instalando dependencias...
pip install -r requirements.txt
pip install pyinstaller
echo.
echo Compilando ejecutable...
pyinstaller --noconfirm --onefile --windowed --name "ProExtrusion_Gestor" main.py
echo.
echo ==========================================
echo COMPILACION TERMINADA
echo El ejecutable esta en la carpeta "dist\"
echo ==========================================
pause
