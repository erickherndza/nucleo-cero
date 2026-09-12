# E0 — Resultados

**Estado: INSTRUMENTO CUESTIONADO. Veredicto NO válido todavía.**

Corpus real (50 imágenes, 49 medidas) corrido el 2026-09-12 con
`medir.py` v1. Salida cruda: `resultados_e0.csv`.

- 100% del corpus clasificado como "suave"
- Solo 27% con `s_libre ≥ 1.4` → veredicto crudo: 🔴 ROJO

**Este veredicto no se acepta como respuesta de E0.** Antes de correrlo se
validó el clasificador con un caso de control de verdad conocida, y falló.
Ver `avances/avance-1.1.md` para el detalle completo.

## Resumen del problema

Prueba de control: se tomó una foto real del corpus y se redujo 4× con un
filtro antialias real (Lanczos, en JPEG y en PNG por separado). Por
construcción, esa imagen reducida **no debería tener margen recuperable**
(`f_eff/f_N` debería acercarse a 1.0, tipo "muro"). El clasificador midió
prácticamente lo mismo que en la imagen original sin tocar (`f_eff/f_N` ≈
0.75–0.81 en ambos casos, "suave" en ambos).

Causa probable: las imágenes naturales son aproximadamente auto-similares en
su espectro de potencia (ley ~1/f² que se conserva al cambiar de escala). Un
filtro de antialias real (no un muro ideal) no deja una firma espectral lo
bastante distinta de la caída natural de cualquier foto, medida solo dentro
del espectro normalizado de una única imagen aislada.

## Qué NO se puede concluir todavía

- No se puede afirmar que el corpus tenga o no tenga margen real.
- No se puede confiar en la etiqueta `tipo_corte` de `resultados_e0.csv` tal
  como está.

## Siguiente paso

Decidir con el usuario cómo seguir (ver `avances/avance-1.1.md`, sección
"opciones"). No se avanza a E1 con esta puerta sin resolver.
