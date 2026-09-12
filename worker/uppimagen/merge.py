"""Fusión de un burst alineado en un lienzo de alta resolución.

Splatting con pesos (kernel regression): cada píxel de cada frame reparte su
valor sobre los vecinos del lienzo HR con un kernel gaussiano, ponderado por
robustez (contra fantasmas de objetos en movimiento) y nitidez del frame.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

RADIO_KERNEL_HR = 1.0  # px en el lienzo HR
UMBRAL_MAD_ROBUSTEZ = 3.0
EPS_DENOMINADOR = 1e-6
UMBRAL_COBERTURA_BAJA = 0.15  # fracción del peso máximo esperado


@dataclass
class ResultadoFusion:
    hr: np.ndarray
    mascara_cobertura: np.ndarray  # True donde la cobertura es baja/nula
    fraccion_sin_cobertura: float


def _transformar_puntos(matriz: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Aplica una transformada 2x3 o 3x3 a un conjunto de puntos (x, y)."""
    puntos = np.stack([xs, ys, np.ones_like(xs)], axis=0)
    if matriz.shape[0] == 2:
        out = matriz @ puntos
        return out[0], out[1]
    out = matriz @ puntos
    out = out / np.where(np.abs(out[2]) < 1e-12, 1e-12, out[2])
    return out[0], out[1]


def _pesos_robustez(frames_alineados: list[np.ndarray]) -> list[np.ndarray]:
    """Peso por píxel según desviación robusta (mediana + MAD) entre frames.

    Evita fantasmas de objetos en movimiento sin inventar contenido: los
    píxeles que se desvían mucho de la mediana temporal reciben peso bajo.
    """
    if len(frames_alineados) < 2:
        return [np.ones(frames_alineados[0].shape[:2], dtype=np.float32)] if frames_alineados else []

    pila = np.stack(frames_alineados, axis=0)  # (N, H, W, C) o (N, H, W)
    mediana = np.median(pila, axis=0)
    mad = np.median(np.abs(pila - mediana), axis=0) + EPS_DENOMINADOR

    pesos = []
    for frame in frames_alineados:
        desvio = np.abs(frame - mediana) / mad
        if desvio.ndim == 3:
            desvio = desvio.mean(axis=2)
        peso = np.clip(1.0 - (desvio / UMBRAL_MAD_ROBUSTEZ), 0.0, 1.0)
        pesos.append(peso.astype(np.float32))
    return pesos


def fusionar(
    frames_alineados: list[np.ndarray],
    matrices: list[np.ndarray],
    nitideces: list[float],
    factor: float,
) -> ResultadoFusion:
    """Fusiona el burst alineado en un lienzo HR de tamaño (H*factor, W*factor)."""
    if not frames_alineados:
        raise ValueError("No hay frames para fusionar")

    h, w = frames_alineados[0].shape[:2]
    canales = frames_alineados[0].shape[2] if frames_alineados[0].ndim == 3 else 1
    h_hr, w_hr = int(round(h * factor)), int(round(w * factor))

    if canales > 1:
        num = np.zeros((h_hr, w_hr, canales), dtype=np.float64)
    else:
        num = np.zeros((h_hr, w_hr), dtype=np.float64)
    den = np.zeros((h_hr, w_hr), dtype=np.float64)

    pesos_robustez = _pesos_robustez(frames_alineados)
    nitidez_max = max(nitideces) if nitideces else 1.0
    radio = max(1, int(np.ceil(2 * RADIO_KERNEL_HR)))

    ys_frame, xs_frame = np.mgrid[0:h, 0:w]
    xs_frame = xs_frame.astype(np.float64).ravel()
    ys_frame = ys_frame.astype(np.float64).ravel()

    for frame, matriz, w_nitidez_frame, w_robustez_mapa in zip(
        frames_alineados, matrices, [n / nitidez_max for n in nitideces], pesos_robustez
    ):
        xs_hr, ys_hr = _transformar_puntos(matriz, xs_frame, ys_frame)
        xs_hr *= factor
        ys_hr *= factor

        valores = frame.reshape(-1, canales) if canales > 1 else frame.reshape(-1)
        w_robustez = w_robustez_mapa.ravel()

        ix0 = np.floor(xs_hr).astype(np.int64)
        iy0 = np.floor(ys_hr).astype(np.int64)

        for oy in range(-radio, radio + 1):
            for ox in range(-radio, radio + 1):
                px = ix0 + ox
                py = iy0 + oy
                dentro = (px >= 0) & (px < w_hr) & (py >= 0) & (py < h_hr)
                if not np.any(dentro):
                    continue

                dx = xs_hr[dentro] - px[dentro]
                dy = ys_hr[dentro] - py[dentro]
                dist2 = dx * dx + dy * dy
                w_gauss = np.exp(-0.5 * dist2 / (RADIO_KERNEL_HR**2))

                peso_total = w_gauss * w_robustez[dentro] * w_nitidez_frame
                idx_lineal = py[dentro] * w_hr + px[dentro]

                if canales > 1:
                    for c in range(canales):
                        np.add.at(
                            num.reshape(-1, canales)[:, c],
                            idx_lineal,
                            valores[dentro, c] * peso_total,
                        )
                else:
                    np.add.at(num.reshape(-1), idx_lineal, valores[dentro] * peso_total)
                np.add.at(den.reshape(-1), idx_lineal, peso_total)

    den_seguro = np.maximum(den, EPS_DENOMINADOR)
    if canales > 1:
        hr = num / den_seguro[..., None]
    else:
        hr = num / den_seguro

    peso_esperado = len(frames_alineados) * (2 * radio + 1) ** 2 * 0.05
    mascara_baja_cobertura = den < max(UMBRAL_COBERTURA_BAJA * peso_esperado, EPS_DENOMINADOR * 10)

    if np.any(mascara_baja_cobertura):
        hr_rellena = hr.astype(np.float32)
        if canales > 1:
            for c in range(canales):
                canal = hr_rellena[..., c]
                canal_relleno = cv2.inpaint(
                    np.clip(canal * 255, 0, 255).astype(np.uint8),
                    mascara_baja_cobertura.astype(np.uint8),
                    3,
                    cv2.INPAINT_TELEA,
                )
                hr_rellena[..., c] = np.where(
                    mascara_baja_cobertura, canal_relleno.astype(np.float32) / 255.0, canal
                )
        else:
            canal_relleno = cv2.inpaint(
                np.clip(hr_rellena * 255, 0, 255).astype(np.uint8),
                mascara_baja_cobertura.astype(np.uint8),
                3,
                cv2.INPAINT_TELEA,
            )
            hr_rellena = np.where(
                mascara_baja_cobertura, canal_relleno.astype(np.float32) / 255.0, hr_rellena
            )
        hr = hr_rellena

    fraccion_sin_cobertura = float(np.mean(mascara_baja_cobertura))

    return ResultadoFusion(
        hr=hr.astype(np.float32),
        mascara_cobertura=mascara_baja_cobertura,
        fraccion_sin_cobertura=fraccion_sin_cobertura,
    )
