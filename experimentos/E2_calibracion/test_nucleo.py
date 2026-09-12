import numpy as np

from nucleo import (
    correlacion_spearman,
    descomponer_rango_nucleo,
    error_relativo,
    error_rms,
    reconstrucciones_bootstrap,
    tau_frecuencia,
    tau_incertidumbre,
)


def test_descomponer_region_puramente_baja_frecuencia():
    # imagen constante: toda su energía (aparte de DC) es cero; con f_c
    # cualquiera, no debería haber núcleo significativo
    region = np.full((64, 64), 0.5)
    norma_rango, norma_nucleo = descomponer_rango_nucleo(region, f_c=0.3)
    assert norma_nucleo < 1e-6
    assert norma_rango > 0


def test_tau_frecuencia_alto_para_ruido_puro_por_encima_del_corte():
    rng = np.random.default_rng(0)
    region = rng.normal(0, 1, size=(64, 64))  # ruido blanco: energía pareja en toda frecuencia
    t_corte_bajo = tau_frecuencia(region, f_c=0.1)  # casi todo cae en "núcleo"
    t_corte_alto = tau_frecuencia(region, f_c=0.9)  # casi todo cae en "rango"
    assert t_corte_bajo > t_corte_alto


def test_tau_incertidumbre_es_cero_sin_variacion_entre_reconstrucciones():
    reconstrucciones = np.stack([np.full((32, 32), 0.5)] * 4)
    t = tau_incertidumbre(reconstrucciones, y0=0, x0=0, tam=32)
    assert t == 0.0


def test_tau_incertidumbre_baja_si_hay_mas_estructura_real_con_igual_ruido():
    """Es un cociente (coeficiente de variación): a igual dispersión entre
    reconstrucciones, más estructura real de fondo debe dar τ MÁS BAJO (más
    confianza relativa) — al revés de tau_frecuencia, que subía con el
    detalle en vez de bajar."""
    rng = np.random.default_rng(3)
    eje = np.linspace(0, 4 * np.pi, 32)
    xx, yy = np.meshgrid(eje, eje)
    poca_estructura = 0.5 + 0.01 * np.sin(xx)
    mucha_estructura = 0.5 + 0.3 * np.sin(xx) * np.cos(yy)

    def con_ruido(base, sigma, k=4):
        return np.stack([base + rng.normal(0, sigma, base.shape) for _ in range(k)])

    t_poca = tau_incertidumbre(con_ruido(poca_estructura, 0.02), 0, 0, 32)
    t_mucha = tau_incertidumbre(con_ruido(mucha_estructura, 0.02), 0, 0, 32)
    assert t_mucha < t_poca


def test_tau_incertidumbre_region_lisa_vs_texturada_con_verdad_conocida():
    """Caso de control con verdad conocida: mitad lisa, mitad con textura
    fuerte, degradada y reconstruida con bootstrap. Documenta el
    comportamiento real medido (no una expectativa a priori, que ya falló
    una vez en este mismo diseño): con τ normalizado por estructura local,
    la región lisa da τ más alto (menos confianza relativa) que la
    texturada — lo esperado de un coeficiente de variación."""
    rng = np.random.default_rng(7)
    tam = 128
    x_verdad = np.zeros((tam, tam))
    x_verdad[:, tam // 2 :] = 0.5  # mitad izquierda lisa, mitad derecha con borde fuerte
    eje = np.arange(tam)
    textura = 0.15 * np.sin(eje[None, :] * 1.2) * np.cos(eje[:, None] * 1.3)
    x_verdad[:, tam // 2 :] += textura[:, tam // 2 :]
    x_verdad = np.clip(x_verdad, 0, 1)

    sigma_psf, factor, sigma_ruido = 1.0, 2, 0.02
    recons, _ = reconstrucciones_bootstrap(x_verdad, sigma_psf, factor, sigma_ruido, k=4, rng=rng)

    t_lisa = tau_incertidumbre(recons, y0=32, x0=16, tam=32)
    t_texturada = tau_incertidumbre(recons, y0=32, x0=tam // 2 + 16, tam=32)
    assert t_lisa > t_texturada


def test_error_rms_cero_si_identico():
    a = np.random.default_rng(1).uniform(0, 1, size=(32, 32))
    assert error_rms(a, a) == 0.0


def test_error_relativo_invariante_de_escala():
    """El bug real detrás de avance-1.4/1.5: error_rms absoluto escala con
    el contraste de la región, así que no es comparable entre una zona lisa
    y una texturada. error_relativo, al dividir por la propia estructura de
    la verdad, debe dar (aprox) el mismo valor si escalo la región entera
    (verdad + un error proporcional) por una constante."""
    rng = np.random.default_rng(9)
    verdad = rng.uniform(0, 1, size=(32, 32))
    error_abs = rng.normal(0, 0.02, size=(32, 32))
    estimado = verdad + error_abs

    verdad_x10 = verdad * 10
    estimado_x10 = estimado * 10  # mismo error relativo, todo escalado x10

    r1 = error_relativo(estimado, verdad)
    r2 = error_relativo(estimado_x10, verdad_x10)
    assert np.isclose(r1, r2, rtol=1e-6)


def test_error_relativo_mayor_en_region_lisa_con_mismo_error_absoluto():
    """Con el MISMO error absoluto, la región con menos estructura real
    (más lisa) debe dar error_relativo más alto — es justo lo que
    error_rms (sin normalizar) no podía distinguir."""
    rng = np.random.default_rng(10)
    error_abs = rng.normal(0, 0.02, size=(32, 32))

    verdad_lisa = np.full((32, 32), 0.5)
    verdad_texturada = np.linspace(0, 1, 32)[None, :].repeat(32, axis=0)

    r_lisa = error_relativo(verdad_lisa + error_abs, verdad_lisa)
    r_texturada = error_relativo(verdad_texturada + error_abs, verdad_texturada)
    assert r_lisa > r_texturada


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
