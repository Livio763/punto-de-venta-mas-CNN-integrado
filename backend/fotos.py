"""Captura de fotografías etiquetadas para entrenar una CNN propia."""
import hashlib
import io
import os
import re
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from .db import connection, DB_PATH

router = APIRouter(prefix="/api")
MAX_BYTES = 6 * 1024 * 1024
MAX_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
SESSION = re.compile(r"^[a-zA-Z0-9_-]{1,48}$")

def storage_dir():
    return Path(os.environ.get("PVS_PHOTO_DIR", str(DB_PATH.parent / "fotos")))

def get_product(db, product_id):
    row = db.execute("SELECT id FROM productos WHERE id=? AND activo=1", (product_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Producto no encontrado")

@router.post("/productos/{producto_id}/fotos", status_code=201)
async def cargar_foto(producto_id: int, archivo: UploadFile = File(...), sesion: str = Form(...)):
    if not SESSION.fullmatch(sesion):
        raise HTTPException(422, "La sesión debe contener 1 a 48 letras, números, guiones o guiones bajos")
    if archivo.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(415, "Solo JPEG, PNG o WebP")
    raw = await archivo.read(MAX_BYTES + 1)
    await archivo.close()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "La imagen supera el máximo de 6 MB")
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.format not in ("JPEG", "PNG", "WEBP"):
                raise ValueError("Formato de imagen no válido")
            if opened.width * opened.height > MAX_PIXELS:
                raise ValueError("Dimensiones excesivas")
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((1600, 1600))
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=90)
            payload = out.getvalue()
    except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, "Archivo de imagen inválido o demasiado grande")
    digest = hashlib.sha256(payload).hexdigest()
    filename = f"{digest}.jpg"
    dest = storage_dir() / f"producto_{producto_id:06d}" / sesion / filename
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        get_product(db, producto_id)
        exists = db.execute("SELECT id FROM fotos_producto WHERE producto_id=? AND ruta=?", (producto_id, str(dest))).fetchone()
        if exists:
            raise HTTPException(409, "Esa fotografía ya está registrada")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        try:
            cursor = db.execute("INSERT INTO fotos_producto(producto_id,ruta,sesion) VALUES (?,?,?)",
                                (producto_id, str(dest), sesion))
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        photo_id = cursor.lastrowid
    return {"id": photo_id, "producto_id": producto_id, "sesion": sesion, "ancho": image.width, "alto": image.height}

@router.get("/productos/{producto_id}/fotos")
def listar_fotos(producto_id: int):
    with connection() as db:
        get_product(db, producto_id)
        rows = db.execute("SELECT id,sesion,fecha FROM fotos_producto WHERE producto_id=? ORDER BY id", (producto_id,)).fetchall()
    return [{**dict(row), "url": f"/api/fotos/{row['id']}"} for row in rows]

@router.get("/fotos/{foto_id}")
def obtener_foto(foto_id: int):
    with connection() as db:
        row = db.execute("SELECT ruta FROM fotos_producto WHERE id=?", (foto_id,)).fetchone()
    if row is None or not Path(row["ruta"]).is_file():
        raise HTTPException(404, "Fotografía no encontrada")
    return FileResponse(row["ruta"], media_type="image/jpeg")

@router.get("/dataset/resumen")
def resumen_dataset():
    with connection() as db:
        rows = db.execute("""SELECT p.id,p.nombre,COUNT(f.id) fotos,COUNT(DISTINCT NULLIF(f.sesion,'')) sesiones
            FROM productos p LEFT JOIN fotos_producto f ON f.producto_id=p.id
            WHERE p.activo=1 GROUP BY p.id,p.nombre ORDER BY p.id""").fetchall()
    return [{"producto_id":r["id"],"nombre":r["nombre"],"fotos":r["fotos"],"sesiones":r["sesiones"],
             "estado_cnn":"pendiente_entrenamiento"} for r in rows]

@router.get("/dataset/manifiesto")
def manifiesto_dataset():
    """Lista rutas y etiquetas; no modifica el split ni entrena automáticamente."""
    with connection() as db:
        rows = db.execute("""SELECT f.id,p.id producto_id,p.nombre,f.sesion,f.ruta
            FROM fotos_producto f JOIN productos p ON p.id=f.producto_id
            WHERE p.activo=1 ORDER BY p.id,f.id""").fetchall()
    return {"imagenes":[{**dict(r)} for r in rows], "nota":"Dividir train/val/test por sesión; no por foto."}
