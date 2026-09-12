"""Carga y guardado de imágenes en luz lineal, float32.

Toda la matemática del pipeline ocurre en luz lineal. Cargar un JPEG y
deconvolucionar sobre valores con gamma sRGB produce halos y resultados
falsos, así que este módulo es el único lugar donde se decodifica/recodifica
la curva de gamma.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

EXTENSIONES_RAW = {".dng", ".cr2", ".nef", ".arw"}
EXTENSIONES_LDR = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# Kernel Laplaciano 3x3 estándar y su norma L2, usados para estimar sigma_n.
_KERNEL_LAPLACIANO = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
_NORMA_KERNEL_LAPLACIANO = float(np.linalg.norm(_KERNEL_LAPLACIANO))


@dataclass
class Metadatos:
    """Metadatos de una imagen cargada, relevantes para el pipeline."""

    ruta: str
    origen: str  # "raw" | "ldr"
    ancho: int
    alto: int
    sigma_n: float  # nivel de ruido estimado, en la misma escala que la imagen [0,1]
    iso: Optional[float] = None
    apertura: Optional[float] = None
    extra: dict = field(default_factory=dict)


def _srgb_a_lineal(c: np.ndarray) -> np.ndarray:
    """Inversa exacta de la curva sRGB (no la aproximación x**2.2)."""
    c = np.clip(c, 0.0, 1.0)
    a = 0.055
    lineal = np.where(c <= 0.04045, c / 12.92, ((c + a) / (1 + a)) ** 2.4)
    return lineal.astype(np.float32)


def _lineal_a_srgb(c: np.ndarray) -> np.ndarray:
    """Curva sRGB directa (codificación), inversa de `_srgb_a_lineal`."""
    c = np.clip(c, 0.0, 1.0)
    a = 0.055
    srgb = np.where(c <= 0.0031308, c * 12.92, (1 + a) * np.power(c, 1 / 2.4) - a)
    return srgb.astype(np.float32)


def estimar_sigma_ruido(gris: np.ndarray) -> float:
    """Estima la desviación estándar del ruido de forma robusta.

    Usa la mediana de desviaciones absolutas (MAD) de la respuesta del
    Laplaciano: los bordes reales generan valores grandes que la mediana
    ignora como outliers, así que el estimador queda dominado por el ruido
    en zonas planas sin necesidad de segmentarlas explícitamente.
    """
    resp = cv2.filter2D(gris.astype(np.float64), -1, _KERNEL_LAPLACIANO, borderType=cv2.BORDER_REFLECT)
    mad = np.median(np.abs(resp - np.median(resp)))
    sigma_resp = mad / 0.6745
    sigma_n = sigma_resp / _NORMA_KERNEL_LAPLACIANO
    return float(max(sigma_n, 0.0))


def _cargar_raw(ruta: str) -> tuple[np.ndarray, Metadatos]:
    import rawpy

    with rawpy.imread(ruta) as raw:
        rgb16 = raw.postprocess(
            output_bps=16,
            no_auto_bright=True,
            gamma=(1, 1),
            use_camera_wb=True,
            demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
            fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
            output_color=rawpy.ColorSpace.raw,
        )

    img = rgb16.astype(np.float32) / 65535.0

    iso = apertura = None
    try:
        import exifread

        with open(ruta, "rb") as fh:
            tags = exifread.process_file(fh, details=False)
        if "EXIF ISOSpeedRatings" in tags:
            iso = float(str(tags["EXIF ISOSpeedRatings"]))
        if "EXIF FNumber" in tags:
            valor = tags["EXIF FNumber"].values[0]
            apertura = float(valor.num) / float(valor.den)
    except Exception:
        pass

    gris = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    sigma_n = estimar_sigma_ruido(gris)

    meta = Metadatos(
        ruta=ruta,
        origen="raw",
        ancho=img.shape[1],
        alto=img.shape[0],
        sigma_n=sigma_n,
        iso=iso,
        apertura=apertura,
    )
    return img, meta


def _cargar_ldr(ruta: str) -> tuple[np.ndarray, Metadatos]:
    bgr = cv2.imread(ruta, cv2.IMREAD_UNCHANGED)
    if bgr is None:
        raise FileNotFoundError(f"No se pudo leer la imagen: {ruta}")

    if bgr.ndim == 2:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
    if bgr.shape[2] == 4:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_BGRA2BGR)

    if bgr.dtype == np.uint16:
        srgb = bgr.astype(np.float32) / 65535.0
    else:
        srgb = bgr.astype(np.float32) / 255.0

    rgb_srgb = cv2.cvtColor(srgb, cv2.COLOR_BGR2RGB)
    img = _srgb_a_lineal(rgb_srgb)

    gris = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    sigma_n = estimar_sigma_ruido(gris)

    meta = Metadatos(
        ruta=ruta,
        origen="ldr",
        ancho=img.shape[1],
        alto=img.shape[0],
        sigma_n=sigma_n,
    )
    return img, meta


def cargar(ruta: str) -> tuple[np.ndarray, Metadatos]:
    """Devuelve (imagen float32 en [0,1] LINEAL, metadatos)."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext in EXTENSIONES_RAW:
        return _cargar_raw(ruta)
    if ext in EXTENSIONES_LDR:
        return _cargar_ldr(ruta)
    raise ValueError(f"Extensión no soportada: {ext}")


def guardar(ruta: str, img_lineal: np.ndarray, bits: int = 16) -> None:
    """Guarda una imagen lineal float32, reaplicando gamma sRGB.

    Por defecto guarda a 16 bits (TIFF/PNG). Para JPEG se fuerza 8 bits.
    """
    ext = os.path.splitext(ruta)[1].lower()
    srgb = _lineal_a_srgb(img_lineal)

    if ext in (".jpg", ".jpeg"):
        bits = 8

    if bits == 16:
        salida = np.clip(srgb * 65535.0 + 0.5, 0, 65535).astype(np.uint16)
    else:
        salida = np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)

    bgr = cv2.cvtColor(salida, cv2.COLOR_RGB2BGR)
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    ok = cv2.imwrite(ruta, bgr)
    if not ok:
        raise IOError(f"No se pudo escribir la imagen: {ruta}")
