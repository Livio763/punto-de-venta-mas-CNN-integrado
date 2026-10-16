# Punto Verde Store — datasets y limpieza

Dataset seleccionado: [RF100 soda-bottles (Roboflow Universe)](https://universe.roboflow.com/roboflow-100/soda-bottles), licencia CC BY 4.0. El dataset contiene detecciones de Coca-Cola, Fanta y Sprite y otras clases; **no garantiza el tamaño o presentación de la bebida**. Comprobar visualmente los recortes y etiquetas antes de tratar cada clase como producto comercial. El modelo se entrena desde cero, sin pesos preentrenados.

## Windows: descarga guiada

1. Abre PowerShell desde la raíz del repositorio con el entorno `.venv` activo.
2. Ejecuta `python -m pip install -r requirements-dataset.txt`.
3. Ejecuta `.\\descargar_productos.bat` para introducir tu clave de Roboflow sin escribirla en el código. Roboflow puede pedir cuenta y aceptación de condiciones.
4. Si ya descargaste el ZIP en Roboflow Universe, usa:
   `python scripts/descargar_dataset_productos.py --zip C:\\ruta\\dataset.zip`.

**El script no necesita importar modelos ni entrenar YOLO**: descarga las fotografías/anotaciones en formato YOLOv8 y recorta las cajas anotadas para crear imágenes de clasificación. No modifica la tienda por defecto. Deposita recortes en `datos/dataset_preparado/<clase>/<split>/`. Revisa visualmente clases y recortes antes de importar.

## Incorporación a la tienda (opcional)

Con la base SQLite creada por la app, ejecuta la misma descarga con `--importar` para insertar imágenes en la tabla `fotos_producto` y vincularlas a productos Coca-Cola, Fanta o Sprite. Ejemplo desde ZIP:

```powershell
python scripts/descargar_dataset_productos.py --zip C:\ruta\dataset.zip --importar
```

Si el producto aún no existe, se crea con **precio Bs 0.00, stock 0 y etiqueta de revisión**. Antes de vender, debes establecer un precio correcto (la pantalla actual todavía no edita precios). Evita usar `--importar` en una base de tienda real sin revisar la configuración. Los splits originales se registran como sesiones `rf100_train`, `rf100_valid` y `rf100_test` para permitir separación durante el entrenamiento, pero son particiones de origen, **no necesariamente sesiones fotográficas independientes**. Evalúa posteriormente con fotos propias del teléfono, en condiciones reales de tienda.

## Limpieza de reciclaje anterior

Los archivos históricos versionados se eliminan **únicamente de la rama nueva**; el contenido previo sigue recuperable en `main` y en el historial Git.

Para archivos locales (incluye dataset antiguo que está ignorado por Git), el script es deliberadamente conservador: primero muestra candidatos sin borrar nada.

```powershell
python scripts/limpiar_reciclaje.py
```

Si estás de acuerdo con esa lista y necesitas liberar espacio, usa:

```powershell
python scripts/limpiar_reciclaje.py --aplicar
```

Antes de eliminar, crea un ZIP en `respaldos_locales/`. No borra `datos/fotos`, `datos/tienda.db`, `datos/modelos` ni `.venv`. No subir a Git los respaldos ZIP, fotografías reales ni claves API.

## Entrenamiento

Después de revisar e importar imágenes etiquetadas en la tienda, ejecutar:

```powershell
python -m cnn.entrenar --min-fotos 30 --min-sesiones 3 --epocas 40
```

Primero comprobar número de clases y muestras en `/api/dataset/resumen`. El entrenador exige al menos dos clases y tres grupos de sesión por clase. **No se ha entrenado ni evaluado todavía el modelo con imágenes de Coca-Cola.**
