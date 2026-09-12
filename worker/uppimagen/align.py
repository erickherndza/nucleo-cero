"""Alineación sub-píxel de un burst de frames.

Aquí es donde se recupera información real: cada frame muestrea una fase
sub-píxel distinta de la escena, y la precisión de la alineación determina
cuánta de esa información se puede desdoblar en `merge.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

UMBRAL_DESPLAZAMIENTO_FRACCION = 0.03  # 3% de la dimensión
UMBRAL_NITIDEZ_RELATIVA = 0.60
UMBRAL_ECC = 0.3
# La estimación sub-píxel (ECC) tiene ruido típico de ~0.1-0.2 px incluso
# para desplazamientos puramente enteros; el umbral debe ser mayor que ese
# ruido para no confundirlo con fases realmente distintas.
UMBRAL_DISPERSION_FASES = 0.15


@dataclass
class TransformadaFrame:
    """Transformada de un frame respecto al de referencia."""

    matriz: np.ndarray  # 2x3 (Euclidiana/Afín) o 3x3 (Homografía)
    modo: str  # "euclidiana" | "homografia"
    nitidez: float
    correlacion_ecc: float
    desplazamiento_px: tuple[float, float]
    aceptado: bool
    motivo_rechazo: str = ""
    es_referencia: bool = False


def _a_gris(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        return cv2.cvtColor(frame.astype(np.float32), cv2.COLOR_RGB2GRAY)
    return frame.astype(np.float32)


def _nitidez_laplaciano(gris: np.ndarray) -> float:
    return float(cv2.Laplacian(gris.astype(np.float64), cv2.CV_64F).var())


def _elegir_referencia(grises: list[np.ndarray]) -> int:
    nitideces = [_nitidez_laplaciano(g) for g in grises]
    return int(np.argmax(nitideces))


def _matriz_identidad(modo: str) -> np.ndarray:
    if modo == "homografia":
        return np.eye(3, dtype=np.float32)
    return np.eye(2, 3, dtype=np.float32)


def _alinear_par(
    ref: np.ndarray, mov: np.ndarray, modo: str
) -> tuple[np.ndarray, float]:
    """Alinea `mov` contra `ref`: fase-correlación gruesa + ECC fino."""
    # 1. Grueso: phase correlation.
    ventana = cv2.createHanningWindow(ref.shape[::-1], cv2.CV_32F)
    (dx, dy), _ = cv2.phaseCorrelate(ref * ventana, mov * ventana)

    matriz = _matriz_identidad(modo)
    matriz[0, 2] += dx
    matriz[1, 2] += dy

    # Pirámide gaussiana para robustez del ECC fino.
    niveles = 3
    ref_piramide = [ref]
    mov_piramide = [mov]
    for _ in range(niveles - 1):
        ref_piramide.append(cv2.pyrDown(ref_piramide[-1]))
        mov_piramide.append(cv2.pyrDown(mov_piramide[-1]))

    modo_cv = cv2.MOTION_HOMOGRAPHY if modo == "homografia" else cv2.MOTION_EUCLIDEAN
    criterio = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-6)

    correlacion = 0.0
    for nivel in reversed(range(niveles)):
        escala = 2.0**nivel
        m = matriz.copy()
        m[0, 2] /= escala
        m[1, 2] /= escala
        try:
            correlacion, m = cv2.findTransformECC(
                ref_piramide[nivel],
                mov_piramide[nivel],
                m,
                modo_cv,
                criterio,
            )
        except cv2.error:
            # Este nivel de la pirámide no convergió (p.ej. poca textura a
            # baja resolución); se conserva la estimación previa y se sigue
            # afinando en los niveles más finos en vez de abortar.
            continue
        m[0, 2] *= escala
        m[1, 2] *= escala
        matriz = m

    return matriz, float(correlacion)


def alinear(
    frames: list[np.ndarray], modo: str = "euclidiana"
) -> tuple[list[np.ndarray], list[TransformadaFrame]]:
    """Alinea un burst de frames. Devuelve (frames_alineados, transformadas).

    Los frames rechazados no se incluyen en `frames_alineados`, pero sí
    aparecen en `transformadas` con `aceptado=False` para el informe.
    """
    if not frames:
        return [], []

    grises = [_a_gris(f) for f in frames]
    idx_ref = _elegir_referencia(grises)
    ref = grises[idx_ref]
    nitidez_ref = _nitidez_laplaciano(ref)
    h, w = ref.shape
    diagonal_max = max(h, w)

    alineados: list[np.ndarray] = []
    transformadas: list[TransformadaFrame] = []

    for i, frame in enumerate(frames):
        if i == idx_ref:
            matriz = _matriz_identidad(modo)
            transformadas.append(
                TransformadaFrame(
                    matriz=matriz,
                    modo=modo,
                    nitidez=nitidez_ref,
                    correlacion_ecc=1.0,
                    desplazamiento_px=(0.0, 0.0),
                    aceptado=True,
                    es_referencia=True,
                )
            )
            alineados.append(frame)
            continue

        gris = grises[i]
        nitidez = _nitidez_laplaciano(gris)
        matriz, correlacion = _alinear_par(ref, gris, modo)
        dx, dy = float(matriz[0, 2]), float(matriz[1, 2])
        desplazamiento = float(np.hypot(dx, dy))

        motivo_rechazo = ""
        if desplazamiento > UMBRAL_DESPLAZAMIENTO_FRACCION * diagonal_max:
            motivo_rechazo = "desplazamiento excesivo (no es temblor de mano)"
        elif nitidez < UMBRAL_NITIDEZ_RELATIVA * nitidez_ref:
            motivo_rechazo = "nitidez muy por debajo del frame de referencia"
        elif correlacion < UMBRAL_ECC:
            motivo_rechazo = "correlación ECC por debajo del umbral"

        aceptado = motivo_rechazo == ""
        transformadas.append(
            TransformadaFrame(
                matriz=matriz,
                modo=modo,
                nitidez=nitidez,
                correlacion_ecc=correlacion,
                desplazamiento_px=(dx, dy),
                aceptado=aceptado,
                motivo_rechazo=motivo_rechazo,
            )
        )
        if aceptado:
            alineados.append(frame)

    return alineados, transformadas


def distribucion_fases(transformadas: list[TransformadaFrame]) -> dict:
    """Analiza si las partes fraccionarias de los desplazamientos están bien
    distribuidas. Si todos los frames caen en la misma fase sub-píxel, no hay
    información nueva que desdoblar.
    """
    aceptadas = [t for t in transformadas if t.aceptado]
    if len(aceptadas) < 2:
        return {"hay_informacion_nueva": False, "fases_x": [], "fases_y": [], "dispersion": 0.0}

    fases_x = [t.desplazamiento_px[0] % 1.0 for t in aceptadas]
    fases_y = [t.desplazamiento_px[1] % 1.0 for t in aceptadas]

    # Dispersión circular simple: desviación estándar de las fases en [0,1).
    dispersion = float(np.std(fases_x) + np.std(fases_y))
    hay_informacion_nueva = dispersion > UMBRAL_DISPERSION_FASES

    return {
        "hay_informacion_nueva": hay_informacion_nueva,
        "fases_x": fases_x,
        "fases_y": fases_y,
        "dispersion": dispersion,
    }
