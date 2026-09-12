"""
E2 — ¿El certificado predice el error?

Ver METODO.md §3 (E2) y §2 (las dos métricas) para la especificación
completa. Reutiliza el modelo directo y la reconstrucción de
experimentos/E1_deconvolucion/nucleo.py (mismo σ_psf, factor, σ_ruido —
E2 no vuelve a inventar el modelo, prueba si el CERTIFICADO de ese modelo
predice el error real).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

# Carga explícita por ruta (no sys.path + import normal): los dos
# experimentos tienen un módulo "nucleo.py" cada uno, y un import por nombre
# colisiona entre ellos.
_ruta_e1 = Path(__file__).resolve().parent.parent / "E1_deconvolucion" / "nucleo.py"
_spec = importlib.util.spec_from_file_location("e1_deconvolucion_nucleo", _ruta_e1)
_e1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_e1)

cargar_gris_lineal = _e1.cargar_gris_lineal
degradar = _e1.degradar
richardson_lucy_sr = _e1.richardson_lucy_sr
banda_recuperada = _e1.banda_recuperada


def _mascara_rango(forma: tuple[int, int], f_c: float) -> np.ndarray:
    """True donde la frecuencia (normalizada al Nyquist de ESTA región) está
    por debajo del corte f_c. f_c es una fracción de Nyquist (0-1), así que
    es válida sin importar el tamaño de la región: el Nyquist normalizado
    corresponde siempre al mismo 0.5 ciclos/píxel físico."""
    h, w = forma
    cy, cx = h // 2, w // 2
    y, x = np.indices(forma)
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    r_nyquist = max(min(cx, cy), 1)
    return (r / r_nyquist) <= f_c


def descomponer_rango_nucleo(region: np.ndarray, f_c: float) -> tuple[float, float]:
    """Descomposición rango-núcleo OPERATIVA (METODO.md §2): no es una SVD
    exacta del operador, es un corte en frecuencia al nivel de corte
    recuperable de la imagen. 'rango' = lo que los datos sostienen; 'núcleo'
    = lo que está más allá de ese límite (relleno del algoritmo, sin
    respaldo directo de la medición)."""
    F = np.fft.fftshift(np.fft.fft2(region))
    en_rango = _mascara_rango(region.shape, f_c)
    norma_rango = float(np.sqrt(np.sum(np.abs(F[en_rango]) ** 2)))
    norma_nucleo = float(np.sqrt(np.sum(np.abs(F[~en_rango]) ** 2)))
    return norma_rango, norma_nucleo


def tau_frecuencia(region: np.ndarray, f_c: float, eps: float = 1e-8) -> float:
    """Primera versión de τ probada (avance-1.4): dio correlación NEGATIVA
    con el error real (-0.42, hasta -0.92 por imagen). Se queda en el
    código como referencia y para que el test que documenta el hallazgo
    siga corriendo — no usar esto para el veredicto de la puerta."""
    norma_rango, norma_nucleo = descomponer_rango_nucleo(region, f_c)
    return norma_nucleo / max(norma_rango, eps)


def reconstrucciones_bootstrap(
    x_verdad: np.ndarray,
    sigma_psf: float,
    factor: int,
    sigma_ruido: float,
    k: int,
    rng: np.random.Generator,
):
    """K reconstrucciones de la MISMA escena con K realizaciones de ruido
    independientes — no es una medición sobre una sola imagen, es la base
    para medir cuánto cambia la reconstrucción si el ruido hubiera caído
    distinto. Devuelve un arreglo (k, H, W) y el kernel usado."""
    reconstrucciones = []
    kernel = None
    for _ in range(k):
        y, kernel = degradar(x_verdad, sigma_psf, factor, sigma_ruido, rng)
        x_rl, _ = richardson_lucy_sr(y, kernel, factor, x_verdad.shape, sigma_ruido)
        reconstrucciones.append(x_rl)
    return np.stack(reconstrucciones), kernel


def tau_incertidumbre(reconstrucciones: np.ndarray, y0: int, x0: int, tam: int, eps: float = 1e-6) -> float:
    """τ operacionalizado como sensibilidad al ruido, NORMALIZADA por la
    estructura local: RMS de la desviación estándar entre reconstrucciones
    (misma escena, ruido distinto), dividida por la desviación estándar de
    la reconstrucción media en esa región (cuánto contraste/estructura real
    hay ahí).

    Sin normalizar por la estructura local, esta métrica cae en la MISMA
    trampa que tau_frecuencia (avance-1.4): la dispersión absoluta entre
    reconstrucciones escala con el contraste local (una zona con textura
    fuerte tiene más variación absoluta simplemente porque hay más señal),
    así que sin normalizar termina midiendo "cuánto detalle hay" otra vez,
    no "cuánta confianza hay". Como cociente (coeficiente de variación) sí
    apunta a lo que importa: cuán grande es la incertidumbre RELATIVA a la
    estructura real que el algoritmo cree haber encontrado ahí."""
    parche = reconstrucciones[:, y0 : y0 + tam, x0 : x0 + tam]
    dispersion = np.sqrt(parche.var(axis=0).mean())
    estructura_local = parche.mean(axis=0).std()
    return float(dispersion / max(estructura_local, eps))


def error_rms(region_estimado: np.ndarray, region_verdad: np.ndarray) -> float:
    return float(np.sqrt(np.mean((region_estimado - region_verdad) ** 2)))


def _rango_de_valores(a: np.ndarray) -> np.ndarray:
    """Rango (posición al ordenar) de cada valor — ties poco probables con
    floats continuos, así que no hace falta el promedio de empates de
    scipy.stats.rankdata."""
    return np.argsort(np.argsort(a)).astype(np.float64)


def correlacion_spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = _rango_de_valores(np.asarray(a)), _rango_de_valores(np.asarray(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def regiones(forma: tuple[int, int], tam_region: int):
    h, w = forma
    for y0 in range(0, h - tam_region + 1, tam_region):
        for x0 in range(0, w - tam_region + 1, tam_region):
            yield y0, x0
