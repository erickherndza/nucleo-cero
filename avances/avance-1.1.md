# Avance 1.1 — E0 corrido sobre el corpus real; el instrumento falla su propia validación

**Fecha:** 2026-09-12

## Qué se hizo

1. Se corrió `medir.py` sobre las 50 imágenes reales colocadas en
   `experimentos/E0_margen/corpus/` (49 medidas, 1 omitida).
2. Resultado crudo: 100% clasificadas "suave", solo 27% con
   `s_libre ≥ 1.4` → veredicto crudo 🔴 ROJO (umbral 60%).
3. Antes de aceptar ese número, se hizo una prueba de control con verdad
   conocida (algo que el propio METODO.md exige implícitamente: no
   interpretar a favor un resultado sin verificarlo — §0 y CLAUDE.md/Debug).
   Se tomó una foto real del corpus, se redujo 4× con Lanczos (antialias
   real), y se volvió a medir. Se repitió en JPEG y en PNG por separado para
   descartar que fuera un artefacto de compresión.

## Resultado de la prueba de control

| Caso | `f_eff/f_N` | `tipo_corte` |
|---|---|---|
| Foto original sin tocar (JPEG) | 0.746 | suave |
| Misma foto reducida 4× con Lanczos | 0.787 | suave |
| PNG original sin tocar | 0.801 | suave |
| Mismo PNG reducido 4× con Lanczos | 0.813 | suave |

Una imagen deliberadamente reducida con antialias real **debería** medir
`f_eff/f_N` cercano a 1.0 (sin margen — el filtro se diseñó para llenar
exactamente hasta el nuevo Nyquist). En cambio, midió prácticamente igual
que la imagen sin reducir. El clasificador no distinguió los dos casos.

## Por qué falla (hipótesis, no solo un bug de código)

Las imágenes naturales son aproximadamente auto-similares en su espectro de
potencia: la ley de caída ~1/f² se conserva al cambiar de escala. Un filtro
de antialias real (Lanczos, bicúbico, caja) no es un muro ideal — tiene una
banda de transición. Al normalizar el espectro de la imagen reducida contra
*su propio* Nyquist, la forma de caída se parece demasiado a la de cualquier
foto natural sin procesar. Medir solo la forma del espectro de una imagen
aislada, sin ninguna referencia externa, puede no bastar para separar "nunca
se redujo" de "ya se redujo con un filtro decente" — que es exactamente la
distinción que E0 necesita para decidir si hay margen recuperable.

Esto no invalida la pregunta de E0 (¿hay margen en las imágenes de
clientes?). Invalida la *herramienta* actual para responderla con confianza.

## Estado de la puerta E0

**No cerrada.** El veredicto rojo del corpus no se acepta como respuesta —
sería interpretar a favor un instrumento que ya se sabe que falla en un caso
de control simple. `RESULTADOS.md` queda marcado como "instrumento
cuestionado", no como rojo ni verde.

## Opciones para seguir (pendiente de decidir con el usuario)

1. **Reforzar el clasificador** — en vez de comparar niveles absolutos de dB,
   ajustar la tendencia natural de caída (ley de potencia) en una banda de
   referencia de baja frecuencia y medir el *residuo* frente a esa tendencia,
   no el nivel absoluto. Más trabajo, no garantiza que resuelva la
   auto-similitud de fondo.
2. **Usar pistas independientes del espectro** — metadata EXIF (software de
   edición, dimensiones originales si están), y el diagnóstico de rejilla
   JPEG 8×8 que el propio METODO.md ya prevé en Fase A punto 5, como señal
   adicional de que la imagen pasó por un pipeline de compresión/redimensión.
3. **Redefinir qué mide E0** — en vez de clasificar la *causa* (suave/muro/
   plegado) por imagen, medir directamente si la deconvolución (E1) logra
   ganancia real medible sobre bicúbica en el corpus real, y dejar que el
   propio E1 (que compara contra una verdad conocida en imágenes degradadas
   sintéticamente) sea la puerta que decide, en vez de intentar diagnosticar
   la causa de antemano con una imagen aislada.
4. **Aceptar la limitación e ir directo a E2** — E2 es "la puerta que
   importa" según el propio documento (§8: "el único resultado que invalida
   la propuesta de valor es E2 en rojo"). Se podría tratar E0 como
   informativo/no bloqueante y avanzar, dejando la pregunta de margen para
   resolverse empíricamente en E1/E2.

No se eligió ninguna opción todavía — se necesita decisión del usuario antes
de seguir construyendo.
