"""Cliente HTTP del worker contra el front en Banahosting.

El Mac siempre inicia la conexión saliente (está detrás de un router sin IP
pública): nunca al revés. Todas las rutas van con `Authorization: Bearer
<WORKER_TOKEN>`.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger("uppimagen.client")

REINTENTOS_MAX = 5
BACKOFF_BASE_SEGUNDOS = 2.0


@dataclass
class Trabajo:
    id: int
    token_publico: str
    factor: float
    archivos: list[dict]  # [{id, nombre, tipo}, ...]


class ClienteFront:
    def __init__(self, front_url: str, worker_token: str, worker_id: str):
        self.base_url = front_url.rstrip("/")
        self.worker_id = worker_id
        self._sesion = requests.Session()
        self._sesion.headers.update({"Authorization": f"Bearer {worker_token}"})

    def _con_reintentos(self, metodo, ruta: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{ruta}"
        ultimo_error: Optional[Exception] = None

        for intento in range(REINTENTOS_MAX):
            try:
                resp = self._sesion.request(metodo, url, timeout=kwargs.pop("timeout", 60), **kwargs)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"Error del servidor {resp.status_code}")
                return resp
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
                ultimo_error = exc
                espera = BACKOFF_BASE_SEGUNDOS * (2**intento)
                logger.warning("Fallo de red (%s), reintentando en %.1fs: %s", metodo, espera, exc)
                time.sleep(espera)

        raise ConnectionError(f"No se pudo completar {metodo} {ruta} tras {REINTENTOS_MAX} intentos") from ultimo_error

    def reclamar_trabajo(self) -> Optional[Trabajo]:
        resp = self._con_reintentos("POST", "/api/trabajos/siguiente", json={"worker_id": self.worker_id})
        if resp.status_code == 204 or resp.status_code == 404:
            return None
        resp.raise_for_status()
        datos = resp.json()
        if not datos:
            return None
        return Trabajo(
            id=datos["id"],
            token_publico=datos["token_publico"],
            factor=float(datos.get("factor", 2.0)),
            archivos=datos.get("archivos", []),
        )

    def descargar_archivo(self, archivo_id: int, destino: str) -> str:
        resp = self._con_reintentos("GET", f"/api/archivos/{archivo_id}/descargar", stream=True)
        resp.raise_for_status()

        sha256 = hashlib.sha256()
        with open(destino, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                fh.write(chunk)
                sha256.update(chunk)

        sha_esperado = resp.headers.get("X-SHA256")
        sha_calculado = sha256.hexdigest()
        if sha_esperado and sha_esperado != sha_calculado:
            raise IOError(f"SHA256 no coincide para archivo {archivo_id}: esperado {sha_esperado}, obtenido {sha_calculado}")

        return sha_calculado

    def actualizar_estado(self, trabajo_id: int, estado: str, mensaje: str = "") -> None:
        resp = self._con_reintentos(
            "POST", f"/api/trabajos/{trabajo_id}/estado", json={"estado": estado, "mensaje": mensaje}
        )
        resp.raise_for_status()

    def marcar_error(self, trabajo_id: int, error_msg: str) -> None:
        resp = self._con_reintentos(
            "POST", f"/api/trabajos/{trabajo_id}/estado", json={"estado": "error", "mensaje": error_msg}
        )
        resp.raise_for_status()

    def subir_resultado(
        self,
        trabajo_id: int,
        ruta_resultado: str,
        ruta_informe: str,
        metricas: dict,
    ) -> None:
        def _sha256_archivo(ruta: str) -> str:
            h = hashlib.sha256()
            with open(ruta, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()

        with open(ruta_resultado, "rb") as f_resultado, open(ruta_informe, "rb") as f_informe:
            archivos = {
                "resultado": (ruta_resultado.split("/")[-1], f_resultado),
                "informe": (ruta_informe.split("/")[-1], f_informe),
            }
            datos = {
                "sha256_resultado": _sha256_archivo(ruta_resultado),
                "sha256_informe": _sha256_archivo(ruta_informe),
                "metricas_json": _a_json(metricas),
            }
            resp = self._con_reintentos(
                "POST",
                f"/api/trabajos/{trabajo_id}/resultado",
                files=archivos,
                data=datos,
                timeout=300,
            )
        resp.raise_for_status()


def _a_json(datos: dict) -> str:
    import json

    return json.dumps(datos, ensure_ascii=False, default=str)
