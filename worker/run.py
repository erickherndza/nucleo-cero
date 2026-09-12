"""Loop de polling del worker contra el front.

    bucle:
        POST /api/trabajos/siguiente
        si no hay trabajo -> dormir INTERVALO y repetir
        descargar originales a carpeta temporal
        POST estado = 'procesando'
        ejecutar pipeline.procesar(...)
        ejecutar fidelity -> si NO es consistente: marcar error, no entregar
        POST resultado + informe + métricas
        limpiar temporales

Nunca entrega un resultado que no pase el test de consistencia de
reproyección (la regla de oro del proyecto).
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import tempfile
import time

import yaml

sys.path.insert(0, os.path.dirname(__file__))

from client import ClienteFront
from uppimagen import fidelity, io_img, pipeline, report

logger = logging.getLogger("uppimagen.worker")


def _configurar_logging(directorio_logs: str) -> None:
    os.makedirs(directorio_logs, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(directorio_logs, "worker.log"), maxBytes=5 * 1024 * 1024, backupCount=5
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


def _cargar_config(ruta: str) -> dict:
    with open(ruta, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class _Caffeinate:
    """Evita que el Mac duerma mientras haya trabajo activo (`caffeinate -i`)."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None

    def __enter__(self):
        if shutil.which("caffeinate"):
            self._proc = subprocess.Popen(["caffeinate", "-i"])
        return self

    def __exit__(self, *exc):
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait(timeout=5)


def _procesar_trabajo(cliente: ClienteFront, trabajo, config: dict) -> None:
    directorio_temporal = tempfile.mkdtemp(
        prefix=f"uppimagen_{trabajo.id}_", dir=config.get("directorio_temporal", "./tmp")
    )
    try:
        rutas_originales = []
        for archivo in trabajo.archivos:
            destino = os.path.join(directorio_temporal, archivo["nombre"])
            cliente.descargar_archivo(archivo["id"], destino)
            rutas_originales.append(destino)

        cliente.actualizar_estado(trabajo.id, "procesando")

        resultado = pipeline.procesar(
            rutas_originales,
            factor=trabajo.factor,
            salida=os.path.join(directorio_temporal, "resultado.tif"),
        )

        if resultado.metricas_fidelidad is None or not resultado.metricas_fidelidad.consistente:
            razon = (
                f"ratio residuo/ruido = {resultado.metricas_fidelidad.ratio:.2f} "
                f">= {fidelity.RATIO_CONSISTENCIA_MAX}"
                if resultado.metricas_fidelidad
                else "no se pudo calcular la fidelidad"
            )
            logger.error("Trabajo %s NO pasó el test de consistencia: %s", trabajo.id, razon)
            cliente.marcar_error(trabajo.id, f"Falló el test de consistencia de reproyección: {razon}")
            return

        original, _ = io_img.cargar(rutas_originales[0])
        ruta_informe = os.path.join(directorio_temporal, "informe.html")
        datos_informe = report.DatosInforme(
            antes=original,
            despues=resultado.imagen,
            consistencia=resultado.metricas_fidelidad,
            degradacion=None,
            factor_alcanzado=resultado.factor_alcanzado,
            avisos=resultado.avisos,
        )
        report.guardar_informe(ruta_informe, datos_informe)

        metricas = {
            "ratio_consistencia": resultado.metricas_fidelidad.ratio,
            "rmse_residuo": resultado.metricas_fidelidad.rmse_residuo,
            "sigma_n": resultado.metricas_fidelidad.sigma_n,
            "factor_alcanzado": resultado.factor_alcanzado,
            "avisos": resultado.avisos,
            "tiempo_segundos": resultado.tiempo_segundos,
        }
        cliente.subir_resultado(trabajo.id, resultado.ruta_salida, ruta_informe, metricas)
        logger.info("Trabajo %s completado y entregado.", trabajo.id)

    except Exception as exc:  # nunca dejar el trabajo colgado
        logger.exception("Error procesando trabajo %s", trabajo.id)
        try:
            cliente.marcar_error(trabajo.id, f"Error de procesamiento: {exc}")
        except Exception:
            logger.exception("No se pudo notificar el error al front para el trabajo %s", trabajo.id)
    finally:
        shutil.rmtree(directorio_temporal, ignore_errors=True)


def bucle_principal(config: dict) -> None:
    cliente = ClienteFront(config["front_url"], config["worker_token"], config["worker_id"])
    intervalo = config.get("intervalo_segundos", 300)

    logger.info("Worker %s iniciado, consultando %s cada %ss", config["worker_id"], config["front_url"], intervalo)

    with _Caffeinate():
        while True:
            try:
                trabajo = cliente.reclamar_trabajo()
            except ConnectionError:
                logger.warning("Sin conexión con el front, reintentando en %ss", intervalo)
                time.sleep(intervalo)
                continue

            if trabajo is None:
                time.sleep(intervalo)
                continue

            logger.info("Trabajo reclamado: %s (factor %.1fx)", trabajo.id, trabajo.factor)
            _procesar_trabajo(cliente, trabajo, config)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker de polling de UppImagenScale.")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args(argv)

    config = _cargar_config(args.config)
    os.makedirs(config.get("directorio_temporal", "./tmp"), exist_ok=True)
    _configurar_logging("./logs")

    try:
        bucle_principal(config)
    except KeyboardInterrupt:
        logger.info("Worker detenido por el usuario.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
