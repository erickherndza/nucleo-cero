# UppImagenScale

Servicio de mejora de resolución real de fotografías, sin generación ni
alucinación de detalle. Ver [`UppImagenScale.md`](UppImagenScale.md) para la
especificación completa (arquitectura, fases, regla de oro de fidelidad).

## Estructura

- `worker/` — pipeline de procesamiento (Python 3.11+), corre en el Mac local.
- `front/` — portal + cola de trabajos (Python 3.8.20), corre en Banahosting.
- `tests/` — pruebas del pipeline.

## Uso rápido (Fase 1, CLI local)

```bash
cd worker
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uppimagen.cli procesar ./entradas/burst_01/ --factor 2 --salida ./salidas/
```
