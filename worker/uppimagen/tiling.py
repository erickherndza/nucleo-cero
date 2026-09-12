"""Procesamiento por tiles para mantener el consumo de memoria constante.

Sin esto, un RAW de 24 MP en float32 son ~290 MB por frame y un burst no cabe
en 8 GB de RAM. Se procesa en bloques de TAMANO_TILE con solapamiento
SOLAPAMIENTO, mezclando con una ventana de Hann 2D para evitar costuras.

Los acumuladores de salida viven en disco (memmap), no en RAM: así el
consumo se mantiene acotado incluso cuando la salida final (imagen HR de un
burst) pesa más que la RAM disponible. Solo los tiles individuales —
pequeños por diseño— ocupan memoria de Python en cada paso.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import weakref
from typing import Callable

import numpy as np

TAMANO_TILE = 512
SOLAPAMIENTO = 64


def _ventana_hann_2d(alto: int, ancho: int) -> np.ndarray:
    hy = np.hanning(alto) if alto > 1 else np.ones(1)
    hx = np.hanning(ancho) if ancho > 1 else np.ones(1)
    ventana = np.outer(hy, hx).astype(np.float32)
    # Evitar ceros exactos en los bordes de la imagen completa (se corrige
    # fuera, pero mantenemos un mínimo para no dividir por cero en la mezcla).
    return np.clip(ventana, 1e-6, 1.0)


def _lista_tiles(dimension: int, tamano: int, solape: int) -> list[tuple[int, int]]:
    """Devuelve pares (inicio, fin) de tiles cubriendo `dimension` con solape."""
    paso = tamano - solape
    if paso <= 0:
        raise ValueError("El solapamiento debe ser menor que el tamaño del tile")

    tiles = []
    inicio = 0
    while True:
        fin = min(inicio + tamano, dimension)
        tiles.append((inicio, fin))
        if fin >= dimension:
            break
        inicio += paso
    return tiles


def _memmap_temporal(forma: tuple[int, ...], dtype=np.float32) -> np.memmap:
    """Crea un array respaldado en disco que se autolimpia al ser recolectado."""
    tmpdir = tempfile.mkdtemp(prefix="uppimagen_tiles_")
    ruta = os.path.join(tmpdir, "buffer.dat")
    arr = np.memmap(ruta, dtype=dtype, mode="w+", shape=forma)
    arr[:] = 0
    weakref.finalize(arr, shutil.rmtree, tmpdir, ignore_errors=True)
    return arr


def procesar_por_tiles(
    img: np.ndarray,
    funcion: Callable[[np.ndarray], np.ndarray],
    factor: float = 1.0,
    tamano_tile: int = TAMANO_TILE,
    solapamiento: int = SOLAPAMIENTO,
) -> np.memmap:
    """Aplica `funcion` a la imagen dividida en tiles solapados y mezcla el
    resultado con una ventana de Hann 2D. `funcion` puede cambiar la
    resolución del tile por `factor` (debe ser consistente para todos).

    Devuelve un `np.memmap` float32 (se comporta como un ndarray normal para
    lectura/guardado) cuyo respaldo en disco se libera automáticamente
    cuando deja de referenciarse.
    """
    h, w = img.shape[:2]
    canales = img.shape[2] if img.ndim == 3 else 1

    h_out, w_out = int(round(h * factor)), int(round(w * factor))
    forma_salida = (h_out, w_out, canales) if canales > 1 else (h_out, w_out)

    salida = _memmap_temporal(forma_salida, dtype=np.float32)
    pesos = _memmap_temporal((h_out, w_out), dtype=np.float32)

    filas = _lista_tiles(h, tamano_tile, solapamiento)
    columnas = _lista_tiles(w, tamano_tile, solapamiento)

    for y0, y1 in filas:
        for x0, x1 in columnas:
            tile = np.array(img[y0:y1, x0:x1])  # copia pequeña, tamaño de tile
            resultado_tile = funcion(tile)

            # El tamaño de salida se deriva del tamaño de ESTE tile de
            # entrada (no de restar coordenadas absolutas redondeadas por
            # separado), para que coincida exactamente con lo que produce
            # una `funcion` que escala por el mismo `factor`.
            alto_tile_out = int(round((y1 - y0) * factor))
            ancho_tile_out = int(round((x1 - x0) * factor))
            ty0 = int(round(y0 * factor))
            tx0 = int(round(x0 * factor))
            ty1 = min(ty0 + alto_tile_out, h_out)
            tx1 = min(tx0 + ancho_tile_out, w_out)
            alto_tile_out, ancho_tile_out = ty1 - ty0, tx1 - tx0

            ventana = _ventana_hann_2d(alto_tile_out, ancho_tile_out)

            if resultado_tile.shape[:2] != (alto_tile_out, ancho_tile_out):
                raise ValueError(
                    "La función de tile devolvió un tamaño inconsistente con `factor`: "
                    f"esperado {(alto_tile_out, ancho_tile_out)}, obtenido {resultado_tile.shape[:2]}"
                )

            if canales > 1:
                salida[ty0:ty1, tx0:tx1] += (resultado_tile * ventana[..., None]).astype(np.float32)
            else:
                salida[ty0:ty1, tx0:tx1] += (resultado_tile * ventana).astype(np.float32)
            pesos[ty0:ty1, tx0:tx1] += ventana

    # Normalización final en bloques de filas, para no cargar la imagen
    # completa en RAM cuando la salida es más grande que la memoria disponible.
    bloque_filas = max(1, tamano_tile)
    for y0, y1 in _lista_tiles(h_out, bloque_filas, 0):
        bloque_den = np.maximum(np.array(pesos[y0:y1]), 1e-6)
        bloque_num = np.array(salida[y0:y1])
        if canales > 1:
            salida[y0:y1] = (bloque_num / bloque_den[..., None]).astype(np.float32)
        else:
            salida[y0:y1] = (bloque_num / bloque_den).astype(np.float32)

    salida.flush()
    return salida
