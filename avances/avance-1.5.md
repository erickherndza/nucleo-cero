# Avance 1.5 — segundo τ probado; misma correlación invertida, más fuerte

**Fecha:** 2026-09-12

## Qué se hizo

Por pedido del usuario ("probar una versión local de τ" tras el rojo de
avance-1.4), se construyó una segunda operacionalización de τ:
`tau_incertidumbre`, basada en sensibilidad al ruido en vez de un corte de
frecuencia global. Idea: reconstruir la MISMA escena varias veces con
distintas realizaciones de ruido (bootstrap) y medir cuánto varía la
reconstrucción por región — una región inestable ante el ruido es una
región donde el algoritmo tiene poco respaldo real de los datos.

Primer intento (varianza cruda entre reconstrucciones, sin normalizar):
**cayó en la misma trampa que `tau_frecuencia`**, confirmado con un test
antes de correr sobre el corpus real — la dispersión absoluta escala con
el contraste local, así que otra vez medía "cuánto detalle hay" en lugar
de "cuánta incertidumbre hay". Se corrigió normalizando por la estructura
local (desviación estándar de la reconstrucción media en la región): un
coeficiente de variación, no una varianza cruda. Con la normalización, un
caso de control sintético (mitad lisa / mitad texturada, verdad conocida)
mostró τ más alto en la zona lisa que en la texturada — el signo esperado
de una medida de confianza relativa.

## Resultado sobre el corpus real (10 fotos, 640 regiones, 4
## reconstrucciones bootstrap por imagen)

**Correlación de Spearman: −0.84** (peor que la v1, que dio −0.42). Las 10
imágenes coinciden sin excepción: todas entre −0.69 y −0.89, ninguna cerca
de cero ni positiva.

Esto es más fuerte y más consistente que el hallazgo de avance-1.4, no más
débil. Dos operacionalizaciones de τ conceptualmente distintas (frecuencia
vs. sensibilidad al ruido) coinciden en el signo — deja de parecer un
problema de cómo se mide τ y empieza a parecer una propiedad real de
Richardson-Lucy sin regularización: reconstruye MEJOR donde hay más
estructura/contraste real, y PEOR en zonas lisas, lo opuesto a la
intuición de que "lo liso es lo seguro".

## Diagnóstico actualizado

METODO.md §8 pide revisar la segmentación antes de descartar τ — ya se
revisó dos veces, con dos diseños distintos, y el signo no cambia. La
hipótesis ahora apunta menos a "τ está mal operacionalizado" y más a "el
algoritmo de reconstrucción (RL puro, sin capa 3/TV) tiene un
comportamiento de error que no coincide con la intuición de dónde está la
incertidumbre" — en zonas lisas, sin señal fuerte que domine al ruido, cada
iteración de RL amplifica ruido residual sin nada que lo corrija; en
bordes/textura fuerte, el algoritmo converge rápido y preciso.

## Estado de la puerta E2

Sigue en 🔴 ROJO, ahora con más confianza en que el hallazgo es real (dos
métodos independientes concuerdan) y no un artefacto de medición. Ver
`experimentos/E2_calibracion/RESULTADOS.md`.

## Pendiente de decidir con el usuario

1. Construir la capa 3 (regularización TV) antes de seguir midiendo τ —
   quizás el certificado empiece a predecir bien recién cuando el
   algoritmo de verdad "rellene" de forma desigual según la confianza, en
   vez de que RL puro trate toda la imagen por igual.
2. Aceptar la relación real medida (más estructura = más confianza, no
   menos) y construir el certificado alrededor de ESO, en vez de pelear
   contra ella — sería un certificado distinto al que describe METODO.md
   §2, pero fundamentado en lo que de verdad se observa.
3. Pausar y repensar el enfoque de certificado desde cero con este
   hallazgo repetido en la mesa.
