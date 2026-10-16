# Planificación — Punto Verde Store con CNN propia

## Propósito
Registradora móvil local sin usuarios ni login. Permite crear productos, vender, aumentar stock y consultar historial en Bs. Una **CNN diseñada y entrenada desde cero** identificará los productos en imágenes, siempre con confirmación humana antes de vender o modificar el inventario.

## Arquitectura
- `backend/main.py`: API FastAPI para catálogo, ventas y stock.
- `backend/db.py`: SQLite, transacciones y movimientos.
- `backend/fotos.py`: validación, subida y organización de imágenes por producto y sesión.
- `web/index.html`: cámara, registro, venta e inventario.
- `cnn/entrenar.py`: CNN propia de cuatro bloques convolucionales, entrenamiento y métricas.
- `scripts/descargar_dataset_productos.py`: descarga de dataset Roboflow o procesamiento de ZIP, recortes de detecciones para clasificación.
- `scripts/limpiar_reciclaje.py`: respaldo previo y retirada segura de archivos locales del sistema anterior.

## Flujos
1. **Registrar:** nombre, categoría, precio, stock y fotos.
2. **Vender:** buscar o (en fase futura) reconocer con CNN, confirmar, descontar stock y guardar venta.
3. **Reponer:** buscar o (en fase futura) reconocer con CNN, confirmar, sumar stock y registrar movimiento.
4. **Entrenar:** fotos etiquetadas -> revisión -> separación por sesión -> CNN -> evaluación -> modelo candidato versionado.
5. **Ampliar catálogo:** los nuevos productos son vendibles manualmente hasta entrenar y validar una versión que los reconozca.

## Dataset inicial
La fuente propuesta es RF100 `soda-bottles` (Roboflow Universe, CC BY 4.0), que contiene etiquetas de Coca-Cola, Fanta y Sprite. Las cajas de detección YOLO se convierten a imágenes recortadas para entrenar una CNN clasificadora. No implica identificar tamaños o variantes comerciales con fiabilidad sin auditoría adicional.

Se requieren fotografías nuevas del celular para evaluar generalización. Softmax no es una medida calibrada de confianza ni garantiza rechazo de productos desconocidos.

## Fases
| Fase | Entregable | Estado |
|---|---|---|
| 1 | API, productos, ventas, inventario | Implementación inicial |
| 2 | Fotografía, galería y manifiesto | Implementación inicial |
| 3 | Importación de datasets y código de entrenamiento CNN | Preparado; ejecución pendiente |
| 4 | Reconocimiento CNN para venta y reposición | Pendiente |
| 5 | Evaluación con imágenes reales y puesta en marcha | Pendiente |

## Seguridad y calidad
Sin autenticación se permite **solo red local de confianza**, no publicar por Internet. El reconocimiento no genera ventas automáticamente. Las transacciones impiden stock negativo y almacenan el dinero en centavos. La carpeta local de fotos, modelos, base SQLite y claves API no se sube al repositorio. La versión histórica del reciclaje se conserva en la rama `main`; para limpiar archivos ignorados localmente utilizar el script que genera respaldo ZIP.

## Ejecución
```powershell
python -m pip install -r requirements-pos.txt
python -m uvicorn backend.main:app --reload
```

Consulta `GUIA_DATASET.md` para descargar datos. Con imágenes registradas, instala `requirements.txt` y ejecuta:
```powershell
python -m cnn.entrenar --min-fotos 30 --min-sesiones 3 --epocas 40
```
No activar un modelo sin revisar precisión por producto y rechazos de imágenes desconocidas.
