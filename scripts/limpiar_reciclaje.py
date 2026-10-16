"""Limpieza segura de archivos LOCALES del reciclaje anterior.

Por defecto solo muestra candidatos. Al aplicar, primero crea un respaldo ZIP.
Nunca toca la base de tienda ni las nuevas fotos en datos/fotos/.
"""
import argparse
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
LEGACY=[
    "dataset", "modelo_reciclaje.keras", "modelo_web", "continuo.log",
    "train.log", "servidor.log", "ngrok.log", "inter.html"
]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--aplicar",action="store_true",help="Respaldar y limpiar archivos locales heredados")
    args=p.parse_args()
    paths=[BASE/name for name in LEGACY if (BASE/name).exists()]
    print("Candidatos de reciclaje anterior:")
    for path in paths:
        print(" -",path)
    if not paths:
        print("No hay archivos heredados identificados.")
        return
    if not args.aplicar:
        print("SIMULACIÓN: no se borró nada. Usa --aplicar tras revisar la lista.")
        return
    respaldo=BASE/"respaldos_locales"/("reciclaje_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".zip")
    respaldo.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(respaldo,"x",zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
        for path in paths:
            if path.is_file():
                archive.write(path,path.relative_to(BASE))
            else:
                for child in path.rglob("*"):
                    if child.is_file():
                        archive.write(child,child.relative_to(BASE))
    print("Respaldo creado:",respaldo)
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    print("Limpieza completada. Datos comerciales y modelos nuevos conservados.")

if __name__=="__main__":
    main()
