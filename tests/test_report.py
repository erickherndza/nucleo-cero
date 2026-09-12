import numpy as np

from uppimagen import fidelity, report


def test_generar_informe_incluye_sello_ok_cuando_es_consistente():
    antes = np.random.default_rng(0).random((32, 32, 3)).astype(np.float32)
    despues = antes.copy()

    consistencia = fidelity.ResultadoConsistencia(rmse_residuo=0.001, sigma_n=0.01, ratio=0.1, consistente=True)
    datos = report.DatosInforme(
        antes=antes, despues=despues, consistencia=consistencia, degradacion=None, factor_alcanzado=2.0, avisos=[]
    )

    html = report.generar_informe(datos)

    assert "Verificado — sin generación de detalle" in html
    assert "sello ok" in html
    assert "data:image/jpeg;base64," in html


def test_generar_informe_incluye_sello_fallo_cuando_no_es_consistente():
    antes = np.random.default_rng(0).random((32, 32, 3)).astype(np.float32)
    despues = antes.copy()

    consistencia = fidelity.ResultadoConsistencia(rmse_residuo=0.5, sigma_n=0.01, ratio=50.0, consistente=False)
    datos = report.DatosInforme(
        antes=antes,
        despues=despues,
        consistencia=consistencia,
        degradacion=None,
        factor_alcanzado=2.0,
        avisos=["3 frames descartados"],
    )

    html = report.generar_informe(datos)

    assert "No verificado" in html
    assert "sello fallo" in html
    assert "3 frames descartados" in html


def test_guardar_informe_escribe_archivo(tmp_path):
    antes = np.random.default_rng(0).random((16, 16, 3)).astype(np.float32)
    consistencia = fidelity.ResultadoConsistencia(rmse_residuo=0.001, sigma_n=0.01, ratio=0.1, consistente=True)
    datos = report.DatosInforme(
        antes=antes, despues=antes, consistencia=consistencia, degradacion=None, factor_alcanzado=1.5, avisos=[]
    )

    ruta = tmp_path / "informe.html"
    report.guardar_informe(str(ruta), datos)

    assert ruta.exists()
    assert "html" in ruta.read_text(encoding="utf-8").lower()
