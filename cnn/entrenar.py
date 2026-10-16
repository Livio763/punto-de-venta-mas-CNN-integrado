"""Entrenamiento supervisado de CNN propia para productos comerciales.

Ejecutar desde raíz: python -m cnn.entrenar
No utiliza MobileNet ni pesos preentrenados.
"""
import argparse
import json
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def argumentos():
    p = argparse.ArgumentParser(description="Entrenar CNN propia con fotografías de Punto Verde Store")
    p.add_argument("--db", type=Path, default=ROOT / "datos" / "tienda.db")
    p.add_argument("--salida", type=Path, default=ROOT / "datos" / "modelos")
    p.add_argument("--epocas", type=int, default=40)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--min-fotos", type=int, default=30)
    p.add_argument("--min-sesiones", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()

def cargar_fotos(db_path):
    if not db_path.is_file():
        raise RuntimeError(f"Base de datos no encontrada: {db_path}")
    with sqlite3.connect(db_path) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute("""
            SELECT p.id producto_id,p.nombre,f.ruta,f.sesion FROM fotos_producto f
            JOIN productos p ON p.id=f.producto_id WHERE p.activo=1
            ORDER BY p.id,f.sesion,f.id
        """).fetchall()
    return [dict(r) for r in rows if Path(r["ruta"]).is_file()]

def preparar_datos(rows, min_fotos, min_sesiones, seed):
    """Separa por sesión, no por imagen, evitando fuga de capturas casi idénticas."""
    por_producto=defaultdict(lambda: defaultdict(list))
    for row in rows:
        por_producto[row["producto_id"]][row["sesion"]].append(row["ruta"])
    if len(por_producto)<2:
        raise RuntimeError("Se necesitan al menos 2 productos con fotografías.")
    clases=sorted(por_producto)
    split={"train":[],"val":[],"test":[]}
    rng=random.Random(seed)
    for clase_idx,pid in enumerate(clases):
        sessions=list(por_producto[pid].items())
        count=sum(len(images) for _,images in sessions)
        if count<min_fotos or len(sessions)<min_sesiones:
            raise RuntimeError(f"Producto {pid}: {count} fotos en {len(sessions)} sesiones; mínimo {min_fotos} fotos y {min_sesiones} sesiones.")
        rng.shuffle(sessions)
        # Al menos una sesión independiente para validación y otra para prueba.
        target={"val":sessions[0:1],"test":sessions[1:2],"train":sessions[2:]}
        for group,entries in target.items():
            for _,images in entries:
                split[group].extend((path,clase_idx) for path in images)
    if any(not x for x in split.values()):
        raise RuntimeError("Split vacío: captura más sesiones antes de entrenar.")
    label_map={str(i): pid for i,pid in enumerate(clases)}
    return split,label_map

def construir_modelo(tf, n_clases):
    """Arquitectura CNN desde cero inspirada en entrenar.py original."""
    L=tf.keras.layers
    reg=tf.keras.regularizers.l2(1e-4)
    model=tf.keras.Sequential([
        L.Input(shape=(160,160,3)),L.Rescaling(1/255),
        L.Conv2D(32,3,padding="same",use_bias=False),L.BatchNormalization(),L.Activation("relu"),L.MaxPooling2D(),L.Dropout(.10),
        L.Conv2D(64,3,padding="same",use_bias=False),L.BatchNormalization(),L.Activation("relu"),L.MaxPooling2D(),L.Dropout(.15),
        L.Conv2D(128,3,padding="same",use_bias=False),L.BatchNormalization(),L.Activation("relu"),L.MaxPooling2D(),L.Dropout(.20),
        L.Conv2D(256,3,padding="same",use_bias=False),L.BatchNormalization(),L.Activation("relu"),L.MaxPooling2D(),L.Dropout(.25),
        L.GlobalAveragePooling2D(),L.Dense(128,activation="relu",kernel_regularizer=reg),
        L.Dropout(.30),L.Dense(n_clases,activation="softmax")
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
                  loss="sparse_categorical_crossentropy",metrics=["accuracy"])
    return model

def dataset(tf, items, batch, training=False, seed=42):
    paths=[x[0] for x in items]
    labels=[x[1] for x in items]
    ds=tf.data.Dataset.from_tensor_slices((paths,labels))
    def read(path,label):
        raw=tf.io.read_file(path)
        image=tf.io.decode_jpeg(raw,channels=3)
        image=tf.image.resize(image,(160,160))
        return image,label
    ds=ds.map(read,num_parallel_calls=tf.data.AUTOTUNE)
    if training:
        ds=ds.shuffle(len(items),seed=seed)
        aug=tf.keras.Sequential([
            tf.keras.layers.RandomRotation(.07),
            tf.keras.layers.RandomZoom(.08),
            tf.keras.layers.RandomTranslation(.04,.04),
            tf.keras.layers.RandomBrightness(.10,value_range=(0,255))
        ])
        ds=ds.batch(batch).map(lambda x,y:(aug(x,training=True),y),
                                num_parallel_calls=tf.data.AUTOTUNE)
    else:
        ds=ds.batch(batch)
    return ds.prefetch(tf.data.AUTOTUNE)

def entrenar(args):
    if args.epocas<1 or args.batch<1 or args.min_fotos<1 or args.min_sesiones<3:
        raise ValueError("Argumentos inválidos: epocas/batch/min-fotos positivos y min-sesiones >=3")
    rows=cargar_fotos(args.db)
    splits,labels=preparar_datos(rows,args.min_fotos,args.min_sesiones,args.seed)
    import numpy as np
    import tensorflow as tf
    tf.keras.utils.set_random_seed(args.seed)
    model=construir_modelo(tf,len(labels))
    train=dataset(tf,splits["train"],args.batch,True,args.seed)
    val=dataset(tf,splits["val"],args.batch)
    test=dataset(tf,splits["test"],args.batch)
    callbacks=[
        tf.keras.callbacks.EarlyStopping(monitor="val_loss",patience=7,restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss",patience=3,factor=.5,min_lr=1e-5)
    ]
    history=model.fit(train,validation_data=val,epochs=args.epocas,callbacks=callbacks,verbose=2)
    loss,acc=model.evaluate(test,verbose=0)
    truth,pred=[],[]
    for images,y in test:
        scores=model.predict(images,verbose=0)
        truth.extend(y.numpy().tolist())
        pred.extend(np.argmax(scores,axis=1).tolist())
    n=len(labels)
    confusion=np.zeros((n,n),dtype=int)
    for a,b in zip(truth,pred):
        confusion[a,b]+=1
    precision={}
    for i in range(n):
        count=int(confusion[i].sum())
        precision[str(i)]={"producto_id":labels[str(i)],"total_pruebas":count,
                           "aciertos":int(confusion[i,i]),"recall":float(confusion[i,i]/count) if count else None}
    version=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output=args.salida/version
    output.mkdir(parents=True,exist_ok=False)
    model.save(output/"modelo.keras")
    (output/"clases.json").write_text(json.dumps(labels,indent=2),encoding="utf-8")
    metrics={"version":version,"accuracy_test":float(acc),"loss_test":float(loss),
             "ejemplos":{key:len(value) for key,value in splits.items()},
             "por_clase":precision,"matriz_confusion":confusion.tolist(),
             "val_accuracy_final":float(history.history["val_accuracy"][-1]),
             "nota":"Modelo candidato no publicado automáticamente; revisar métricas antes de activar."}
    (output/"metricas.json").write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"salida":str(output),"metricas":metrics},indent=2,ensure_ascii=False))
    return metrics

if __name__=="__main__":
    entrenar(argumentos())
