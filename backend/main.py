"""Punto Verde Store: API local de productos, ventas e inventario."""
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from .db import connection, initialize

ROOT = Path(__file__).resolve().parents[1]

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    yield

app = FastAPI(title="Punto Verde Store", version="0.1.0", lifespan=lifespan)

class NuevoProducto(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    categoria: str = Field(default="", max_length=80)
    precio: Decimal = Field(ge=0)
    stock: int = Field(default=0, ge=0)
    umbral_stock: int = Field(default=3, ge=0)

    @field_validator("precio")
    @classmethod
    def max_decimales(cls, v):
        if not v.is_finite() or v != v.quantize(Decimal("0.01")):
            raise ValueError("El precio debe tener máximo dos decimales")
        return v

class StockEntrada(BaseModel):
    cantidad: int = Field(gt=0)
    nota: str = Field(default="", max_length=300)

class VentaEntrada(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(default=1, gt=0)

def money(cents):
    return f"{Decimal(cents) / 100:.2f}"

def producto(row):
    d = dict(row)
    d["precio"] = money(d.pop("precio_centavos"))
    d["stock_bajo"] = d["stock"] <= d["umbral_stock"]
    return d

@app.get("/")
def home():
    return FileResponse(ROOT / "web" / "index.html")

@app.get("/api/salud")
def salud():
    return {"estado": "ok", "cnn": "pendiente_de_entrenamiento"}

@app.get("/api/productos")
def productos(q: str = Query(default="", max_length=120)):
    with connection() as db:
        rows = db.execute("SELECT * FROM productos WHERE activo=1 AND nombre LIKE ? ORDER BY nombre,id", (f"%{q}%",)).fetchall()
    return [producto(r) for r in rows]

@app.post("/api/productos", status_code=201)
def crear_producto(datos: NuevoProducto):
    with connection() as db:
        cur = db.execute("INSERT INTO productos(nombre,categoria,precio_centavos,stock,umbral_stock) VALUES (?,?,?,?,?)",
            (datos.nombre.strip(), datos.categoria.strip(), int(datos.precio * 100), datos.stock, datos.umbral_stock))
        pid = cur.lastrowid
        if datos.stock:
            db.execute("INSERT INTO movimientos(producto_id,tipo,cantidad,nota) VALUES (?,?,?,?)", (pid,"entrada",datos.stock,"Stock inicial"))
        result = db.execute("SELECT * FROM productos WHERE id=?", (pid,)).fetchone()
    return producto(result)

@app.post("/api/productos/{producto_id}/stock")
def agregar_stock(producto_id: int, datos: StockEntrada):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        cur = db.execute("UPDATE productos SET stock=stock+? WHERE id=? AND activo=1", (datos.cantidad,producto_id))
        if not cur.rowcount:
            raise HTTPException(404,"Producto no encontrado")
        db.execute("INSERT INTO movimientos(producto_id,tipo,cantidad,nota) VALUES (?,?,?,?)",
            (producto_id,"entrada",datos.cantidad,datos.nota))
        row = db.execute("SELECT * FROM productos WHERE id=?", (producto_id,)).fetchone()
    return producto(row)

@app.post("/api/ventas", status_code=201)
def vender(datos: VentaEntrada):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM productos WHERE id=? AND activo=1", (datos.producto_id,)).fetchone()
        if row is None:
            raise HTTPException(404,"Producto no encontrado")
        if row["stock"] < datos.cantidad:
            raise HTTPException(409,"Stock insuficiente")
        precio = row["precio_centavos"]
        total = precio * datos.cantidad
        cur = db.execute("INSERT INTO ventas(producto_id,producto_nombre,cantidad,precio_unitario_centavos,total_centavos) VALUES (?,?,?,?,?)",
            (datos.producto_id,row["nombre"],datos.cantidad,precio,total))
        db.execute("UPDATE productos SET stock=stock-? WHERE id=?", (datos.cantidad,datos.producto_id))
        db.execute("INSERT INTO movimientos(producto_id,tipo,cantidad,nota) VALUES (?,?,?,?)",
            (datos.producto_id,"salida",-datos.cantidad,f"Venta #{cur.lastrowid}"))
        return {"id":cur.lastrowid,"producto_id":datos.producto_id,"cantidad":datos.cantidad,"total":money(total)}

@app.get("/api/ventas")
def historial():
    with connection() as db:
        rows = db.execute("SELECT * FROM ventas ORDER BY id DESC LIMIT 200").fetchall()
    return [{**dict(r),"precio_unitario":money(r["precio_unitario_centavos"]),"total":money(r["total_centavos"])} for r in rows]

@app.get("/api/resumen")
def resumen():
    with connection() as db:
        ventas = db.execute("SELECT COUNT(*) n, COALESCE(SUM(total_centavos),0) total FROM ventas WHERE date(fecha)=date('now')").fetchone()
        bajos = db.execute("SELECT COUNT(*) n FROM productos WHERE activo=1 AND stock<=umbral_stock").fetchone()
    return {"ventas_hoy":ventas["n"],"total_hoy":money(ventas["total"]),"stock_bajo":bajos["n"]}

@app.post("/api/reconocer")
def reconocer():
    raise HTTPException(503,"CNN todavía no entrenada con productos: use búsqueda manual.")
