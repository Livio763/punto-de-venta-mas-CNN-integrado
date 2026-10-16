@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
echo Descarga del dataset RF100 soda-bottles para Punto Verde Store
echo.
echo Necesitas una clave de Roboflow para la descarga automatica.
echo Alternativa: descarga ZIP desde Universe y ejecuta:
echo   python scripts\descargar_dataset_productos.py --zip RUTA_DEL_ZIP
echo.
set /p ROBOFLOW_API_KEY=Introduce tu clave Roboflow (no se guarda en el repositorio):
if "%ROBOFLOW_API_KEY%"=="" (
 echo No hay clave. Descarga cancelada.
 pause
 exit /b 1
)
"%PYTHON%" scripts\descargar_dataset_productos.py
if errorlevel 1 (
 echo Hubo un problema. Revisa el mensaje de error.
 pause
 exit /b 1
)
echo Dataset preparado. Revisa datos\dataset_preparado antes de importar.
pause
