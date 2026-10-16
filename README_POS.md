# Punto Verde Store — MVP comercial

Esta rama prepara la registradora móvil **sin login**, para uso en una sola tienda y red local. El reconocimiento con **CNN propia, entrenada con fotografías de productos**, es la siguiente fase; no se utiliza MobileNetV2 ni embeddings.

## Instalar

```bash
python -m pip install -r requirements-pos.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Abrir http://127.0.0.1:8000. Para conectarse desde un teléfono en la LAN, configurar una dirección accesible y **HTTPS** para el permiso de cámara (excepto localhost). No publicar sin autenticación ni otras protecciones.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

La base SQLite se crea automáticamente en `datos/tienda.db`, o en la ruta definida por `PVS_DB_PATH`. No subir datos reales de tienda al repositorio.

## Flujo disponible

Crear producto con precio (Bs) y stock inicial; buscar y vender por nombre; sumar stock; consultar ventas y resumen de hoy. No se permite stock negativo. Importes guardados en centavos enteros. Operaciones de venta y stock usan transacciones.

## Próxima fase CNN

Reutilizar la arquitectura convolucional original de `entrenar.py`, sustituyendo clases de residuos por IDs estables de productos. Capturar fotografías etiquetadas en múltiples sesiones; mantener entrenamiento/validación/prueba separados por sesión; entrenar, evaluar por clase y publicar un modelo versionado solo si supera criterios de aceptación. La inferencia nunca debe registrar una venta sin confirmación humana. Los productos nuevos son vendibles manualmente hasta el siguiente entrenamiento validado.

## Fase 2: fotos etiquetadas por producto

En **Productos** guarda el artículo, selecciónalo, escribe un identificador de sesión (por ejemplo, `dia1_frente`) y usa **Encender cámara → Tomar fotografía**, o sube archivos JPEG/PNG/WebP desde el teléfono. Para acceso desde otro dispositivo, la cámara requiere un contexto seguro HTTPS (o localhost).

La API almacena JPEG normalizados bajo `datos/fotos/producto_000001/<sesion>/<hash>.jpg` y guarda referencias en SQLite; verifica tipo, tamaño máximo de 6 MB, dimensiones y duplicados dentro de una sesión.

Endpoints:
- `POST /api/productos/{id}/fotos` con multipart `archivo` + `sesion`
- `GET /api/productos/{id}/fotos`
- `GET /api/fotos/{foto_id}`
- `GET /api/dataset/resumen`
- `GET /api/dataset/manifiesto`

El manifiesto ofrece rutas, IDs de producto y sesiones para una próxima fase de entrenamiento. **No entrena automáticamente** al cargar fotografías. Captura varias sesiones reales por producto con luz, fondos y ángulos diferentes. No mezclar imágenes de una misma sesión entre train/validación/test. La cámara no ejecuta reconocimiento todavía.

Pruebas de esta fase: `python -m unittest discover -s tests -v`.
