"""Benchmark local: tiempo por foto y capacidad proyectada por hora (Fase 2 del plan)."""
import logging
import time
from typing import Callable, Dict, List

log = logging.getLogger('nucleo_cero.benchmark')


def ejecutar_benchmark(proceso: Callable, lote: List[str], calentamiento=True) -> Dict:
    """Corre `proceso(item)` sobre cada ítem y mide.

    La primera llamada carga los modelos en memoria (varios segundos); con
    `calentamiento=True` se reporta aparte para no contaminar el promedio.
    """
    tiempos, fallos = [], 0
    t_carga = None
    inicio = time.perf_counter()
    for i, item in enumerate(lote, 1):
        t0 = time.perf_counter()
        try:
            proceso(item)
        except Exception as e:  # una foto mala no debe tumbar el lote
            fallos += 1
            log.error('[%d/%d] %s falló: %s', i, len(lote), item, e)
            continue
        dt = time.perf_counter() - t0
        if calentamiento and t_carga is None:
            t_carga = dt
            log.info('[%d/%d] %.2fs (incluye carga de modelos, no cuenta en el promedio)', i, len(lote), dt)
            continue
        tiempos.append(dt)
        log.info('[%d/%d] %.2fs', i, len(lote), dt)
    if not tiempos:
        return {'error': 'sin iteraciones válidas (usa al menos 2 fotos con calentamiento)'}
    prom = sum(tiempos) / len(tiempos)
    return {
        'procesadas': len(tiempos) + (1 if t_carga else 0),
        'fallos': fallos,
        'carga_modelos_s': round(t_carga, 2) if t_carga else None,
        'promedio_por_foto_s': round(prom, 2),
        'fotos_por_hora': int(3600 / prom),
        'total_s': round(time.perf_counter() - inicio, 2),
    }
