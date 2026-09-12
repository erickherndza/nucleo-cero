import numpy as np

from uppimagen import align


def _patron_textura(tamano=128, seed=0):
    rng = np.random.default_rng(seed)
    base = rng.random((tamano, tamano)).astype(np.float32)
    from scipy.ndimage import gaussian_filter

    return gaussian_filter(base, 1.0).astype(np.float32)


def _desplazar(img: np.ndarray, dx: float, dy: float) -> np.ndarray:
    matriz = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
    return cv2_warp(img, matriz)


def cv2_warp(img, matriz):
    import cv2

    return cv2.warpAffine(img, matriz, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR)


def test_alinear_recupera_desplazamiento_subpixel():
    ref = _patron_textura()
    desplazado = _desplazar(ref, 2.3, -1.7)

    alineados, transformadas = align.alinear([ref, desplazado])

    assert len(alineados) == 2
    t = transformadas[1]
    assert t.aceptado
    dx, dy = t.desplazamiento_px
    assert abs(dx - 2.3) < 0.3
    assert abs(dy - (-1.7)) < 0.3


def test_alinear_rechaza_frame_borroso():
    from scipy.ndimage import gaussian_filter

    ref = _patron_textura()
    borroso = gaussian_filter(ref, 8.0).astype(np.float32)

    alineados, transformadas = align.alinear([ref, borroso])

    assert transformadas[1].aceptado is False
    assert transformadas[1].motivo_rechazo != ""
    assert len(alineados) == 1


def test_alinear_referencia_es_la_mas_nitida():
    from scipy.ndimage import gaussian_filter

    nitida = _patron_textura()
    borrosa = gaussian_filter(nitida, 3.0).astype(np.float32)

    # La referencia (frame 0) debe elegirse por nitidez, sin importar el orden.
    _, transformadas = align.alinear([borrosa, nitida])
    nitideces = [t.nitidez for t in transformadas]
    assert nitideces[1] == max(nitideces)


def test_distribucion_fases_detecta_fase_repetida():
    ref = _patron_textura()
    # Todos los desplazamientos caen en la fase entera -> sin info nueva.
    frames = [ref, _desplazar(ref, 1.0, 0.0), _desplazar(ref, 2.0, 0.0)]
    _, transformadas = align.alinear(frames)
    resultado = align.distribucion_fases(transformadas)
    assert resultado["hay_informacion_nueva"] is False


def test_distribucion_fases_detecta_fases_variadas():
    ref = _patron_textura()
    frames = [ref, _desplazar(ref, 0.25, 0.1), _desplazar(ref, 0.6, 0.75)]
    _, transformadas = align.alinear(frames)
    resultado = align.distribucion_fases(transformadas)
    assert resultado["hay_informacion_nueva"] is True
