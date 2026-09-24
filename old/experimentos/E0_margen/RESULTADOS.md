# E0 — Resultados

**Estado: CERRADA. Veredicto 🔴 ROJO.**

Corpus real: 50 imágenes de cliente (WhatsApp, descargas web, escaneos,
fotos de móvil), 49 medidas (1 omitida por error de lectura). Medido con
`medir.py` v2 (clasificador reforzado — ver `avances/avance-1.2.md` para el
detalle de la validación). Salida cruda: `resultados_e0.csv`.

## Validación del instrumento antes de aceptar el veredicto

La v1 del clasificador falló una prueba de control (ver `avance-1.1.md`):
no distinguía una imagen recién reducida con antialias real de una sin
tocar. Se corrigió midiendo el residuo contra la tendencia natural de caída
del espectro (ley de potencia ajustada en banda de referencia), en vez de
niveles absolutos de dB. Validado contra tres casos de verdad conocida:

| Caso de control | Resultado | ¿Correcto? |
|---|---|---|
| Foto real sin tocar | suave, s_libre=1.34 | — (línea base) |
| Misma foto reducida 4× con Lanczos (antialias real) | **muro** | ✅ corregido (v1 daba "suave", igual al original) |
| Misma foto con desenfoque gaussiano genuino (sin redimensionar) | suave, s_libre=1.52 (sube, como se espera con más blur) | ✅ |
| Misma foto decimada sin antialias (aliasing real) | suave (debería ser "plegado") | ❌ limitación conocida — no bloquea el veredicto de esta puerta porque el criterio de E0 solo depende de la fracción "suave" |

## Resultado sobre el corpus real

- 49 imágenes medidas
- Distribución: **86% suave**, 8% muro, 6% ambiguo
- De las "suave", solo **13/49 (27%)** alcanzan `s_libre ≥ 1.4`
- El resto de las "suave" se agrupa justo debajo del umbral (mayoría entre
  1.25 y 1.39) — no son outliers aislados, es la mayoría del corpus.

**VEREDICTO: 🔴 ROJO** (umbral verde: ≥ 60% con `s_libre ≥ 1.4`; el corpus da 27%)

## Qué significa esto (METODO.md §3, §8)

Rojo en E0 **no cierra el proyecto**. Significa que, para las imágenes reales
de este cliente, el producto vendible con más fundamento es **limpieza y
restauración** (ruido, artefactos de compresión, color, desenfoque leve
recuperable), no "aumento de resolución" como titular — el margen honesto de
resolución existe pero es modesto (`s_libre` típico ≈ 1.25–1.4×, no 2×+).

## Limitaciones conocidas del instrumento

- El detector de "plegado" (aliasing por decimación sin antialias) no está
  validado y probablemente subestima esa categoría — no afecta este
  veredicto (que depende de la fracción "suave", no de "plegado"), pero no
  hay que confiar en las filas `plegado` de `resultados_e0.csv` porque
  prácticamente no existen ("muro" y "ambiguo" pueden estar absorbiendo
  casos que en realidad son aliasing).
- Un solo caso de control con antialias real (Lanczos) fue validado. No se
  probó bicúbica, box, ni el resize real que usan WhatsApp/navegadores.
