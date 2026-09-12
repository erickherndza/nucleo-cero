import numpy as np

from nucleo import correlacion_spearman, descomponer_rango_nucleo, error_rms, tau


def test_descomponer_region_puramente_baja_frecuencia():
    # imagen constante: toda su energía (aparte de DC) es cero; con f_c
    # cualquiera, no debería haber núcleo significativo
    region = np.full((64, 64), 0.5)
    norma_rango, norma_nucleo = descomponer_rango_nucleo(region, f_c=0.3)
    assert norma_nucleo < 1e-6
    assert norma_rango > 0


def test_tau_alto_para_ruido_puro_por_encima_del_corte():
    rng = np.random.default_rng(0)
    region = rng.normal(0, 1, size=(64, 64))  # ruido blanco: energía pareja en toda frecuencia
    t_corte_bajo = tau(region, f_c=0.1)  # casi todo cae en "núcleo"
    t_corte_alto = tau(region, f_c=0.9)  # casi todo cae en "rango"
    assert t_corte_bajo > t_corte_alto


def test_error_rms_cero_si_identico():
    a = np.random.default_rng(1).uniform(0, 1, size=(32, 32))
    assert error_rms(a, a) == 0.0


def test_correlacion_spearman_perfecta():
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    b = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    assert np.isclose(correlacion_spearman(a, b), 1.0)


def test_correlacion_spearman_inversa():
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    b = np.array([50.0, 40.0, 30.0, 20.0, 10.0])
    assert np.isclose(correlacion_spearman(a, b), -1.0)


def test_correlacion_spearman_sin_relacion_es_baja():
    rng = np.random.default_rng(2)
    a = rng.uniform(0, 1, size=200)
    b = rng.uniform(0, 1, size=200)
    assert abs(correlacion_spearman(a, b)) < 0.25
