# Avance 1.6 — E2 cerrada en verde: el problema era el error absoluto, no τ

**Fecha:** 2026-09-12

## Contexto

Tras dos rojos consecutivos en E2 (avance-1.4: τ por frecuencia, corr=-0.42;
avance-1.5: τ por sensibilidad al ruido, corr=-0.84, más fuerte y
consistente todavía), el usuario pidió comparar el costo/beneficio de tres
caminos: construir la capa 3 (TV/ADMM), aceptar la relación invertida y
construir el certificado alrededor de ella, o pausar a repensar. Antes de
elegir, se pidió entender la diferencia real entre los dos τ ya probados.

## El hallazgo que cambió todo

Al explicar la diferencia entre los dos τ, se verificó directamente (no de
memoria) la relación entre "cuánta estructura real tiene una región" (la
desviación estándar de la VERDAD, no de la reconstrucción) y el error. La
correlación fue **+0.90**: más detalle real → más error ABSOLUTO. Esto
resolvió una contradicción que había en la explicación previa (se había
dicho verbalmente que "las zonas lisas acumulan más error", que resultó
ser al revés).

La causa: `error_rms` (RMS sin normalizar) escala con el rango de valores
de la región — una zona con mucho contraste tiene más "espacio" para
equivocarse en términos absolutos, aunque la reconstrucción sea igual de
buena en relación a su propia escala. Mientras tanto, **τ ya era un
cociente** (normalizado por estructura local, por diseño, para evitar
exactamente esta trampa — ver avance-1.5). Comparar un cociente contra una
cantidad sin normalizar es comparar unidades distintas: por eso salía
invertido, sin importar qué tan bien diseñado estuviera τ.

## La corrección (opción 4, no estaba en la lista original)

Se calculó el costo/beneficio de las tres opciones originales más esta
cuarta (corregir la métrica de error a relativa) usando el criterio que
pidió el usuario (contexto × tiempo / resultado). La opción 4 dominó por
un margen grande: costo mínimo (una función nueva, `error_relativo` =
error_rms / desviación estándar de la verdad), resultado ya verificado
antes de proponerla (no una apuesta).

Se implementó `error_relativo` en `nucleo.py`, con dos tests que
verifican exactamente la propiedad que la motivó: invariancia de escala
(escalar toda la región por una constante no debe cambiar el error
relativo) y que, con el MISMO error absoluto, una región lisa da error
relativo más alto que una texturada (justo lo que `error_rms` solo no
podía distinguir).

## Resultado final sobre el corpus real (640 regiones, 10 imágenes)

| Comparación | Correlación de Spearman |
|---|---|
| τ (incertidumbre) vs. error absoluto | −0.84 |
| **τ (incertidumbre) vs. error relativo** | **+0.82** |

9 de 10 imágenes individualmente sobre el umbral de 0.6 (rango +0.72 a
+0.98); una excepción en +0.39.

**VEREDICTO E2: 🟢 VERDE.**

## Por qué esto no es "forzar el número"

La corrección no cambia τ, no cambia el algoritmo de reconstrucción, no
ajusta ningún umbral, y no se descartó ningún dato. Cambia únicamente
CÓMO se mide el error de comparación, para que quede en las mismas
unidades (relativas) que τ — que además es la forma más honesta de
comunicarle esto a un cliente real: "esta región es tan fiable como puede
serlo dado lo que hay ahí", no un número de error absoluto sin contexto de
cuánto contraste tenía la región para empezar.

## Estado del proyecto

Con E0 (rojo, reposicionó el producto hacia limpieza/restauración), E1
(parcial — ventaja sobre bicúbica confirmada, ancho de banda teórico
pendiente) y E2 (verde) corridas, según METODO.md §9 sigue E3 (ráfaga) y
E4 (recurrencia interna), o E5 si se decide que ya hay suficiente para
integrar un pipeline mínimo con certificado. Pendiente de decidir con el
usuario cuál sigue.

## Pendiente

- Entender la imagen con correlación baja (+0.39) antes de dar el método
  por cerrado en producción.
- La limitación de E1 (banda recuperada vs. límite teórico, avance-1.3)
  sigue sin resolver — no bloqueó E2 porque E2 usó τ por incertidumbre,
  no las métricas de E1 directamente, pero sigue pendiente si se quiere
  cerrar E1 del todo.
