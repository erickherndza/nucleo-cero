"""Test de fidelidad: la regla de oro del proyecto.

Toda estimación x̂ debe cumplir consistencia de reproyección:

    ‖ D · H · x̂  −  y ‖  ≈  ‖n‖

Si degradamos el resultado con el mismo modelo físico, debemos recuperar la
entrada original. Un upscaler generativo falla este test; el nuestro no
puede fallarlo. Esta comprobación no es opcional: es el producto.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from scipy.signal import fftconvolve
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

RATIO_CONSISTENCIA_MAX = 1.5


@dataclass
class ResultadoConsistencia:
    rmse_residuo: float
    sigma_n: float
    ratio: float
    consistente: bool


@dataclass
class ResultadoDegradacion:
    psnr: float
    ssim: float
    psnr_bicubica: float
    ssim_bicubica: float
    mapa_diferencias: np.ndarray
    supera_bicubica: bool


def _decimar(img: np.ndarray, factor: float) -> np.ndarray:
    h, w = img.shape[:2]
    h_baja, w_baja = int(round(h / factor)), int(round(w / factor))
    interpolacion = cv2.INTER_AREA  # promedio de área = modelo de decimación D
    return cv2.resize(img, (w_baja, h_baja), interpolation=interpolacion)


def _convolucionar(img: np.ndarray, psf: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return np.stack(
            [fftconvolve(img[..., c], psf, mode="same") for c in range(img.shape[2])], axis=-1
        )
    return fftconvolve(img, psf, mode="same")


def degradar(x_est: np.ndarray, psf: np.ndarray, factor: float, forma_objetivo: tuple[int, int] | None = None) -> np.ndarray:
    """Aplica el modelo directo y_rep = D(H(x_est)): la misma degradación
    física (borroneo + decimación) que produjo la entrada capturada.
    """
    borrosa = _convolucionar(np.asarray(x_est, dtype=np.float64), psf)
    y_rep = _decimar(borrosa.astype(np.float32), factor)

    if forma_objetivo is not None and y_rep.shape[:2] != forma_objetivo:
        y_rep = cv2.resize(y_rep, (forma_objetivo[1], forma_objetivo[0]), interpolation=cv2.INTER_AREA)
    return y_rep


def consistencia_reproyeccion(
    x_est: np.ndarray, y_orig: np.ndarray, psf: np.ndarray, factor: float, sigma_n: float | None = None
) -> ResultadoConsistencia:
    """
    Degrada la estimación con el mismo modelo físico y la compara con la
    entrada original: y_rep = D(H(x_est)); residuo = ||y_rep - y_orig||.
    Si residuo ≈ nivel de ruido → la salida es consistente con los datos.
    Si residuo >> ruido → se inventó información. FALLO.
    """
    y_rep = degradar(x_est, psf, factor, forma_objetivo=y_orig.shape[:2])

    residuo = y_rep.astype(np.float64) - y_orig.astype(np.float64)
    rmse_residuo = float(np.sqrt(np.mean(residuo**2)))

    if sigma_n is None:
        from .io_img import estimar_sigma_ruido

        gris = cv2.cvtColor(y_orig.astype(np.float32), cv2.COLOR_RGB2GRAY) if y_orig.ndim == 3 else y_orig
        sigma_n = estimar_sigma_ruido(gris)

    sigma_n = max(float(sigma_n), 1e-6)
    ratio = rmse_residuo / sigma_n
    consistente = ratio < RATIO_CONSISTENCIA_MAX

    return ResultadoConsistencia(
        rmse_residuo=rmse_residuo, sigma_n=sigma_n, ratio=ratio, consistente=consistente
    )


def prueba_degradacion(
    img_alta_res: np.ndarray, factor: float, psf: np.ndarray, pipeline_reconstruccion
) -> ResultadoDegradacion:
    """Degrada una imagen HR conocida (H y luego D), la reconstruye con el
    pipeline y compara contra el original. También compara contra la línea
    base de interpolación bicúbica.
    """
    borrosa = _convolucionar(img_alta_res.astype(np.float64), psf).astype(np.float32)
    y_baja = _decimar(borrosa, factor)

    reconstruida = pipeline_reconstruccion(y_baja)
    if reconstruida.shape[:2] != img_alta_res.shape[:2]:
        reconstruida = cv2.resize(
            reconstruida, (img_alta_res.shape[1], img_alta_res.shape[0]), interpolation=cv2.INTER_CUBIC
        )

    bicubica = cv2.resize(
        y_baja, (img_alta_res.shape[1], img_alta_res.shape[0]), interpolation=cv2.INTER_CUBIC
    )

    rango = 1.0
    psnr = float(peak_signal_noise_ratio(img_alta_res, reconstruida, data_range=rango))
    psnr_bicubica = float(peak_signal_noise_ratio(img_alta_res, bicubica, data_range=rango))

    canal_eje = 2 if img_alta_res.ndim == 3 else None
    ssim = float(
        structural_similarity(
            img_alta_res, reconstruida, data_range=rango, channel_axis=canal_eje
        )
    )
    ssim_bicubica = float(
        structural_similarity(
            img_alta_res, bicubica, data_range=rango, channel_axis=canal_eje
        )
    )

    mapa_diferencias = np.abs(img_alta_res.astype(np.float32) - reconstruida.astype(np.float32))

    return ResultadoDegradacion(
        psnr=psnr,
        ssim=ssim,
        psnr_bicubica=psnr_bicubica,
        ssim_bicubica=ssim_bicubica,
        mapa_diferencias=mapa_diferencias,
        supera_bicubica=psnr > psnr_bicubica and ssim > ssim_bicubica,
    )
