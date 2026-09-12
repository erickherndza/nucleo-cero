# Avance 1.2 — Clasificador reforzado, puerta E0 cerrada en rojo

**Fecha:** 2026-09-12

## Qué se hizo

Se reforzó `clasificar_corte` en `medir.py` (opción elegida por el usuario en
avance-1.1: "reforzar el clasificador"). Cambio central: en vez de comparar
el nivel de dB contra un piso/pico absolutos (que quedaba dominado por la
caída natural ~1/f² de cualquier imagen, sin importar su historia), ahora se
ajusta esa caída natural como una recta en log-frecuencia sobre una banda de
referencia de baja frecuencia (`f/f_N` en [0.05, 0.25]) y se mide el
**residuo** frente a esa tendencia extrapolada. Un corte adicional real
(filtro de antialias previo, desenfoque encima de lo natural) se ve como una
caída del residuo por debajo de la tendencia; el ancho de esa caída hasta
llegar al piso medido es lo que distingue "suave" de "muro".

## Validación (antes de volver a correr el corpus)

Tres pruebas de control con verdad conocida, todas nuevas en este avance:

1. **Foto reducida 4× con Lanczos** (antialias real, sin margen por
   construcción) → ahora da **"muro"**. En v1 daba "suave", indistinguible
   del original. Corregido.
2. **Foto con desenfoque gaussiano genuino, sin redimensionar** → sigue
   dando "suave", y `s_libre` sube de 1.34 a 1.52 (más blur → más margen
   recuperable), que es el comportamiento físicamente esperado.
3. **Foto decimada sin antialias** (aliasing real, debería dar "plegado")
   → sigue dando "suave". **No se resolvió.** Queda como limitación
   documentada en `RESULTADOS.md`. No bloquea el veredicto de E0 porque el
   criterio de la puerta (METODO.md §3) depende solo de la fracción
   "suave" + `s_libre`, no de detectar plegado correctamente.

También se notó una ambigüedad no resuelta: una imagen PNG descargada de la
web dio "muro" tanto antes como después de reducirla — no se pudo confirmar
si el archivo original ya venía redimensionado (lo más probable, dado que es
un "download.png" de navegador) o si el clasificador tiene un sesgo con
archivos PNG. No se investigó más a fondo por no ser crítico para el
veredicto agregado.

## Resultado sobre el corpus real (49 imágenes)

- Distribución: 86% suave, 8% muro, 6% ambiguo (antes: 100% suave — la v1
  no distinguía nada)
- 13/49 (27%) de las "suave" alcanzan `s_libre ≥ 1.4`
- **Veredicto: 🔴 ROJO** (umbral: 60%)

El número de imágenes que pasa el umbral (13) no cambió respecto a la
medición cruda de avance-1.1 — lo que cambió es que ahora hay confianza en
que las 42 imágenes restantes clasificadas "suave" realmente no tienen un
corte adicional detectable, en vez de que la etiqueta "suave" sea un
artefacto de un clasificador roto.

## Qué significa para el proyecto (METODO.md §3, §8)

Rojo en E0 no cierra el proyecto. El producto con más fundamento para este
cliente es limpieza y restauración (ruido, compresión, color, desenfoque
leve recuperable), no "aumento de resolución" como propuesta principal — el
margen existe pero es modesto (`s_libre` típico 1.25–1.4×). Ver
`experimentos/E0_margen/RESULTADOS.md` para el detalle completo y las
limitaciones conocidas del instrumento.

## Siguiente paso

Con E0 cerrada (aunque en rojo), toca decidir: ¿reposicionar el producto
ahora, o seguir a E1 (deconvolución) para confirmar que al menos el margen
modesto que sí existe (~1.3×) es recuperable en la práctica, antes de tomar
la decisión de reposicionamiento? METODO.md §9 sugiere seguir el orden
(E1 responde una pregunta distinta y más barata que E2), pero es una
decisión de negocio, no solo técnica — pendiente de hablarlo con el usuario.
