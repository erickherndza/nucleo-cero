"""Orquestador del pipeline: carga → PSF → alinear → (fusionar) →
deconvolucionar → verificar fidelidad → guardar + informe.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import align, deconv, fidelity, io_img, merge, psf as psf_mod, tiling

FACTOR_MAXIMO = 2.0
FACTOR_MAXIMO_JPEG_UNICO = 1.5
FACTOR_MAXIMO_UN_FRAME = 1.5


@dataclass
class Resultado:
    ruta_salida: str | None
    metricas_fidelidad: fidelity.ResultadoConsistencia | None
    factor_alcanzado: float
    avisos: list[str] = field(default_factory=list)
    tiempo_segundos: float = 0.0
    imagen: np.ndarray | None = None


def _escalar_tile(factor: float):
    """Función de tile que reescala por `factor` con interpolación cúbica.

    El tamaño de destino se calcula con la MISMA fórmula que usa
    `tiling.procesar_por_tiles` para el tile de salida, así el resultado
    siempre coincide con lo que espera el ensamblador.
    """

    def _escalar(tile: np.ndarray) -> np.ndarray:
        alto_salida = int(round(tile.shape[0] * factor))
        ancho_salida = int(round(tile.shape[1] * factor))
        return cv2.resize(tile, (ancho_salida, alto_salida), interpolation=cv2.INTER_CUBIC)

    return _escalar


def _retroproyeccion_iterativa(
    x_est: np.ndarray,
    y_orig: np.ndarray,
    psf: np.ndarray,
    factor: float,
    iters: int = 20,
    paso: float = 1.2,
    tol_residuo: float = 1e-4,
) -> np.ndarray:
    """Retroproyección iterativa (Irani & Peleg, 1991): corrige x̂ para que
    al degradarlo con el mismo modelo físico reproduzca mejor la entrada.

    La deconvolución sola no garantiza consistencia porque el upscale
    inicial (interpolación) y la degradación D·H no son operadores
    exactamente inversos. Este paso cierra ese hueco iterando
    x̂ += paso · upsample(y − D(H(x̂))), es decir, sigue corrigiendo con la
    MISMA entrada real hasta que la reproyección la reproduce dentro del
    ruido — nunca añade información que no esté ya en `y_orig`.
    """
    x = np.asarray(x_est, dtype=np.float32).copy()
    forma_objetivo = y_orig.shape[:2]
    residuo_anterior = None

    for _ in range(max(1, iters)):
        y_rep = fidelity.degradar(x, psf, factor, forma_objetivo=forma_objetivo)
        residuo_bajo_res = y_orig.astype(np.float32) - y_rep

        rmse = float(np.sqrt(np.mean(residuo_bajo_res**2)))
        if residuo_anterior is not None and (residuo_anterior - rmse) < tol_residuo * max(residuo_anterior, 1e-8):
            break
        residuo_anterior = rmse

        correccion = cv2.resize(
            residuo_bajo_res, (x.shape[1], x.shape[0]), interpolation=cv2.INTER_CUBIC
        )
        x = np.clip(x + paso * correccion, 0.0, 1.0).astype(np.float32)

    return x


def _factor_maximo_permitido(metadatos_frames: list[io_img.Metadatos], n_frames: int) -> float:
    if n_frames == 1:
        origen = metadatos_frames[0].origen
        if origen == "ldr":
            return FACTOR_MAXIMO_JPEG_UNICO
        return FACTOR_MAXIMO_UN_FRAME
    return FACTOR_MAXIMO


def procesar(
    rutas: list[str],
    factor: float = 2.0,
    salida: str | None = None,
    perfil: str = "equilibrado",
) -> Resultado:
    inicio = time.time()
    avisos: list[str] = []

    frames, metadatos = [], []
    for ruta in rutas:
        img, meta = io_img.cargar(ruta)
        frames.append(img)
        metadatos.append(meta)

    factor_max = _factor_maximo_permitido(metadatos, len(frames))
    if factor > factor_max:
        avisos.append(
            f"Factor solicitado {factor}x reducido a {factor_max}x: "
            f"el límite real para esta entrada no permite más."
        )
        factor = factor_max
    factor = min(factor, FACTOR_MAXIMO)

    referencia = frames[0]
    psf = psf_mod.estimar_psf(referencia)
    sigma_n = float(np.median([m.sigma_n for m in metadatos]))

    if len(frames) > 1:
        alineados, transformadas = align.alinear(frames)
        # El lienzo HR queda en el sistema de coordenadas del frame más
        # nítido (el que align.alinear elige como referencia interna), que
        # no siempre es frames[0]: la verificación de fidelidad debe
        # compararse contra ESE frame, no contra el primero de la lista.
        idx_ref = next((i for i, t in enumerate(transformadas) if t.es_referencia), 0)
        referencia = frames[idx_ref]
        n_rechazados = sum(1 for t in transformadas if not t.aceptado)
        if n_rechazados:
            avisos.append(f"{n_rechazados} frame(s) descartado(s) por desplazamiento, nitidez o correlación.")

        info_fases = align.distribucion_fases(transformadas)
        if not info_fases["hay_informacion_nueva"]:
            avisos.append(
                "Los frames caen en fases sub-píxel muy similares: no hay información nueva "
                "que desdoblar. La ganancia real del burst será limitada."
            )

        if len(alineados) < 2:
            avisos.append("Menos de 2 frames válidos tras alinear: se procesa como frame único.")
            factor = min(factor, FACTOR_MAXIMO_UN_FRAME)
            hr = tiling.procesar_por_tiles(
                alineados[0] if alineados else referencia, _escalar_tile(factor), factor=factor
            )
        else:
            nitideces = [t.nitidez for t in transformadas if t.aceptado]
            matrices = [t.matriz for t in transformadas if t.aceptado]
            resultado_fusion = merge.fusionar(alineados, matrices, nitideces, factor=factor)
            hr = resultado_fusion.hr
            if resultado_fusion.fraccion_sin_cobertura > 0.01:
                avisos.append(
                    f"{resultado_fusion.fraccion_sin_cobertura * 100:.1f}% de la imagen sin cobertura "
                    "directa de los frames; rellenado por interpolación."
                )
    else:
        hr = tiling.procesar_por_tiles(referencia, _escalar_tile(factor), factor=factor)

    lam = 0.002 * max(sigma_n, 1e-4) / 0.01

    def _deconvolucionar_tile(tile: np.ndarray) -> np.ndarray:
        return deconv.richardson_lucy_tv(tile, psf, iters=20, lam=lam)

    restaurada = tiling.procesar_por_tiles(hr, _deconvolucionar_tile, factor=1.0)
    restaurada = _retroproyeccion_iterativa(np.asarray(restaurada), referencia, psf, factor)

    metricas = fidelity.consistencia_reproyeccion(
        np.asarray(restaurada), referencia, psf, factor=factor, sigma_n=sigma_n
    )
    if not metricas.consistente:
        avisos.append(
            f"El resultado NO pasó el test de consistencia (ratio={metricas.ratio:.2f} "
            f">= {fidelity.RATIO_CONSISTENCIA_MAX}). Puede haber información inventada."
        )

    ruta_salida = None
    if salida:
        ruta_salida = salida
        io_img.guardar(ruta_salida, np.asarray(restaurada))

    return Resultado(
        ruta_salida=ruta_salida,
        metricas_fidelidad=metricas,
        factor_alcanzado=factor,
        avisos=avisos,
        tiempo_segundos=time.time() - inicio,
        imagen=np.asarray(restaurada),
    )
