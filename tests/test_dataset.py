"""Pruebas de captura/dataset; aisladas de los datos reales de tienda."""
import io
import os
import tempfile
import unittest
from pathlib import Path

TEMP = tempfile.TemporaryDirectory()
os.environ["PVS_DB_PATH"] = str(Path(TEMP.name) / "store.db")
os.environ["PVS_PHOTO_DIR"] = str(Path(TEMP.name) / "fotos")

from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

def jpg():
    out=io.BytesIO()
    Image.new("RGB", (128, 128), (50, 140, 80)).save(out, format="JPEG")
    return out.getvalue()

class DatasetTests(unittest.TestCase):
    def test_fotos_y_manifiesto(self):
        with TestClient(app) as client:
            p=client.post("/api/productos",json={"nombre":"Agua 500 ml","precio":"5.00"}).json()
            id=p["id"]
            r=client.post(f"/api/productos/{id}/fotos",data={"sesion":"captura_01"},
                files={"archivo":("agua.jpg",jpg(),"image/jpeg")})
            self.assertEqual(r.status_code,201,r.text)
            foto=r.json()
            self.assertEqual(foto["producto_id"],id)
            lista=client.get(f"/api/productos/{id}/fotos").json()
            self.assertEqual(len(lista),1)
            self.assertEqual(client.get(lista[0]["url"]).status_code,200)
            self.assertEqual(client.get("/api/dataset/resumen").json()[-1]["fotos"],1)
            manifest=client.get("/api/dataset/manifiesto").json()["imagenes"]
            self.assertTrue(any(row["producto_id"]==id and row["sesion"]=="captura_01" for row in manifest))
            dup=client.post(f"/api/productos/{id}/fotos",data={"sesion":"captura_01"},
                files={"archivo":("agua.jpg",jpg(),"image/jpeg")})
            self.assertEqual(dup.status_code,409)
            self.assertEqual(client.post(f"/api/productos/{id}/fotos",data={"sesion":"../escape"},
                files={"archivo":("agua.jpg",jpg(),"image/jpeg")}).status_code,422)
            self.assertEqual(client.post(f"/api/productos/{id}/fotos",data={"sesion":"captura_02"},
                files={"archivo":("mal.txt",b"abc","text/plain")}).status_code,415)
            self.assertEqual(client.post("/api/productos/999999/fotos",data={"sesion":"captura_02"},
                files={"archivo":("agua.jpg",jpg(),"image/jpeg")}).status_code,404)

if __name__=="__main__":
    unittest.main()
