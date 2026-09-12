import tracemalloc

import numpy as np

from uppimagen import tiling


def test_procesar_por_tiles_identidad_reconstruye_imagen():
    rng = np.random.default_rng(0)
    img = rng.random((300, 400, 3)).astype(np.float32)

    resultado = tiling.procesar_por_tiles(img, lambda t: t, factor=1.0, tamano_tile=128, solapamiento=32)

    np.testing.assert_allclose(resultado, img, atol=1e-4)


def test_procesar_por_tiles_sin_costuras_visibles():
    # Gradiente suave: si hay costuras en los bordes de tile, aparecerán
    # discontinuidades detectables en la segunda derivada.
    x = np.linspace(0, 1, 256, dtype=np.float32)
    img = np.tile(x, (256, 1))

    resultado = tiling.procesar_por_tiles(img, lambda t: t, factor=1.0, tamano_tile=64, solapamiento=16)

    segunda_derivada = np.diff(resultado, n=2, axis=1)
    assert np.max(np.abs(segunda_derivada)) < 1e-2


def test_procesar_por_tiles_respeta_factor_de_escala():
    img = np.zeros((64, 64), dtype=np.float32)

    def duplicar(tile):
        return np.repeat(np.repeat(tile, 2, axis=0), 2, axis=1)

    resultado = tiling.procesar_por_tiles(img, duplicar, factor=2.0, tamano_tile=32, solapamiento=8)

    assert resultado.shape == (128, 128)


def test_consumo_de_memoria_acotado_para_imagen_grande():
    """Verifica que el procesamiento por tiles mantenga memoria constante."""
    img = np.random.default_rng(0).random((3000, 4000)).astype(np.float32)

    tracemalloc.start()
    tracemalloc.reset_peak()
    _ = tiling.procesar_por_tiles(img, lambda t: t * 1.0, factor=1.0)
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    pico_mb = pico / (1024 * 1024)
    assert pico_mb < 400, f"Consumo pico {pico_mb:.1f} MB supera el límite de 400 MB"
