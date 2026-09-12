"""CLI local: la herramienta con la que se atienden los primeros clientes
manualmente, sin ningún servidor.

    python -m uppimagen.cli procesar ./entradas/burst_01/ --factor 2 --salida ./salidas/
    python -m uppimagen.cli verificar ./salidas/resultado.tif --original ./entradas/burst_01/
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np

from . import fidelity, io_img, pipeline, psf as psf_mod, report

EXTENSIONES_VALIDAS = io_img.EXTENSIONES_RAW | io_img.EXTENSIONES_LDR


def _listar_entradas(ruta: str) -> list[str]:
    if os.path.isdir(ruta):
        archivos = []
        for ext in EXTENSIONES_VALIDAS:
            archivos.extend(glob.glob(os.path.join(ruta, f"*{ext}")))
            archivos.extend(glob.glob(os.path.join(ruta, f"*{ext.upper()}")))
        return sorted(archivos)
    return [ruta]


def cmd_procesar(args: argparse.Namespace) -> int:
    rutas = _listar_entradas(args.entrada)
    if not rutas:
        print(f"No se encontraron imágenes válidas en: {args.entrada}", file=sys.stderr)
        return 1

    print(f"Procesando {len(rutas)} archivo(s): {', '.join(os.path.basename(r) for r in rutas)}")

    os.makedirs(args.salida, exist_ok=True)
    nombre_base = os.path.splitext(os.path.basename(rutas[0]))[0]
    ruta_resultado = os.path.join(args.salida, f"{nombre_base}_x{args.factor:.1f}.tif")
    ruta_informe = os.path.join(args.salida, f"{nombre_base}_informe.html")

    resultado = pipeline.procesar(rutas, factor=args.factor, salida=ruta_resultado, perfil=args.perfil)

    print(f"Factor alcanzado: {resultado.factor_alcanzado:.2f}x")
    print(f"Tiempo: {resultado.tiempo_segundos:.1f} s")
    if resultado.metricas_fidelidad:
        m = resultado.metricas_fidelidad
        veredicto = "CONSISTENTE" if m.consistente else "NO CONSISTENTE"
        print(f"Fidelidad: {veredicto} (ratio residuo/ruido = {m.ratio:.2f}, umbral {fidelity.RATIO_CONSISTENCIA_MAX})")
    for aviso in resultado.avisos:
        print(f"  AVISO: {aviso}")

    original, _ = io_img.cargar(rutas[0])
    datos_informe = report.DatosInforme(
        antes=original,
        despues=resultado.imagen,
        consistencia=resultado.metricas_fidelidad,
        degradacion=None,
        factor_alcanzado=resultado.factor_alcanzado,
        avisos=resultado.avisos,
    )
    report.guardar_informe(ruta_informe, datos_informe)

    print(f"Resultado:  {ruta_resultado}")
    print(f"Informe:    {ruta_informe}")

    return 0 if (resultado.metricas_fidelidad is None or resultado.metricas_fidelidad.consistente) else 2


def cmd_verificar(args: argparse.Namespace) -> int:
    resultado_img, _ = io_img.cargar(args.resultado)
    rutas_originales = _listar_entradas(args.original)
    if not rutas_originales:
        print(f"No se encontraron imágenes originales en: {args.original}", file=sys.stderr)
        return 1

    original, meta = io_img.cargar(rutas_originales[0])
    kernel = psf_mod.estimar_psf(original)

    factor = resultado_img.shape[1] / original.shape[1]
    metricas = fidelity.consistencia_reproyeccion(resultado_img, original, kernel, factor=factor)

    veredicto = "CONSISTENTE" if metricas.consistente else "NO CONSISTENTE"
    print(f"Factor estimado: {factor:.2f}x")
    print(f"RMSE residuo: {metricas.rmse_residuo:.5f}")
    print(f"sigma_n: {metricas.sigma_n:.5f}")
    print(f"Ratio residuo/ruido: {metricas.ratio:.2f} (umbral {fidelity.RATIO_CONSISTENCIA_MAX})")
    print(f"Veredicto: {veredicto}")

    return 0 if metricas.consistente else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uppimagen", description="Pipeline de mejora de resolución real.")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    p_procesar = subparsers.add_parser("procesar", help="Procesa un burst o una imagen única.")
    p_procesar.add_argument("entrada", help="Archivo o carpeta con las imágenes de entrada.")
    p_procesar.add_argument("--factor", type=float, default=2.0)
    p_procesar.add_argument("--salida", default="./salidas/")
    p_procesar.add_argument("--perfil", default="equilibrado", choices=["rapido", "equilibrado", "calidad"])
    p_procesar.set_defaults(func=cmd_procesar)

    p_verificar = subparsers.add_parser("verificar", help="Verifica la consistencia de un resultado ya generado.")
    p_verificar.add_argument("resultado", help="Ruta al archivo resultado.")
    p_verificar.add_argument("--original", required=True, help="Archivo o carpeta con el/los original(es).")
    p_verificar.set_defaults(func=cmd_verificar)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
