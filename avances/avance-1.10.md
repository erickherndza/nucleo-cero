# Avance 1.10 — primera prueba con ráfaga real: el certificado detecta que el modelo no ajusta bien

**Fecha:** 2026-09-12

## Qué se hizo

Primera corrida del MVP en **modo producción** (avance-1.9 solo lo había
probado en modo validación, sintético). El usuario subió 3 fotos reales
de una ráfaga (`experimentos/E3_rafaga/rafaga_real/`, 4000×2256, tomadas
con ~1-2s de diferencia entre sí, mismo encuadre): dos personas de pie
frente a una tienda "Claro".

## Resultado

```
Diversidad de fase: x=0.74, y=0.48  ->  repartidas (bien, hay aliasing desplegable)
sigma_n inicial (MAD) = 0.00234
discrepancia medida = 8.62  ->  sigma_n corregido = 0.00702 (tope de seguridad 3x, no el valor "libre")
Certificado: ratio residuo/ruido = 3.07  ✗ INCONSISTENTE
tau = 0.1303 -> "Comercial" (calculado igual, sin condicionar a la consistencia)
```

En las pruebas sintéticas (avance-1.8, 1.9) la discrepancia medida rondaba
0.6-0.7 (el modelo se ajustaba bien). Aquí salió **8.62** — tan alta que
el factor de recalibración de σ_ruido chocó contra el tope de seguridad
del código (`min(3.0, ...)`), sin el cual el sistema habría intentado
multiplicar σ_ruido por más de 8x.

## Diagnóstico (no es que el script esté roto)

Se verificó por separado si la pose estimada realmente explica la
diferencia entre frames:

- Diferencia media cruda entre frame 1 y 2: **0.0243**
- Diferencia media tras alinear frame 1 con la pose estimada: **0.0090**
  (baja a más de un tercio — la estimación de pose SÍ está funcionando,
  no es un fallo de E3)

Pero 0.0090 sigue siendo mayor que la σ_ruido corregida (0.00702) — hay
algo más que pura traslación/rotación de cámara entre los frames. La
explicación más probable: son fotos de **personas de pie**, no una escena
rígida — el propio sujeto se mueve un poco entre tomas (respiración,
balanceo, parpadeo), además de posibles pequeños cambios de exposición
entre disparos. El modelo (`A = D·H·W_k`, con `W_k` una transformación
afín global) asume que **solo la cámara se mueve y la escena es rígida**
— con sujetos vivos, esa suposición no se cumple del todo.

## Por qué esto es un resultado bueno, no un fallo

**El certificado hizo exactamente lo que tiene que hacer**: no ocultó la
inconsistencia. A diferencia de E0/E1/E2 (que fueron degradaciones
sintéticas con verdad conocida), este es el primer caso donde no hay
verdad de referencia — solo el certificado para saber si confiar en el
resultado. Y el certificado dijo, correctamente, "no confíes del todo en
esto".

Revisando la imagen reconstruida (`..._reconstruida.png`): no se ven
artefactos evidentes de fantasma/duplicado — probablemente porque los
pesos robustos de Tukey, DENTRO de la optimización, ya bajaron el peso de
las zonas inconsistentes (rechazo de outliers, METODO.md). Pero
`consistencia()` (la función que arma el certificado) mide el residuo SIN
esos pesos robustos — es una medida más estricta y "cruda" que lo que el
optimizador realmente usó para reconstruir. Esto explica por qué la imagen
se ve razonable pero el certificado igual marca inconsistencia: son dos
medidas distintas, y el certificado, a propósito, es el más desconfiado de
las dos.

## Gap encontrado en el MVP (a corregir)

`_nivel_servicio()` en `mvp.py` calcula el nivel de servicio ("Comercial",
etc.) **solo a partir de τ**, sin mirar si `ratio_residuo_ruido` marcó
inconsistencia. Eso significa que el informe de entrega puede decir
"Comercial" con la misma confianza aunque el propio certificado haya
dicho "✗ inconsistente" un renglón arriba — technically ambas líneas están
en el informe, pero nada fuerza a leerlas juntas. Antes de usar esto con
un cliente real, el nivel de servicio debería degradarse (o marcarse "no
confiable") cuando la consistencia falla, no reportarse como si nada.

## Estado

Modo producción probado por primera vez con datos reales. Funciona de
punta a punta (informe, imagen reconstruida, comparación), pero reveló
un caso real donde el modelo no ajusta perfectamente — y reveló que el
MVP no comunica esa falla de forma suficientemente clara en el nivel de
servicio reportado.

## Pendiente

1. Corregir `_nivel_servicio()` para que dependa también de la
   consistencia, no solo de τ.
2. Decidir si vale la pena, para ráfagas con sujetos vivos, robustecer
   aún más el rechazo de outliers, o aceptar que el método es más
   confiable en escenas verdaderamente estáticas (arquitectura, objetos,
   paisajes) y comunicarlo así.
3. No se probó el perfil `completo` sobre esta ráfaga real todavía
   (tomaría ~10+ min) — podría no cambiar la conclusión, dado que el
   problema no es de iteraciones sino de que el modelo de movimiento
   rígido no explica toda la diferencia entre frames.
