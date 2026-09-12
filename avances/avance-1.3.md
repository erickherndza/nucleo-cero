# Avance 1.3 — E1 construido y corrido; una métrica sólida, otra sin resolver

**Fecha:** 2026-09-12

## Qué se hizo

Se construyó `experimentos/E1_deconvolucion/`: modelo directo simulado
(`y = D(H·x) + ruido` con PSF gaussiana y decimación por promedio, ambas
conocidas), Richardson-Lucy generalizado para ese operador, bicúbica como
línea base, y métricas (PSNR, SSIM, ancho de banda). 12 tests unitarios,
incluida una prueba de producto punto para el operador adjunto (si el
adjunto está mal, RL converge mal sin dar ningún error visible — se validó
numéricamente antes de confiar en el algoritmo).

Se corrió sobre las 10 fotos reales de cámara que subió el usuario
(recorte 512×512 más nítido de cada una, `σ_psf=1.2px`, `factor=2`,
`σ_ruido=0.01`).

## Hallazgo 1 (real, con impacto en el diseño): RL sin parada correcta empeora

Primera corrida de prueba (antes del corpus completo): en un caso sintético
fácil, Richardson-Lucy con 25 iteraciones y "parar cuando el residuo deja
de bajar" dio **peor** PSNR que la sola bicúbica (32.1 dB vs 35.3 dB). Se
diagnosticó iteración por iteración: RL supera a bicúbica en la iteración 1
(38.3 dB) y luego se degrada monótonamente — el residuo interno sigue
bajando todo el tiempo (se ajusta cada vez mejor al RUIDO), así que nunca
"se estanca" aunque ya esté sobreajustando. Esto es exactamente lo que
CLAUDE.md advierte ("más iteraciones no es más nitidez, es más artefacto"),
y confirma por qué el propio Debug del proyecto pide reproducir/aislar
antes de aceptar un número.

**Fix:** parada por principio de discrepancia de Morozov — frenar en cuanto
el residuo de los datos llega al nivel de ruido CONOCIDO (`σ_n²`), no
cuando deja de mejorar. Con esto, RL gana consistente sobre bicúbica.
Documentado como test explícito (`test_richardson_lucy_sin_parada_temprana_empeora`)
para que si alguien "simplifica" esto después, el test lo agarre.

## Hallazgo 2 (bug real, corregido): unidades de la densidad espectral

`espectro_radial` no dividía por `H·W`, así que la "potencia" no estaba en
las mismas unidades que una varianza de intensidad — compararla contra
`σ_ruido²` salía mal por un factor de ~262 000 (el tamaño del recorte).
Esto hacía que `banda_recuperada` diera exactamente 0% en las 10 imágenes,
sin excepción — la uniformidad total (ni una imagen distinta) fue la pista
de que era un bug de unidades, no un hallazgo. Se corrigió normalizando a
densidad espectral de potencia (Parseval) y se agregó un test que valida la
convención directamente: ruido blanco de varianza conocida debe medir esa
misma varianza, plano en frecuencia.

## Hallazgo 3 (sin resolver): `f_max_teorico` probablemente subestimado

Con las unidades corregidas, comparar el error de reconstrucción contra el
piso de ruido crudo seguía dando 0% — pero esta vez por una razón real, no
un bug: ninguna deconvolución baja el error hasta el nivel de ruido crudo
del sensor, porque el operador invertido amplifica ruido en el dominio de
la imagen. Se cambió el criterio de "banda recuperada" para comparar el
error contra la potencia de la **señal verdadera** en cada frecuencia
(SNR≥1, criterio estándar), y con eso las mediciones por imagen se vuelven
sensatas individualmente (0% sin relación con la verdad, 100% si la
reconstrucción es perfecta — ambos casos probados).

Pero al comparar contra `f_max_teorico`, la fracción recuperada **supera el
100%** en 9 de 10 imágenes reales (hasta 197%). Recuperar más de lo que la
teoría dice que es el límite no es posible — así que `f_max_teorico` está
mal calibrado, probablemente por un desajuste de escala de frecuencia entre
la grilla de alta resolución (donde se mide el espectro de la verdad) y la
grilla de baja resolución (donde se inyectó el ruido conocido). No se
investigó más a fondo en este avance.

## Estado de la puerta E1

**No cerrada del todo.** Lo que sí se puede afirmar con confianza:
Richardson-Lucy con PSF conocida y parada por discrepancia gana sobre
bicúbica de forma consistente (+3.47 dB promedio, 80% de las imágenes sobre
el umbral de +2dB — ese criterio de METODO.md §3 se cumple). Lo que NO se
puede afirmar todavía: si la banda recuperada llega al 80% del límite
teórico — la métrica que lo mediría tiene una inconsistencia interna sin
resolver (probablemente en `f_max_teorico`, no en la reconstrucción misma).

No se acepta un veredicto verde completo de E1 con una métrica que da
resultados imposibles (>100%). Ver `experimentos/E1_deconvolucion/RESULTADOS.md`.

## Siguiente paso

Pendiente de decidir con el usuario: (a) invertir tiempo en corregir el
desajuste de escala de `f_max_teorico` antes de cerrar E1 formalmente, o
(b) aceptar la ventaja sobre bicúbica como evidencia suficiente para seguir
adelante (por ejemplo hacia E1-b, estimación de PSF real en vez de
conocida, o hacia E2) y dejar el ancho de banda teórico como trabajo
pendiente no bloqueante.
