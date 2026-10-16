"""Descarga RF100 soda-bottles y prepara recortes para la CNN propia.

Requiere clave Roboflow (variable ROBOFLOW_API_KEY) o ZIP descargado desde Universe.
No descarga pesos preentrenados. No borra datos existentes.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import zipfile
from pathlib import Path
from PIL import Image, ImageOps

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/"datos"
SELECT={"coca-cola","fanta","sprite"}
ALIASES={"coca cola":"coca-cola","cocacola":"coca-cola"}

def parse():
    p=argparse.ArgumentParser(description="Descargar y preparar dataset de gaseosas (RF100)")
    p.add_argument("--api-key",default=os.getenv("ROBOFLOW_API_KEY"),help="Clave API Roboflow (preferible variable de entorno)")
    p.add_argument("--zip",type=Path,help="Usar un ZIP de Roboflow ya descargado")
    p.add_argument("--dataset-dir",type=Path,default=DATA/"externos"/"soda-bottles")
    p.add_argument("--importar",action="store_true",help="Registrar imágenes en SQLite y crear productos de ejemplo sin precio")
    p.add_argument("--db",type=Path,default=DATA/"tienda.db")
    p.add_argument("--fotos-dir",type=Path,default=DATA/"fotos")
    return p.parse_args()

def descargar(args):
    target=args.dataset_dir.resolve()
    if args.zip:
        with zipfile.ZipFile(args.zip) as z:
            for entry in z.infolist():
                if entry.is_dir():
                    continue
                path=Path(entry.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("ZIP contiene rutas inseguras")
                out=(target/path).resolve()
                if not out.is_relative_to(target):
                    raise ValueError("ZIP contiene rutas inseguras")
                out.parent.mkdir(parents=True,exist_ok=True)
                with z.open(entry) as source, open(out,"wb") as dest:
                    while chunk:=source.read(1024*1024):
                        dest.write(chunk)
    else:
        if not args.api_key:
            raise RuntimeError("Configura ROBOFLOW_API_KEY o usa --zip archivo.zip. La descarga puede requerir cuenta y aceptación de licencia.")
        try:
            from roboflow import Roboflow
        except ImportError as exc:
            raise RuntimeError("Instala: python -m pip install roboflow") from exc
        rf=Roboflow(api_key=args.api_key)
        result=rf.workspace("roboflow-100").project("soda-bottles").version(3).download("yolov8",location=str(target),overwrite=False)
        target=Path(result.location).resolve()
    return target

def nombres(yamlpath):
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("Instala PyYAML: python -m pip install pyyaml") from exc
    d=yaml.safe_load(yamlpath.read_text(encoding="utf-8"))
    n=d["names"]
    if isinstance(n,dict):
        return {int(i):str(v).strip().lower() for i,v in n.items()}
    return {i:str(v).strip().lower() for i,v in enumerate(n)}

def convertir(base, fotos_dir, db, importar):
    yamls=list(base.rglob("data.yaml"))
    if not yamls:
        raise RuntimeError("No se encontró data.yaml: exporta el dataset en formato YOLOv8")
    root=yamls[0].parent
    clases=nombres(yamls[0])
    picked={i:ALIASES.get(n,n) for i,n in clases.items() if ALIASES.get(n,n) in SELECT}
    if not picked:
        raise RuntimeError(f"No hay clases compatibles en data.yaml: {clases}")
    if importar and not db.is_file():
        raise RuntimeError("Inicializa la tienda con Uvicorn antes de usar --importar (falta tienda.db)")
    conn=None
    ids={}
    if importar:
        conn=sqlite3.connect(db)
        conn.execute("PRAGMA foreign_keys=ON")
        for name in sorted(set(picked.values())):
            row=conn.execute("SELECT id FROM productos WHERE nombre=? AND activo=1",(name,)).fetchone()
            if row:
                ids[name]=row[0]
            else:
                ids[name]=conn.execute("INSERT INTO productos(nombre,categoria,precio_centavos,stock,umbral_stock) VALUES (?,?,0,0,3)",
                                      (name,"Dataset externo - revisar precio")).lastrowid
        conn.commit()
    counts={name:0 for name in set(picked.values())}
    duplicates=0
    # Clases de clasificación: recortes por bounding box, nunca imágenes completas multiclase.
    for split in ("train","valid","val","test"):
        img_dir=root/split/"images"
        lab_dir=root/split/"labels"
        if not img_dir.is_dir() or not lab_dir.is_dir():
            continue
        session={"train":"rf100_train","valid":"rf100_valid","val":"rf100_valid","test":"rf100_test"}[split]
        for imgpath in sorted(img_dir.iterdir()):
            if imgpath.suffix.lower() not in (".jpg",".jpeg",".png",".webp"):
                continue
            labpath=lab_dir/(imgpath.stem+".txt")
            if not labpath.is_file():
                continue
            with Image.open(imgpath) as opened:
                image=ImageOps.exif_transpose(opened).convert("RGB")
            w,h=image.size
            for idx,line in enumerate(labpath.read_text(encoding="utf-8").splitlines()):
                fields=line.split()
                if len(fields)<5:
                    continue
                try:
                    category=int(fields[0])
                    x,y,bw,bh=map(float,fields[1:5])
                except ValueError:
                    continue
                if category not in picked:
                    continue
                name=picked[category]
                left=max(0,round((x-bw/2)*w)); right=min(w,round((x+bw/2)*w))
                top=max(0,round((y-bh/2)*h)); bottom=min(h,round((y+bh/2)*h))
                if right-left<24 or bottom-top<24:
                    continue
                crop=image.crop((left,top,right,bottom))
                payload_path=f"{imgpath.as_posix()}:{idx}:{name}"
                digest=hashlib.sha256(payload_path.encode()).hexdigest()[:20]
                if importar:
                    dest=fotos_dir/f"producto_{ids[name]:06d}"/session/(digest+".jpg")
                else:
                    dest=DATA/"dataset_preparado"/name/session/(digest+".jpg")
                dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists():
                    duplicates+=1
                    continue
                crop.save(dest,"JPEG",quality=92)
                counts[name]+=1
                if conn:
                    conn.execute("INSERT INTO fotos_producto(producto_id,ruta,sesion) VALUES (?,?,?)",(ids[name],str(dest.resolve()),session))
    if conn:
        conn.commit()
        conn.close()
    return counts,duplicates

def main():
    args=parse()
    location=descargar(args)
    counts,duplicates=convertir(location,args.fotos_dir,args.db,args.importar)
    print(json.dumps({"origen":str(location),"imagenes_nuevas":counts,"ya_existentes":duplicates,
                      "importado_en_tienda":args.importar,
                      "nota":"Revisar calidad, etiquetas y precios; separar evaluación por origen y capturar fotos propias."},
                     indent=2,ensure_ascii=False))
    if not sum(counts.values()) and duplicates==0:
        raise SystemExit("No se generaron imágenes; inspecciona las clases y rutas del dataset.")

if __name__=="__main__":
    main()
