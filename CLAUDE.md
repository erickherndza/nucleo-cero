# CLAUDE.md — UppImagenScale

## Regla no negociable
Este proyecto NO genera ni alucina detalle. Prohibido introducir modelos
generativos, GANs, difusión, o cualquier red que sintetice píxeles.
Toda mejora debe pasar el test de consistencia de reproyección de
`worker/uppimagen/fidelity.py`.

## Dos entornos, dos versiones de Python
- `worker/` → Python 3.11+, corre en el Mac. numpy/scipy/opencv/rawpy modernos.
- `front/`  → Python 3.8.20, corre en Banahosting bajo Passenger.
  SOLO dependencias Python puro (no compilar nada).
  NUNCA importar numpy, scipy, opencv ni rawpy aquí.

## Restricciones de máquina (MacBook Pro 2015, 8 GB, Intel)
- Procesar SIEMPRE por tiles. El consumo debe ser constante
  independientemente del tamaño de la imagen.
- Sin GPU. Sin Metal/MPS. Todo CPU.
- No usar Docker para el pipeline (la VM de Docker Desktop consume 2-4 GB).

## Convenciones
- Todo el procesamiento numérico en float32 y en LUZ LINEAL
  (deshacer gamma al cargar, reaplicar al guardar).
- Código y comentarios en español.
- Cada módulo con su test antes de darlo por terminado.

## Debug
Seguir: Reproducir → Aislar → Hipótesis → Verificar → Fix mínimo.
