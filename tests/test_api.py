import os
import tempfile
import unittest
from pathlib import Path

with tempfile.TemporaryDirectory() as _unused:
    pass
TEMP = tempfile.TemporaryDirectory()
os.environ["PVS_DB_PATH"] = str(Path(TEMP.name) / "test.db")

from fastapi.testclient import TestClient
from backend.main import app

class TestVentas(unittest.TestCase):
    def test_flujo_completo(self):
        with TestClient(app) as client:
            r = client.post("/api/productos",json={"nombre":"Gaseosa 500 ml","precio":"12.50","stock":4})
            self.assertEqual(r.status_code,201)
            p=r.json()
            self.assertEqual(p["precio"],"12.50")
            self.assertEqual(client.post(f'/api/productos/{p["id"]}/stock',json={"cantidad":3}).json()["stock"],7)
            venta=client.post("/api/ventas",json={"producto_id":p["id"],"cantidad":2})
            self.assertEqual(venta.status_code,201)
            self.assertEqual(venta.json()["total"],"25.00")
            self.assertEqual(client.get("/api/productos").json()[0]["stock"],5)
            self.assertEqual(len(client.get("/api/ventas").json()),1)
            self.assertEqual(client.post("/api/ventas",json={"producto_id":p["id"],"cantidad":6}).status_code,409)
            self.assertEqual(client.get("/api/productos").json()[0]["stock"],5)

if __name__ == "__main__":
    unittest.main()
