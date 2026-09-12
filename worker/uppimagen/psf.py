"""Estimación de la PSF (Point Spread Function).

No se puede deconvolucionar lo que no se modela. v1 usa una PSF gaussiana
isotrópica, cuyo sigma se estima midiendo la Edge Spread Function sobre
bordes rectos y fuertes de la imagen.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy.optimize import curve_fit

SIGMA_FALLBACK = 0.8  # difracción típica, en píxeles


def _gaussiana_1d(x: np.ndarray, sigma: float, amp: float, x0: float, offset: float) -> np.ndarray:
    return offset + amp * np.exp(-0.5 * ((x - x0) / sigma) ** 2)


def _kernel_gaussiano(sigma: float, radio: int | None = None) -> np.ndarray:
    """Kernel 2D gaussiano isotrópico, normalizado a suma 1."""
    if radio is None:
        radio = max(1, int(np.ceil(4 * sigma)))
    eje = np.arange(-radio, radio + 1, dtype=np.float64)
    g1d = np.exp(-0.5 * (eje / max(sigma, 1e-6)) ** 2)
    kernel = np.outer(g1d, g1d)
    kernel /= kernel.sum()
    return kernel.astype(np.float32)


def _perfiles_esf(gris: np.ndarray, max_bordes: int = 30) -> list[np.ndarray]:
    """Extrae perfiles perpendiculares a bordes rectos (Edge Spread Function)."""
    img8 = np.clip(gris * 255.0, 0, 255).astype(np.uint8)
    bordes = cv2.Canny(img8, 50, 150)
    lineas = cv2.HoughLinesP(
        bordes, rho=1, theta=np.pi / 180, threshold=60, minLineLength=40, maxLineGap=3
    )
    if lineas is None:
        return []

    perfiles = []
    h, w = gris.shape
    longitud_muestreo = 12  # px a cada lado del borde
    paso = 0.25  # sub-píxel

    for linea in lineas[:max_bordes]:
        x1, y1, x2, y2 = linea[0]
        dx, dy = x2 - x1, y2 - y1
        largo = np.hypot(dx, dy)
        if largo < 1e-6:
            continue
        # normal unitaria a la línea (dirección de muestreo del perfil)
        nx, ny = -dy / largo, dx / largo
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

        offsets = np.arange(-longitud_muestreo, longitud_muestreo + paso, paso)
        xs = cx + nx * offsets
        ys = cy + ny * offsets

        if xs.min() < 1 or xs.max() > w - 2 or ys.min() < 1 or ys.max() > h - 2:
            continue

        muestras = cv2.remap(
            gris.astype(np.float32),
            xs.astype(np.float32).reshape(1, -1),
            ys.astype(np.float32).reshape(1, -1),
            interpolation=cv2.INTER_CUBIC,
        ).flatten()

        if not np.isfinite(muestras).all():
            continue
        perfiles.append(muestras)

    return perfiles


def _sigma_desde_perfiles(perfiles: list[np.ndarray], paso: float = 0.25) -> float | None:
    sigmas = []
    for perfil in perfiles:
        # Line Spread Function = derivada de la Edge Spread Function.
        lsf = np.gradient(perfil, paso)
        lsf = lsf - lsf.min()
        if lsf.max() < 1e-6:
            continue
        x = np.arange(len(lsf)) * paso
        x0_inicial = x[np.argmax(lsf)]
        amp_inicial = lsf.max()
        try:
            popt, _ = curve_fit(
                _gaussiana_1d,
                x,
                lsf,
                p0=[1.0, amp_inicial, x0_inicial, 0.0],
                maxfev=2000,
            )
            sigma = abs(popt[0])
            if 0.1 <= sigma <= 6.0:
                sigmas.append(sigma)
        except Exception:
            continue

    if not sigmas:
        return None
    return float(np.median(sigmas))


def estimar_psf(img: np.ndarray, metodo: str = "esf") -> np.ndarray:
    """Estima la PSF y devuelve un kernel 2D gaussiano normalizado a suma 1."""
    if img.ndim == 3:
        gris = cv2.cvtColor(img.astype(np.float32), cv2.COLOR_RGB2GRAY)
    else:
        gris = img.astype(np.float32)

    sigma = None
    if metodo == "esf":
        perfiles = _perfiles_esf(gris)
        sigma = _sigma_desde_perfiles(perfiles)

    if sigma is None:
        sigma = SIGMA_FALLBACK

    return _kernel_gaussiano(sigma)
