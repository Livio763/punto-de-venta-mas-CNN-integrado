"""Validación del split sin depender de TensorFlow ni fotografías reales."""
import unittest
from cnn.entrenar import preparar_datos

class EntrenamientoTests(unittest.TestCase):
    def test_sesiones_no_se_mezclan(self):
        rows=[]
        for pid in (10,20):
            for session in ("dia1","dia2","dia3","dia4"):
                for i in range(3):
                    rows.append({"producto_id":pid,"sesion":session,"ruta":f"/tmp/p{pid}/{session}/{i}.jpg"})
        groups,labels=preparar_datos(rows,12,3,42)
        self.assertEqual(set(labels.values()),{10,20})
        sets=[]
        for group in ("train","val","test"):
            sets.append(set("/".join(path.split("/")[:-1]) for path,_ in groups[group]))
        self.assertFalse(sets[0]&sets[1])
        self.assertFalse(sets[0]&sets[2])
        self.assertFalse(sets[1]&sets[2])

    def test_rechaza_pocos_datos(self):
        with self.assertRaises(RuntimeError):
            preparar_datos([{"producto_id":1,"sesion":"uno","ruta":"x.jpg"}],30,3,42)
