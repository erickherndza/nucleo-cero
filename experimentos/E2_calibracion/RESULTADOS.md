# E2 — Resultados

**Estado: CERRADA. Veredicto 🔴 ROJO, confirmado con dos métodos independientes.**

Esta es la puerta que más importa según METODO.md §8: "el único resultado
que invalida la propuesta de valor es E2 en rojo".

## Método

Mismo modelo directo que E1 (`σ_psf=1.2`, `factor=2`, `σ_ruido=0.01`),
recorte central 1024×1024 de cada una de las 10 fotos reales, grilla de
regiones 128×128 (640 regiones). Se probaron DOS operacionalizaciones
independientes de τ:

**v1 — corte de frecuencia global** (`tau_frecuencia`): energía por encima
del límite recuperable de la imagen sobre energía por debajo.
Correlación de Spearman: **−0.42**.

**v2 — sensibilidad al ruido, normalizada** (`tau_incertidumbre`): cada
imagen se reconstruyó 4 veces con 4 realizaciones de ruido independientes
(misma escena); τ = dispersión entre esas reconstrucciones dividida por la
estructura local (desviación estándar de la reconstrucción media en esa
región) — un coeficiente de variación, no una varianza cruda (la varianza
cruda, sin normalizar, tenía el mismo problema: se probó y se descartó, ver
`avances/avance-1.5.md`).
Correlación de Spearman: **−0.84**, y esta vez las 10 imágenes coinciden
sin excepción (−0.69 a −0.89 cada una — ninguna cerca de cero, ninguna
positiva).

## Resultado

**Ambos métodos dan correlación NEGATIVA y consistente.** Esto ya no
parece ser un problema de cómo se mide τ (se intentaron dos enfoques
conceptualmente distintos, uno basado en frecuencia y otro en sensibilidad
al ruido por bootstrap, y coinciden en el signo). Parece ser una propiedad
real de la reconstrucción con Richardson-Lucy puro (sin regularización
TV/capa 3): las regiones con más estructura/contraste real se reconstruyen
con MENOS error, y las regiones lisas/de bajo contraste acumulan MÁS error
relativo — lo opuesto a la intuición de que "lo liso es seguro, lo
detallado es arriesgado".

## Por qué pasa esto (hipótesis, consistente con literatura de RL)

Richardson-Lucy sin regularización espacial no tiene ningún prior que
suavice zonas planas: en bordes/textura fuerte, el gradiente de la
verosimilitud está bien condicionado y el algoritmo converge rápido y
preciso; en zonas lisas, hay poca señal real que domine al ruido, y cada
iteración amplifica un poco de ruido residual sin nada que lo corrija —
error absoluto pequeño (porque el rango de valores ahí es chico) pero
relativamente más lejos de la verdad que en zonas con estructura fuerte.

## Qué significa (METODO.md §8)

No se avanza a integración con este resultado sin resolver. Dos caminos
razonables, no excluyentes: (a) el propio algoritmo necesita la capa 3
(regularización TV) que todavía no existe — quizás τ empiece a predecir
bien recién cuando exista algo que de verdad "rellene" de forma desigual
según la confianza, en vez de RL puro tratando toda la imagen igual; o
(b) construir el certificado alrededor de la relación real medida (más
estructura = más confianza, no menos) en vez de pelear contra ella.

## Pendiente

Ver `avances/avance-1.5.md` para la decisión con el usuario sobre cómo
seguir.
