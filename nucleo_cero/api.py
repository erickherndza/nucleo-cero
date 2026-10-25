"""API REST (Fase 3). Arranque: uvicorn nucleo_cero.api:app --port 8000

Versión 1 síncrona: la foto se procesa dentro de la petición (~1.5 s en M1).
Un candado serializa el motor porque comparte modelos en memoria (no es thread-safe).
"""
import os
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .__main__ import CONFIG

DATOS = Path(os.environ.get('NUCLEO_DATOS', 'data'))
ENTRADA, SALIDA = DATOS / 'input', DATOS / 'output'
MAX_BYTES = 25 * 1024 * 1024
EXTENSIONES = {'.jpg', '.jpeg', '.png', '.webp'}

app = FastAPI(title='nucleo-cero', version='0.1')
_candado = threading.Lock()
_trabajos = {}   # job_id -> dict (en memoria; se pierde al reiniciar)
_tiempos = []


@app.post('/api/v1/procesar')
async def procesar(foto: UploadFile = File(...), esrgan: bool = False):
    ext = Path(foto.filename or '').suffix.lower()
    if ext not in EXTENSIONES:
        raise HTTPException(415, f'Formato no soportado ({ext or "sin extensión"}). Usa {sorted(EXTENSIONES)}')
    datos = await foto.read()
    if len(datos) > MAX_BYTES:
        raise HTTPException(413, 'La foto supera 25 MB')
    job_id = uuid.uuid4().hex[:12]   # nombre propio: nunca se usa el del cliente en disco
    ENTRADA.mkdir(parents=True, exist_ok=True)
    ruta = ENTRADA / f'{job_id}{ext}'
    ruta.write_bytes(datos)

    from . import motor   # import diferido: arranque rápido, modelos al primer uso
    t0 = time.perf_counter()
    try:
        with _candado:
            _, _, reporte, rutas = motor.mejorar_foto(
                str(ruta), carpeta_salida=str(SALIDA), verbose=False, **dict(CONFIG, usar_esrgan=esrgan))
    except Exception as e:
        _trabajos[job_id] = {'estado': 'error', 'error': str(e)}
        raise HTTPException(422, f'No se pudo procesar la imagen: {e}')
    dt = round(time.perf_counter() - t0, 2)
    _tiempos.append(dt)
    _trabajos[job_id] = {'estado': 'listo', 'segundos': dt, 'caras': reporte, 'resultado': rutas['resultado']}
    return {'job_id': job_id, **_trabajos[job_id], 'resultado': f'/api/v1/resultado/{job_id}'}


@app.get('/api/v1/estado/{job_id}')
def estado(job_id: str):
    if job_id not in _trabajos:
        raise HTTPException(404, 'job_id desconocido')
    return {k: v for k, v in _trabajos[job_id].items() if k != 'resultado'}


@app.get('/api/v1/resultado/{job_id}')
def resultado(job_id: str):
    t = _trabajos.get(job_id)
    if not t or t['estado'] != 'listo':
        raise HTTPException(404, 'resultado no disponible')
    return FileResponse(t['resultado'], media_type='image/png', filename=f'{job_id}_mejorada.png')


@app.get('/api/v1/metricas')
def metricas():
    n = len(_tiempos)
    return {'procesadas': n, 'promedio_s': round(sum(_tiempos) / n, 2) if n else None}
