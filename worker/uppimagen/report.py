"""Informe HTML autocontenido para el cliente.

Este informe es parte del entregable: es lo que justifica el precio. Incluye
comparación antes/después, mapa de diferencias, tabla de métricas y el sello
de fidelidad con el ratio residuo/ruido como evidencia numérica.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import cv2
import numpy as np

from .fidelity import RATIO_CONSISTENCIA_MAX, ResultadoConsistencia, ResultadoDegradacion
from .io_img import _lineal_a_srgb


def _img_a_data_uri(img_lineal: np.ndarray, calidad: int = 90) -> str:
    srgb = _lineal_a_srgb(np.clip(img_lineal, 0, 1))
    img8 = np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)
    bgr = cv2.cvtColor(img8, cv2.COLOR_RGB2BGR) if img8.ndim == 3 else img8
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, calidad])
    if not ok:
        raise IOError("No se pudo codificar la imagen para el informe")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


@dataclass
class DatosInforme:
    antes: np.ndarray
    despues: np.ndarray
    consistencia: ResultadoConsistencia
    degradacion: ResultadoDegradacion | None
    factor_alcanzado: float
    avisos: list[str]


_PLANTILLA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe de fidelidad — UppImagenScale</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; background: #fafafa; }}
  h1 {{ font-size: 1.4rem; }}
  .sello {{ display: inline-block; padding: 0.5rem 1rem; border-radius: 6px; font-weight: 600; margin: 1rem 0; }}
  .sello.ok {{ background: #dcfce7; color: #166534; border: 1px solid #16653433; }}
  .sello.fallo {{ background: #fee2e2; color: #991b1b; border: 1px solid #991b1b33; }}
  .comparador {{ position: relative; width: 100%; max-width: 800px; margin: 1.5rem 0; overflow: hidden; border-radius: 8px; border: 1px solid #ddd; }}
  .comparador img {{ display: block; width: 100%; height: auto; }}
  .comparador .despues {{ position: absolute; top: 0; left: 0; width: 50%; overflow: hidden; border-right: 2px solid white; }}
  .comparador .despues img {{ width: var(--ancho-comparador, 800px); max-width: none; }}
  input[type=range] {{ width: 100%; margin-top: 0.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; }}
  .avisos {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 0.75rem 1rem; }}
  .avisos li {{ margin-bottom: 0.25rem; }}
  figure {{ margin: 1rem 0; }}
  figcaption {{ font-size: 0.85rem; color: #555; }}
</style>
</head>
<body>
<h1>Informe de fidelidad</h1>
<div class="sello {clase_sello}">{texto_sello}</div>

<h2>Antes / Después</h2>
<div class="comparador" id="comparador">
  <img src="{uri_antes}" alt="Original">
  <div class="despues" id="despues-contenedor">
    <img src="{uri_despues}" alt="Resultado">
  </div>
</div>
<input type="range" min="0" max="100" value="50" id="deslizador">

<h2>Mapa de diferencias (degradación controlada)</h2>
{seccion_mapa_diferencias}

<h2>Métricas</h2>
<table>
  <tr><th>Métrica</th><th>Valor</th></tr>
  <tr><td>Factor efectivo alcanzado</td><td>{factor_alcanzado:.2f}×</td></tr>
  <tr><td>RMSE residuo de reproyección</td><td>{rmse_residuo:.5f}</td></tr>
  <tr><td>σ ruido estimado</td><td>{sigma_n:.5f}</td></tr>
  <tr><td>Ratio residuo / ruido</td><td>{ratio:.2f} (umbral: {umbral:.1f})</td></tr>
  {filas_degradacion}
</table>

<h2>Avisos</h2>
{seccion_avisos}

<script>
  const deslizador = document.getElementById('deslizador');
  const despues = document.getElementById('despues-contenedor');
  const comparador = document.getElementById('comparador');
  function actualizar() {{
    const pct = deslizador.value;
    despues.style.width = pct + '%';
    const anchoTotal = comparador.clientWidth;
    despues.querySelector('img').style.width = anchoTotal + 'px';
  }}
  deslizador.addEventListener('input', actualizar);
  window.addEventListener('resize', actualizar);
  actualizar();
</script>
</body>
</html>
"""


def generar_informe(datos: DatosInforme) -> str:
    """Genera el HTML autocontenido del informe y lo devuelve como string."""
    consistente = datos.consistencia.consistente
    clase_sello = "ok" if consistente else "fallo"
    texto_sello = (
        "✓ Verificado — sin generación de detalle"
        if consistente
        else "✗ No verificado — revisar antes de entregar"
    )

    uri_antes = _img_a_data_uri(datos.antes)
    uri_despues = _img_a_data_uri(datos.despues)

    filas_degradacion = ""
    seccion_mapa_diferencias = "<p><em>No se ejecutó prueba de degradación controlada para este trabajo.</em></p>"
    if datos.degradacion is not None:
        filas_degradacion = (
            f"<tr><td>PSNR (pipeline)</td><td>{datos.degradacion.psnr:.2f} dB</td></tr>"
            f"<tr><td>PSNR (bicúbica)</td><td>{datos.degradacion.psnr_bicubica:.2f} dB</td></tr>"
            f"<tr><td>SSIM (pipeline)</td><td>{datos.degradacion.ssim:.4f}</td></tr>"
            f"<tr><td>SSIM (bicúbica)</td><td>{datos.degradacion.ssim_bicubica:.4f}</td></tr>"
            f"<tr><td>¿Supera a bicúbica?</td><td>{'Sí' if datos.degradacion.supera_bicubica else 'No'}</td></tr>"
        )
        mapa = datos.degradacion.mapa_diferencias
        mapa_norm = mapa / max(mapa.max(), 1e-6)
        uri_mapa = _img_a_data_uri(mapa_norm)
        seccion_mapa_diferencias = (
            f'<figure><img src="{uri_mapa}" style="max-width:100%;border-radius:8px;border:1px solid #ddd;">'
            "<figcaption>Diferencia amplificada entre la reconstrucción y la imagen de referencia "
            "en la prueba de degradación controlada.</figcaption></figure>"
        )

    if datos.avisos:
        items = "".join(f"<li>{aviso}</li>" for aviso in datos.avisos)
        seccion_avisos = f"<ul class='avisos'>{items}</ul>"
    else:
        seccion_avisos = "<p>Sin avisos: todos los frames se usaron y no hubo zonas sin cobertura.</p>"

    return _PLANTILLA.format(
        clase_sello=clase_sello,
        texto_sello=texto_sello,
        uri_antes=uri_antes,
        uri_despues=uri_despues,
        seccion_mapa_diferencias=seccion_mapa_diferencias,
        factor_alcanzado=datos.factor_alcanzado,
        rmse_residuo=datos.consistencia.rmse_residuo,
        sigma_n=datos.consistencia.sigma_n,
        ratio=datos.consistencia.ratio,
        umbral=RATIO_CONSISTENCIA_MAX,
        filas_degradacion=filas_degradacion,
        seccion_avisos=seccion_avisos,
    )


def guardar_informe(ruta: str, datos: DatosInforme) -> None:
    html = generar_informe(datos)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(html)
