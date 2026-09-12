import numpy as np
import pytest

from uppimagen import io_img


def test_srgb_lineal_roundtrip():
    valores = np.linspace(0, 1, 257, dtype=np.float32)
    lineal = io_img._srgb_a_lineal(valores)
    de_vuelta = io_img._lineal_a_srgb(lineal)
    np.testing.assert_allclose(de_vuelta, valores, atol=1e-4)


def test_srgb_a_lineal_es_monotona_y_acotada():
    valores = np.linspace(0, 1, 100, dtype=np.float32)
    lineal = io_img._srgb_a_lineal(valores)
    assert np.all(lineal >= 0.0) and np.all(lineal <= 1.0)
    assert np.all(np.diff(lineal) >= 0)


def test_srgb_a_lineal_extremos():
    extremos = np.array([0.0, 1.0], dtype=np.float32)
    lineal = io_img._srgb_a_lineal(extremos)
    np.testing.assert_allclose(lineal, [0.0, 1.0], atol=1e-6)


def test_estimar_sigma_ruido_crece_con_el_ruido(rng=np.random.default_rng(0)):
    plano = np.full((128, 128), 0.5, dtype=np.float32)

    ruido_bajo = plano + rng.normal(0, 0.01, plano.shape).astype(np.float32)
    ruido_alto = plano + rng.normal(0, 0.05, plano.shape).astype(np.float32)

    sigma_bajo = io_img.estimar_sigma_ruido(ruido_bajo)
    sigma_alto = io_img.estimar_sigma_ruido(ruido_alto)

    assert sigma_bajo < sigma_alto
    # El estimador debe aproximar razonablemente el sigma real inyectado.
    assert sigma_bajo == pytest.approx(0.01, abs=0.01)
    assert sigma_alto == pytest.approx(0.05, abs=0.02)


def test_estimar_sigma_ruido_imagen_sin_ruido_es_casi_cero():
    # Gradiente suave, sin ruido: el Laplaciano debe ser ~0 en casi toda la imagen.
    x = np.linspace(0, 1, 64, dtype=np.float32)
    plano = np.tile(x, (64, 1))
    sigma = io_img.estimar_sigma_ruido(plano)
    assert sigma < 1e-3


def test_guardar_y_cargar_png_roundtrip(tmp_path):
    rng = np.random.default_rng(1)
    img = rng.random((32, 48, 3)).astype(np.float32)
    ruta = tmp_path / "prueba.png"

    io_img.guardar(str(ruta), img, bits=16)
    cargada, meta = io_img.cargar(str(ruta))

    assert meta.origen == "ldr"
    assert cargada.shape == img.shape
    np.testing.assert_allclose(cargada, img, atol=1e-3)
