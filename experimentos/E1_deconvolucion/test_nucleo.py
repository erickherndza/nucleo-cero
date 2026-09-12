import numpy as np

from nucleo import (
    adjunto_decimar_promedio,
    banda_recuperada,
    bicubica_hasta,
    convolucionar,
    decimar_promedio,
    degradar,
    f_max_teorico,
    kernel_gaussiano,
    psnr,
    richardson_lucy_sr,
    espectro_radial,
    ssim,
)


def test_kernel_gaussiano_normalizado():
    k = kernel_gaussiano(1.5)
    assert np.isclose(k.sum(), 1.0)
    assert k.shape[0] == k.shape[1]
    assert k.shape[0] % 2 == 1


def test_convolucionar_preserva_dc():
    # convolucionar con un kernel normalizado no debe cambiar el nivel medio
    rng = np.random.default_rng(0)
    img = rng.uniform(0, 1, size=(64, 64))
    k = kernel_gaussiano(2.0)
    out = convolucionar(img, k)
    assert np.isclose(img.mean(), out.mean(), atol=1e-3)


def test_decimar_promedio_forma_y_valor():
    img = np.arange(16, dtype=np.float64).reshape(4, 4)
    d = decimar_promedio(img, 2)
    assert d.shape == (2, 2)
    # bloque superior-izquierdo: [[0,1],[4,5]] -> media 2.5
    assert np.isclose(d[0, 0], 2.5)


def test_adjunto_decimar_es_adjunto_real():
    """Prueba de producto punto: <D u, z> debe igualar <u, D^T z> para
    cualquier u, z — si esto falla, Richardson-Lucy converge mal aunque
    el código "corra sin error"."""
    rng = np.random.default_rng(1)
    factor = 4
    forma_hr = (32, 32)
    u = rng.uniform(0, 1, size=forma_hr)
    z = rng.uniform(0, 1, size=(forma_hr[0] // factor, forma_hr[1] // factor))

    Du = decimar_promedio(u, factor)
    DTz = adjunto_decimar_promedio(z, factor, forma_hr)

    izquierda = float(np.sum(Du * z))
    derecha = float(np.sum(u * DTz))
    assert np.isclose(izquierda, derecha, rtol=1e-8)


def test_psnr_identico_es_infinito():
    a = np.ones((8, 8))
    assert psnr(a, a) == float("inf")


def test_ssim_identico_es_uno():
    rng = np.random.default_rng(2)
    a = rng.uniform(0, 1, size=(64, 64))
    assert np.isclose(ssim(a, a), 1.0, atol=1e-6)


def test_espectro_radial_ruido_blanco_da_piso_correcto():
    """Validación de unidades: la PSD de ruido blanco de varianza conocida
    debe medir ~esa varianza, plana en todas las frecuencias. Sin dividir
    por H·W en espectro_radial esto sale ~H·W veces más grande — el bug
    real que hacía que banda_recuperada diera 0% en todas las imágenes."""
    rng = np.random.default_rng(3)
    sigma = 0.02
    ruido = rng.normal(0, sigma, size=(256, 256))
    freqs, psd = espectro_radial(ruido)
    # lejos de f=0 (donde el ruido también tiene su propia componente DC
    # aleatoria) la PSD debe rondar sigma², no sigma²*65536
    media_psd = np.mean(psd[freqs > 0.1])
    assert 0.5 * sigma**2 < media_psd < 2.0 * sigma**2


def test_f_max_teorico_baja_con_mas_blur():
    freqs = np.linspace(0, 1, 200)
    S = np.exp(-4 * freqs)  # espectro de verdad sintético, decae naturalmente
    f_poco_blur = f_max_teorico(freqs, S, sigma_psf=0.5, sigma_ruido=0.05)
    f_mucho_blur = f_max_teorico(freqs, S, sigma_psf=3.0, sigma_ruido=0.05)
    assert f_mucho_blur < f_poco_blur


def test_banda_recuperada_es_cero_si_no_se_reconstruye_nada():
    rng = np.random.default_rng(4)
    x_verdad = rng.uniform(0, 1, size=(64, 64))
    x_estimado = rng.uniform(0, 1, size=(64, 64))  # sin relación con la verdad
    f = banda_recuperada(x_estimado, x_verdad)
    assert f <= 0.05  # prácticamente nada más allá de la continua


def test_banda_recuperada_es_maxima_si_la_reconstruccion_es_perfecta():
    rng = np.random.default_rng(5)
    x_verdad = rng.uniform(0, 1, size=(64, 64))
    f = banda_recuperada(x_verdad.copy(), x_verdad)
    assert f == 1.0


def test_richardson_lucy_recupera_mejor_que_bicubica_en_caso_facil():
    """Caso de control: blur leve, ruido bajo, factor 2. RL debe acercarse
    más a la verdad que la sola interpolación bicúbica — si esto no se
    cumple aquí (el caso más fácil posible), algo del operador está mal."""
    rng = np.random.default_rng(42)
    tam = 64
    # imagen sintética con estructura de alta frecuencia real (a diferencia
    # de ruido blanco puro, que no tiene nada "recuperable" con sentido)
    eje = np.linspace(0, 4 * np.pi, tam)
    xx, yy = np.meshgrid(eje, eje)
    x_verdad = 0.5 + 0.4 * np.sin(xx) * np.cos(yy * 1.3)
    x_verdad = np.clip(x_verdad, 0, 1)

    sigma_psf, factor, sigma_ruido = 1.0, 2, 0.01
    y, kernel = degradar(x_verdad, sigma_psf, factor, sigma_ruido, rng)

    x_rl, iteraciones = richardson_lucy_sr(y, kernel, factor, x_verdad.shape, sigma_ruido)
    x_bicubica = bicubica_hasta(y, x_verdad.shape)

    psnr_rl = psnr(x_rl, x_verdad)
    psnr_bicubica = psnr(x_bicubica, x_verdad)
    assert psnr_rl > psnr_bicubica
    assert iteraciones < 30  # debe frenar por discrepancia, no agotar el máximo


def test_richardson_lucy_sin_parada_temprana_empeora():
    """Confirma el hallazgo: sin principio de discrepancia, más iteraciones
    de RL EMPEORAN el PSNR real (sobreajuste a ruido) aunque el residuo
    interno siga bajando. Si este test empieza a fallar, revisar si cambió
    el operador antes de asumir que "ya no pasa"."""
    rng = np.random.default_rng(42)
    tam = 64
    eje = np.linspace(0, 4 * np.pi, tam)
    xx, yy = np.meshgrid(eje, eje)
    x_verdad = np.clip(0.5 + 0.4 * np.sin(xx) * np.cos(yy * 1.3), 0, 1)

    sigma_psf, factor, sigma_ruido = 1.0, 2, 0.01
    y, kernel = degradar(x_verdad, sigma_psf, factor, sigma_ruido, rng)

    x_pocas, _ = richardson_lucy_sr(y, kernel, factor, x_verdad.shape, sigma_ruido, iteraciones_max=2)
    x_muchas, _ = richardson_lucy_sr(
        y, kernel, factor, x_verdad.shape, sigma_ruido, iteraciones_max=25, margen_discrepancia=0.0
    )
    assert psnr(x_pocas, x_verdad) > psnr(x_muchas, x_verdad)
