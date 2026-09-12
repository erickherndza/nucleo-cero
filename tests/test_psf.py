import numpy as np

from uppimagen import psf


def test_kernel_gaussiano_normalizado():
    k = psf._kernel_gaussiano(1.5)
    assert k.ndim == 2
    np.testing.assert_allclose(k.sum(), 1.0, atol=1e-5)
    assert np.all(k >= 0)


def test_kernel_gaussiano_mas_ancho_con_mas_sigma():
    k_estrecho = psf._kernel_gaussiano(0.5, radio=10)
    k_ancho = psf._kernel_gaussiano(3.0, radio=10)
    centro = 10
    assert k_ancho[centro, centro] < k_estrecho[centro, centro]


def test_estimar_psf_fallback_sin_bordes():
    # Imagen plana con ruido leve: sin bordes utilizables -> debe caer al fallback.
    rng = np.random.default_rng(0)
    img = 0.5 + rng.normal(0, 0.001, (64, 64)).astype(np.float32)
    kernel = psf.estimar_psf(img, metodo="esf")
    np.testing.assert_allclose(kernel.sum(), 1.0, atol=1e-5)
    centro = kernel.shape[0] // 2
    # sigma fallback = 0.8 -> el pico central debe corresponder a ese kernel
    esperado = psf._kernel_gaussiano(psf.SIGMA_FALLBACK, radio=centro)
    np.testing.assert_allclose(kernel, esperado, atol=1e-4)


def test_estimar_psf_recupera_sigma_de_borde_sintetico():
    from scipy.ndimage import gaussian_filter

    img = np.zeros((200, 200), dtype=np.float32)
    img[:, 100:] = 1.0
    sigma_real = 1.2
    img_borrosa = gaussian_filter(img, sigma_real)

    kernel = psf.estimar_psf(img_borrosa, metodo="esf")
    centro = kernel.shape[0] // 2
    # El sigma recuperado debe ser razonablemente cercano al real.
    perfil = kernel[centro, :]
    varianza = np.sum(perfil * (np.arange(len(perfil)) - centro) ** 2)
    sigma_estimado = np.sqrt(varianza)
    assert abs(sigma_estimado - sigma_real) < 0.6
