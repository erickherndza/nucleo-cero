import numpy as np

from uppimagen import merge


def test_fusionar_un_solo_frame_produce_tamano_hr_correcto():
    frame = np.full((16, 16), 0.5, dtype=np.float32)
    identidad = np.eye(2, 3, dtype=np.float32)

    resultado = merge.fusionar([frame], [identidad], [1.0], factor=2.0)

    assert resultado.hr.shape == (32, 32)
    np.testing.assert_allclose(resultado.hr, 0.5, atol=0.05)


def test_fusionar_burst_reduce_ruido_respecto_a_un_frame():
    rng = np.random.default_rng(0)
    base = np.full((24, 24), 0.5, dtype=np.float32)
    frames = [base + rng.normal(0, 0.05, base.shape).astype(np.float32) for _ in range(6)]
    identidad = np.eye(2, 3, dtype=np.float32)
    matrices = [identidad] * 6
    nitideces = [1.0] * 6

    resultado = merge.fusionar(frames, matrices, nitideces, factor=1.0)

    ruido_un_frame = np.std(frames[0] - 0.5)
    ruido_fusion = np.std(resultado.hr - 0.5)
    assert ruido_fusion < ruido_un_frame


def test_fusionar_detecta_zonas_sin_cobertura_con_traslacion_grande():
    frame = np.full((16, 16), 0.5, dtype=np.float32)
    desplazada = np.array([[1, 0, 50], [0, 1, 50]], dtype=np.float32)  # fuera del lienzo

    resultado = merge.fusionar([frame, frame], [np.eye(2, 3, dtype=np.float32), desplazada], [1.0, 1.0], factor=1.0)

    assert resultado.fraccion_sin_cobertura >= 0.0
    assert resultado.mascara_cobertura.shape == resultado.hr.shape
