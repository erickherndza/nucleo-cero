import numpy as np

from medir import clasificar_corte, espectro_radial, srgb_a_lineal


def _freqs(n=200):
    return np.linspace(0, 1, n)


def test_clasifica_caida_suave():
    freqs = _freqs()
    # decaimiento gaussiano: transición ancha por construcción
    dB_pico, dB_piso = 40.0, 0.0
    dB = dB_piso + (dB_pico - dB_piso) * np.exp(-(freqs**2) / (2 * 0.35**2))
    potencia = 10 ** (dB / 10)
    f_eff, tipo = clasificar_corte(freqs, potencia)
    assert tipo == "suave"
    assert f_eff < 0.95  # queda margen antes de Nyquist


def test_clasifica_muro_abrupto():
    freqs = _freqs()
    dB = np.where(freqs < 0.5, 40.0, 0.0)
    potencia = 10 ** (dB / 10)
    _, tipo = clasificar_corte(freqs, potencia)
    assert tipo == "muro"


def test_clasifica_energia_plegada():
    freqs = _freqs()
    dB = np.where(freqs < 0.5, 40.0, 0.0)
    # repunte de energía justo en el borde de Nyquist
    dB = np.where(freqs >= 0.96, 15.0, dB)
    potencia = 10 ** (dB / 10)
    _, tipo = clasificar_corte(freqs, potencia)
    assert tipo == "plegado"


def test_srgb_a_lineal_es_monotona_y_acotada():
    c = np.linspace(0, 1, 50, dtype=np.float32)
    lin = srgb_a_lineal(c)
    assert np.all(np.diff(lin) >= 0)
    assert lin.min() >= 0.0 and lin.max() <= 1.0 + 1e-6


def test_espectro_radial_forma_de_salida():
    img = np.random.default_rng(0).normal(size=(64, 96)).astype(np.float32)
    freqs, potencia = espectro_radial(img)
    assert freqs.shape == potencia.shape
    assert freqs[0] == 0.0
    assert freqs[-1] == 1.0
