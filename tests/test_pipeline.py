import cv2
import numpy as np

from uppimagen import io_img, pipeline


def _guardar_png_sintetico(ruta, tamano=96, seed=0):
    rng = np.random.default_rng(seed)
    img = np.zeros((tamano, tamano, 3), dtype=np.float32)
    for _ in range(10):
        x0, y0 = rng.integers(0, tamano, 2)
        r = rng.integers(5, 15)
        color = tuple(float(c) for c in rng.random(3))
        cv2.circle(img, (int(x0), int(y0)), int(r), color, -1)
    io_img.guardar(ruta, img)
    return img


def test_procesar_un_solo_frame_ldr_respeta_techo_1_5x(tmp_path):
    ruta_entrada = tmp_path / "entrada.png"
    _guardar_png_sintetico(str(ruta_entrada))

    ruta_salida = tmp_path / "salida.tif"
    resultado = pipeline.procesar([str(ruta_entrada)], factor=2.0, salida=str(ruta_salida))

    assert resultado.factor_alcanzado <= pipeline.FACTOR_MAXIMO_JPEG_UNICO
    assert any("reducido" in aviso for aviso in resultado.avisos)
    assert ruta_salida.exists()
    assert resultado.metricas_fidelidad is not None


def test_procesar_burst_alcanza_factor_solicitado(tmp_path):
    rng = np.random.default_rng(0)
    original = _guardar_png_sintetico(str(tmp_path / "f0.png"), seed=1)

    rutas = [str(tmp_path / "f0.png")]
    for i in range(1, 4):
        desplazado = np.roll(original, shift=(i, i), axis=(0, 1))
        ruta = tmp_path / f"f{i}.png"
        io_img.guardar(str(ruta), desplazado)
        rutas.append(str(ruta))

    resultado = pipeline.procesar(rutas, factor=2.0, salida=str(tmp_path / "salida.tif"))

    assert resultado.factor_alcanzado == 2.0
    assert resultado.imagen.shape[0] == original.shape[0] * 2
