# Avance 1.4 — E2 corrido: rojo, y no uno cualquiera

**Fecha:** 2026-09-12

## Qué se hizo

Se construyó `experimentos/E2_calibracion/`: descomposición rango-núcleo
operativa (corte de frecuencia al límite recuperable de cada imagen, medido
igual que en E1), cálculo de τ y error real por región (grilla de 128×128
sobre un recorte de 1024×1024), y correlación de Spearman entre ambos sobre
las 10 fotos reales (640 regiones). 6 tests unitarios sobre las piezas
(descomposición, τ, correlación de Spearman) antes de correr sobre datos
reales — misma disciplina que E0/E1.

## Resultado

**Correlación de Spearman: −0.42** global (umbral verde: ≥ +0.6). Peor
todavía: 8 de 10 imágenes dan correlación NEGATIVA, varias fuertes (hasta
−0.92). Por cuartil de τ, el 25% de regiones con τ MÁS ALTO tiene el error
MÁS BAJO (0.013 vs 0.021–0.026 en los otros cuartiles) — el certificado
apunta exactamente al revés de donde están los problemas.

Esto es distinto de "sin correlación" (que ya sería rojo). Es una relación
sistemática e invertida, no ruido — la clase de resultado que MEDIR
tiene sentido tomarse en serio en vez de descartar como casualidad.

## Diagnóstico (no confirmado con más experimentos, es la hipótesis más
## probable)

METODO.md §8 pide revisar la segmentación antes de descartar τ. La
operacionalización usada (un corte de frecuencia único, global por imagen,
igual para toda la imagen) probablemente mide "cuánto detalle real tiene la
región" en vez de "cuánta incertidumbre tiene". Una región con textura
fuerte muestra mucha energía por encima del corte → τ alto — pero esa
energía es señal real, bien condicionada, y Richardson-Lucy la reconstruye
mejor (bordes fuertes = algo claro para anclar la deconvolución). Una zona
lisa muestra τ bajo, pero acumula más error relativo porque no hay señal
fuerte dominando el ruido residual.

Si es así, el defecto no está en la idea de τ (separar lo que los datos
sostienen de lo que no) sino en operacionalizarlo con un corte de
frecuencia GLOBAL sin ponderar por cuánta señal real hay LOCALMENTE en cada
región.

## Por qué esto importa más que los rojos anteriores

METODO.md §8 es explícito: "el único resultado que invalida la propuesta de
valor es E2 en rojo. Todos los demás reducen el alcance sin tumbar el
producto." E0 en rojo reposicionó el producto; E1 con una métrica sin
resolver era una limitación de medición. Esto es distinto: si el
certificado no predice el error, el diferenciador central del método
(poder decirle al cliente "esta región es fiable, esta no" con
fundamento) no existe todavía.

## Estado de la puerta E2

**Cerrada en rojo, con diagnóstico, sin resolver.** No se avanza a E3 ni a
integración sin resolver esto o decidir explícitamente replantear el
enfoque — así lo pide METODO.md §9 ("no avanzar de etapa con la puerta en
rojo").

## Pendiente de decidir con el usuario

1. Intentar una operacionalización de τ que pondere por señal local (por
   ejemplo, comparar la energía de alta frecuencia de la reconstrucción
   contra la de la propia región, no contra un corte global) antes de
   concluir que el certificado no funciona.
2. Tratar este resultado como una señal seria de que el enfoque de
   certificado necesita repensarse más a fondo, no solo un ajuste de
   fórmula.
3. Detenerse a revisar todo lo avanzado (avance-1.0 a 1.4) antes de seguir
   invirtiendo tiempo de construcción.
