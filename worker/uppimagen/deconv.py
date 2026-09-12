"""Deconvolución regularizada.

Richardson-Lucy con regularización de variación total (TV) como método
principal, y Wiener como alternativa rápida. Más iteraciones de RL no es
"más nítido": amplifica el ruido. Por eso hay parada automática por residuo.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve

EPS = 1e-8


def _convolucionar(img: np.ndarray, psf: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return np.stack(
            [fftconvolve(img[..., c], psf, mode="same") for c in range(img.shape[2])], axis=-1
        )
    return fftconvolve(img, psf, mode="same")


def _gradiente_tv(img: np.ndarray) -> np.ndarray:
    """Divergencia del gradiente normalizado (regularización TV), canal a canal."""

    def _div_tv_2d(canal: np.ndarray) -> np.ndarray:
        gx = np.roll(canal, -1, axis=1) - canal
        gy = np.roll(canal, -1, axis=0) - canal
        norma = np.sqrt(gx**2 + gy**2 + EPS)
        gx_n, gy_n = gx / norma, gy / norma
        div = (gx_n - np.roll(gx_n, 1, axis=1)) + (gy_n - np.roll(gy_n, 1, axis=0))
        return div

    if img.ndim == 3:
        return np.stack([_div_tv_2d(img[..., c]) for c in range(img.shape[2])], axis=-1)
    return _div_tv_2d(img)


def richardson_lucy_tv(
    img: np.ndarray,
    psf: np.ndarray,
    iters: int = 20,
    lam: float = 0.002,
    tol_residuo: float = 1e-4,
) -> np.ndarray:
    """Richardson-Lucy con regularización TV y parada automática.

    `lam` debe escalar con el ruido estimado (lambda ~ k * sigma_n) desde el
    llamador; aquí solo se aplica como peso de la regularización.
    """
    psf_espejo = psf[::-1, ::-1]
    estimacion = np.clip(img.copy(), EPS, None).astype(np.float64)
    img64 = img.astype(np.float64)

    residuo_anterior = None
    for _ in range(max(1, iters)):
        reproyeccion = np.clip(_convolucionar(estimacion, psf), EPS, None)
        ratio = img64 / reproyeccion
        correccion = _convolucionar(ratio, psf_espejo)

        regularizacion = 1.0 - lam * _gradiente_tv(estimacion)
        regularizacion = np.clip(regularizacion, 0.2, 5.0)

        estimacion = estimacion * correccion / regularizacion
        estimacion = np.clip(estimacion, 0.0, None)

        residuo = float(np.sqrt(np.mean((reproyeccion - img64) ** 2)))
        if residuo_anterior is not None:
            mejora = residuo_anterior - residuo
            if mejora < tol_residuo * max(residuo_anterior, EPS):
                break
        residuo_anterior = residuo

    return np.clip(estimacion, 0.0, 1.0).astype(np.float32)


def wiener(img: np.ndarray, psf: np.ndarray, sigma_n: float) -> np.ndarray:
    """Filtro de Wiener en frecuencia, rápido pero menos preciso que RL-TV.

    El filtro se aplica en el dominio de la frecuencia, que asume
    convolución circular. Para no confundir el borde de esa periodicidad
    artificial con una degradación real, la imagen se extiende por
    reflexión un margen igual al tamaño de la PSF antes de filtrar, y ese
    margen se recorta al final.
    """
    ph, pw = psf.shape

    def _wiener_2d(canal: np.ndarray) -> np.ndarray:
        extendido = np.pad(canal, ((ph, ph), (pw, pw)), mode="reflect")
        h, w = extendido.shape

        psf_pad = np.zeros((h, w), dtype=np.float64)
        psf_pad[:ph, :pw] = psf
        psf_pad = np.roll(psf_pad, (-(ph // 2), -(pw // 2)), axis=(0, 1))

        H = np.fft.fft2(psf_pad)
        Y = np.fft.fft2(extendido)

        potencia_senal = np.mean(extendido.astype(np.float64) ** 2)
        nsr = (sigma_n**2) / max(potencia_senal, EPS)

        H_conj = np.conj(H)
        filtro = H_conj / (np.abs(H) ** 2 + nsr)
        X = filtro * Y
        restaurado = np.real(np.fft.ifft2(X))
        return restaurado[ph:-ph, pw:-pw]

    if img.ndim == 3:
        salida = np.stack([_wiener_2d(img[..., c]) for c in range(img.shape[2])], axis=-1)
    else:
        salida = _wiener_2d(img)

    return np.clip(salida, 0.0, 1.0).astype(np.float32)
