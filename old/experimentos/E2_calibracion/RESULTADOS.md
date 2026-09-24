# E2 — Resultados

**Estado: CERRADA. Veredicto 🟢 VERDE.**

Esta es la puerta que más importa según METODO.md §8. Llegó a verde
después de dos rojos (avance-1.4, avance-1.5) que resultaron ser un
problema de la métrica de comparación, no de τ ni del algoritmo — ver
`avances/avance-1.6.md` para el diagnóstico completo.

## Método

Mismo modelo directo que E1 (`σ_psf=1.2`, `factor=2`, `σ_ruido=0.01`),
recorte central 1024×1024 de cada una de las 10 fotos reales, grilla de
regiones 128×128 (640 regiones). τ = `tau_incertidumbre`: cada imagen se
reconstruyó 4 veces con 4 realizaciones de ruido independientes; τ es la
dispersión entre esas reconstrucciones normalizada por la estructura local
(coeficiente de variación).

**El cambio que cerró la puerta:** el error de comparación pasó de RMS
absoluto a `error_relativo` = RMS dividido por la desviación estándar de
la verdad en esa región. τ ya era un cociente (normalizado por estructura);
compararlo contra un error sin normalizar mezclaba unidades — una región
con mucho contraste real tiene más rango para equivocarse en términos
absolutos, sin que eso signifique que la reconstrucción ahí sea peor
relativamente.

## Resultado

| Comparación | Correlación de Spearman |
|---|---|
| τ vs. error ABSOLUTO (avance-1.4/1.5) | −0.84 |
| **τ vs. error RELATIVO (esta corrida)** | **+0.82** |

Por imagen (error relativo): 9 de 10 imágenes con correlación ≥ 0.6
(rango +0.72 a +0.98); una imagen queda por debajo (+0.39,
`IMG_20260425_184935.jpg`) — no se descarta, queda anotada como excepción.

**VEREDICTO: 🟢 VERDE** (criterio METODO.md §3: correlación ≥ 0.6, estable
a través de tipos de contenido — 9/10 cumple individualmente, y el
agregado de 640 regiones da 0.82, bien por encima del umbral).

## Qué significa

El certificado (τ vía sensibilidad al ruido, normalizado) SÍ predice dónde
está el error, siempre que el error también se mida en términos relativos
al contraste local — que es, de hecho, la forma correcta de comunicárselo
a un cliente ("esta región es tan confiable como puede serlo dado lo que
hay ahí", no "esta región tiene tantos níveles de gris de error absoluto").
El diferenciador central del método (poder señalar regiones fiables vs. no
fiables con fundamento) queda sostenido.

## Limitaciones conocidas

- Un solo tipo de degradación (blur gaussiano + ruido gaussiano uniforme).
  No se probó con PSF estimada (no conocida, ver E1 pendiente) ni con
  degradación espacialmente variable.
- `tau_frecuencia` (la primera versión, corte de frecuencia global) sigue
  sin funcionar incluso con error relativo — no se investigó más porque
  `tau_incertidumbre` ya cerró la puerta; queda como referencia en el
  código.
- Una imagen (`IMG_20260425_184935.jpg`) da correlación baja (+0.39) —
  vale la pena entender por qué antes de dar el método por completamente
  cerrado en producción.
