# Avance 1.0 — Repositorio reiniciado, herramienta de E0 construida

**Fecha:** 2026-09-12

## Qué cambió

- Se reinició el repositorio desde cero (historial de git anterior descartado
  a petición explícita; el estado previo del pipeline "Fases 0-5" queda
  respaldado fuera del repo, no en el historial de git).
- Se adoptó `METODO.md` como especificación única del proyecto, reemplazando
  el enfoque anterior (`UppImagenScale.md`, ya no existe).
- Se creó la estructura de `METODO.md` §6: `experimentos/`, `avances/`.
  `metodo/` no existe todavía — por regla del propio método, nada entra ahí
  hasta que su experimento correspondiente pase la puerta en verde.
- Se implementó `experimentos/E0_margen/medir.py`: carga de imagen con
  deslinealización sRGB→lineal, espectro de potencia promediado radialmente,
  y clasificador de forma del corte (`suave` / `muro` / `plegado`) según la
  tabla de `METODO.md` §3 (E0).
- Tests en `experimentos/E0_margen/test_medir.py` sobre perfiles espectrales
  sintéticos (no sobre imágenes reales) para validar la lógica de
  clasificación de forma independiente del corpus.

## Qué falta para cerrar E0

**Bloqueado en el corpus.** El método exige 50 imágenes reales de clientes
(WhatsApp, web, escaneos, móvil, capturas) — explícitamente *no* datasets
académicos, porque la pregunta de E0 es sobre el margen en imágenes reales de
clientes, no en benchmarks. Sin ese corpus no se puede correr `medir.py` en
serio ni escribir el veredicto en `experimentos/E0_margen/RESULTADOS.md`.

## Siguiente avance

`avance-1.1`: correr `medir.py` sobre el corpus real en cuanto esté
disponible, llenar `RESULTADOS.md`, y registrar el veredicto verde/rojo de la
puerta E0.
