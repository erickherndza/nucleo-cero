import numpy as np
from scipy.signal import fftconvolve

from uppimagen import deconv, psf as psf_mod


def test_richardson_lucy_tv_recupera_nitidez():
    original = np.zeros((64, 64), dtype=np.float32)
    original[20:44, 20:44] = 1.0

    kernel = psf_mod._kernel_gaussiano(1.5)
    borrosa = fftconvolve(original, kernel, mode="same").astype(np.float32)

    restaurada = deconv.richardson_lucy_tv(borrosa, kernel, iters=25, lam=0.001)

    # La restauración debe acercarse más al original que la imagen borrosa.
    error_borroso = np.mean((borrosa - original) ** 2)
    error_restaurado = np.mean((restaurada - original) ** 2)
    assert error_restaurado < error_borroso


def test_richardson_lucy_tv_no_produce_negativos_ni_nan():
    rng = np.random.default_rng(0)
    img = rng.random((32, 32)).astype(np.float32)
    kernel = psf_mod._kernel_gaussiano(1.0)

    restaurada = deconv.richardson_lucy_tv(img, kernel, iters=10)

    assert np.isfinite(restaurada).all()
    assert np.all(restaurada >= 0.0)
    assert np.all(restaurada <= 1.0)


def test_wiener_reduce_desenfoque():
    original = np.zeros((64, 64), dtype=np.float32)
    original[20:44, 20:44] = 1.0
    kernel = psf_mod._kernel_gaussiano(1.5)
    borrosa = fftconvolve(original, kernel, mode="same").astype(np.float32)

    restaurada = deconv.wiener(borrosa, kernel, sigma_n=0.01)

    error_borroso = np.mean((borrosa - original) ** 2)
    error_restaurado = np.mean((restaurada - original) ** 2)
    assert error_restaurado < error_borroso
