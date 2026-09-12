# E2 — Resultados

**Estado: CERRADA. Veredicto 🔴 ROJO — y no es solo "sin correlación", es correlación inversa.**

Esta es la puerta que más importa según METODO.md §8: "el único resultado
que invalida la propuesta de valor es E2 en rojo". Por eso este resultado
no se suaviza.

## Método

Mismo modelo directo que E1 (`σ_psf=1.2`, `factor=2`, `σ_ruido=0.01`) sobre
un recorte central de 1024×1024 de cada una de las 10 fotos reales,
reconstruido con Richardson-Lucy. Cada imagen se dividió en una grilla de
regiones de 128×128 (64 regiones/imagen, 640 en total). Por región se
midió:

- **τ** (descomposición rango-núcleo operativa, METODO.md §2): energía en
  frecuencias por encima del corte recuperable de la imagen (`f_c`, medido
  igual que `banda_recuperada` en E1) sobre energía por debajo.
- **error real**: RMS entre la región reconstruida y la verdad (posible
  porque esto es sintético — se conoce la verdad).

## Resultado

**Correlación de Spearman global: −0.42** (se esperaba ≥ +0.6 para verde).
Por imagen, 8 de 10 dan correlación **negativa**, varias fuertes (−0.92,
−0.79, −0.77, −0.71, −0.69).

Por cuartil de τ (agregado de las 640 regiones):

| Cuartil de τ | τ medio | error medio |
|---|---|---|
| 25% más bajo | 0.028 | 0.0214 |
| 25–50% | 0.051 | 0.0260 |
| 50–75% | 0.072 | 0.0206 |
| **25% más alto** | **0.227** | **0.0128** |

Las regiones con τ MÁS ALTO tienen el error MÁS BAJO. Es lo contrario de lo
que el certificado debería hacer.

## Diagnóstico (antes de aceptar esto como un fallo del concepto de τ)

METODO.md §8 pide revisar la segmentación antes de asumir que τ no sirve.
Hipótesis más probable, no confirmada con más experimentos: la
descomposición operativa usada (corte de frecuencia único, global por
imagen) no mide incertidumbre — mide **cuánto detalle real tiene la
región**. Una región con bordes y textura fuerte tiene mucha energía por
encima del corte, así que da τ alto — pero esa energía es señal real bien
condicionada, y Richardson-Lucy la reconstruye MEJOR, no peor (los bordes
fuertes le dan al algoritmo algo claro para "engancharse"). Las zonas lisas
dan τ bajo, pero acumulan más error relativo porque no hay señal fuerte que
domine al ruido residual — el algoritmo tiene menos de qué agarrarse.

Si esta hipótesis es correcta, el problema no es que "τ no correlaciona
con el error" en general — es que esta OPERACIONALIZACIÓN particular de τ
(un corte de frecuencia global, sin ponderar por cuánta señal real hay
localmente) confunde "mucho detalle" con "mucha incertidumbre", cuando en
la práctica son casi opuestos.

## Qué significa (METODO.md §8)

Esta es la puerta que de verdad importa. Un rojo aquí, sin resolver, dice
que el certificado no mide lo que afirma medir, y el producto pierde su
diferenciador frente a cualquier escalador convencional. No se avanza a E3
ni a integración con esto sin resolver, o sin decidir explícitamente
replantear el enfoque.

## Pendiente

Decidir con el usuario: intentar una operacionalización de τ que pondere
por señal local (no un corte global) antes de descartar el concepto, o
tratar esto como una señal seria de que el enfoque actual necesita
repensarse. Ver `avances/avance-1.4.md`.
