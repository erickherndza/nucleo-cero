import cv2
import numpy as np

from uppimagen import fidelity, psf as psf_mod


def _imagen_sintetica(tamano=128, seed=0):
    rng = np.random.default_rng(seed)
    img = np.zeros((tamano, tamano), dtype=np.float32)
    for _ in range(15):
        x0, y0 = rng.integers(0, tamano, 2)
        r = rng.integers(5, 20)
        cv2.circle(img, (int(x0), int(y0)), int(r), float(rng.random()), -1)
    return img


def test_consistencia_reproyeccion_pasa_para_estimacion_correcta():
    kernel = psf_mod._kernel_gaussiano(1.0)
    x_real = _imagen_sintetica()

    from scipy.signal import fftconvolve

    borrosa = fftconvolve(x_real, kernel, mode="same").astype(np.float32)
    y = cv2.resize(borrosa, (64, 64), interpolation=cv2.INTER_AREA)

    # La "estimación" es el propio x_real: al reproyectarlo debe recuperar y
    # casi exactamente (sin ruido inyectado).
    resultado = fidelity.consistencia_reproyeccion(x_real, y, kernel, factor=2.0, sigma_n=0.01)

    assert resultado.consistente
    assert resultado.ratio < fidelity.RATIO_CONSISTENCIA_MAX


def test_consistencia_reproyeccion_falla_si_se_inventa_detalle():
    kernel = psf_mod._kernel_gaussiano(1.0)
    x_real = _imagen_sintetica()

    from scipy.signal import fftconvolve

    borrosa = fftconvolve(x_real, kernel, mode="same").astype(np.float32)
    y = cv2.resize(borrosa, (64, 64), interpolation=cv2.INTER_AREA)

    # Estimación "alucinada": ruido de alta frecuencia inventado, no derivado de y.
    rng = np.random.default_rng(1)
    x_alucinado = np.clip(x_real + rng.normal(0, 0.3, x_real.shape).astype(np.float32), 0, 1)

    resultado = fidelity.consistencia_reproyeccion(x_alucinado, y, kernel, factor=2.0, sigma_n=0.01)

    assert not resultado.consistente
    assert resultado.ratio >= fidelity.RATIO_CONSISTENCIA_MAX


def test_prueba_degradacion_supera_bicubica_con_pipeline_perfecto():
    kernel = psf_mod._kernel_gaussiano(1.0)
    x_real = _imagen_sintetica(tamano=96)

    def pipeline_oraculo(y_baja):
        # Un "pipeline" que hace trampa y devuelve el original: sirve para
        # verificar que la métrica identifica correctamente una mejora real.
        return x_real

    resultado = fidelity.prueba_degradacion(x_real, factor=2.0, psf=kernel, pipeline_reconstruccion=pipeline_oraculo)

    assert resultado.supera_bicubica
    assert resultado.psnr > resultado.psnr_bicubica
