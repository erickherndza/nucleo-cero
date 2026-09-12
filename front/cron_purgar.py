"""Cron diario de purga de archivos vencidos.

Sin esto el disco del hosting compartido se llena en semanas: los originales
(RAW/JPEG) y resultados se borran `DIAS_RETENCION_ARCHIVOS` días después de
entregado el trabajo (campo `purgar_en`).

Uso en cPanel (Cron Jobs): ejecutar diariamente, ej.
    /usr/local/bin/python3.8 /home/usuario/uppimagen/front/cron_purgar.py
"""

import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from app import crear_app
from app.models import Trabajo, db


def purgar_vencidos() -> int:
    app = crear_app()
    with app.app_context():
        vencidos = Trabajo.query.filter(
            Trabajo.purgar_en.isnot(None), Trabajo.purgar_en < datetime.utcnow()
        ).all()

        directorio_archivos = app.config["DIRECTORIO_ARCHIVOS"]
        purgados = 0
        for trabajo in vencidos:
            directorio_trabajo = os.path.join(directorio_archivos, trabajo.token_publico)
            shutil.rmtree(directorio_trabajo, ignore_errors=True)
            db.session.delete(trabajo)  # cascada elimina también sus `archivos`
            purgados += 1

        db.session.commit()
        return purgados


if __name__ == "__main__":
    total = purgar_vencidos()
    print(f"[{datetime.utcnow().isoformat()}] Trabajos purgados: {total}")
