"""Descarga de pesos (equivalente a la CELDA 1 del notebook)."""
import os
import urllib.request

from .config import MODELOS, MODELO_CODEFORMER, PESOS


def descargar_pesos(con_codeformer=False):
    os.makedirs(PESOS, exist_ok=True)
    lista = dict(MODELOS)
    if con_codeformer:
        lista.update(MODELO_CODEFORMER)
    for nombre, url in lista.items():
        ruta = os.path.join(PESOS, nombre)
        if not os.path.exists(ruta) or os.path.getsize(ruta) < 100_000:
            print(f'⏬ {nombre}')
            urllib.request.urlretrieve(url, ruta)
        print(f'✓ {nombre:40s} {os.path.getsize(ruta) / 1e6:6.1f} MB')
