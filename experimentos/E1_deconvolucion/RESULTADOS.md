# E1 — Resultados

**Estado: PARCIAL. Una de las dos métricas de la puerta es confiable; la
otra tiene una inconsistencia interna sin resolver.**

Modelo directo simulado sobre 10 fotos reales de cámara (recorte 512×512 más
nítido de cada una): `σ_psf=1.2px`, `factor=2`, `σ_ruido=0.01`, PSF y ruido
**conocidos** (esto aísla la calidad de la deconvolución en sí, separado de
la estimación de PSF — METODO.md §3, E1). Salida cruda: `resultados_e1.csv`.

## Métrica 1 — Ventaja sobre bicúbica: CONFIABLE

- Ventaja media: **+3.47 dB** sobre bicúbica al mismo factor
- 80% de las imágenes superan el umbral de +2 dB (criterio verde de METODO.md §3)
- Validado con tests (`test_nucleo.py`): incluye un caso que reproduce y
  documenta un hallazgo real — sin parada por principio de discrepancia,
  Richardson-Lucy EMPEORA con más iteraciones (sobreajusta al ruido) aunque
  el residuo interno siga bajando. Con la parada correcta (frenar cuando el
  residuo del dato llega al nivel de ruido conocido), RL gana consistente.

## Métrica 2 — Banda recuperada / f_max teórico: NO CONFIABLE TODAVÍA

Primer intento: comparar el error de reconstrucción contra el piso de ruido
crudo `σ_n²` (lectura literal de METODO.md §4) → dio **0% en las 10
imágenes sin excepción**. Se investigó: no es un hallazgo real, es que
cualquier deconvolución amplifica ruido en el dominio de la imagen, así que
ningún método baja el error hasta el nivel de ruido crudo del sensor en
ninguna frecuencia — el criterio literal es demasiado estricto para
compararse contra el error de reconstrucción de una imagen, aunque sí tiene
sentido como definición de `f_max_teorico` (el límite antes de deconvolucionar).

Segundo intento: comparar el error contra la potencia de la **señal real**
en esa frecuencia (criterio SNR≥1, estándar en recuperación de señales) →
ahora da valores razonables por imagen individual (validado: 0% si no hay
relación con la verdad, 100% si la reconstrucción es perfecta), pero
agregado contra `f_max_teorico` la fracción recuperada **supera el 100%**
en 9 de 10 imágenes (hasta 197%). Recuperar más banda que el límite teórico
no tiene sentido — indica que `f_max_teorico` está subestimado, casi
seguro por un desajuste de escala de frecuencia entre la grilla de alta
resolución (donde se mide el espectro) y la grilla de baja resolución
(donde se añadió el ruido conocido). No resuelto todavía.

## Qué SÍ se puede afirmar con esta corrida

- Richardson-Lucy con parada por discrepancia recupera detalle real y mide
  mejor que bicúbica de forma consistente, con PSF conocida.
- No se puede afirmar todavía si alcanza el 80% del límite teórico
  predicho — la métrica que lo mediría no está validada.

## Pendiente

Resolver el desajuste de escala en `f_max_teorico` antes de aceptar un
veredicto verde/rojo completo de E1. Ver `avances/avance-1.3.md`.
