# Avance 1.8 — experimento externo (Colab) integrado: E1+E3+capa3+certificado

**Fecha:** 2026-09-12

## Contexto

El usuario corrió un experimento propio en Google Colab
(`E1_E3_colab.py`, no versionado — vive en `~/Downloads/` fuera del repo)
que va bastante más allá de lo construido en esta sesión: implementa E3
(ráfaga) desde cero, y además construye la **capa 3 (regularización TV)**
que nosotros no habíamos tocado, con un τ mucho más fiel a la definición
de METODO.md §2 que nuestras dos versiones anteriores.

## Qué trae este script que nosotros no teníamos

1. **E3 real**: estimación de pose sub-píxel por pirámide (grueso→fino,
   terminando a escala completa), con la pose **dentro** del operador
   directo (`A_k = D·H·W_k`) en vez de alinear los datos — decisión de
   diseño correcta y documentada explícitamente: alinear los datos destruye
   la diversidad de fase que da la ganancia de resolución.
2. **Diagnóstico de diversidad de fase sub-píxel** (dispersión circular de
   fases): exactamente lo que METODO.md §3 (E3) pide medir y que nosotros
   no habíamos construido.
3. **Capa 3 (TV) de verdad**: variación total suavizada (√(∇²+ε), diferenciable),
   optimizada con Adam + decaimiento coseno — una alternativa más simple que
   el ADMM/primal-dual que sugiere CLAUDE.md, pero que evita la no-diferenciabilidad
   sin necesitar operadores proximales. Vale la pena anotarlo como una
   desviación deliberada de la especificación técnica, no un error.
4. **τ mucho más fiel al espíritu de METODO.md §2**: se reconstruye la
   MISMA escena con y sin regularización TV (misma inicialización), y
   τ = ‖x_con_TV − x_sin_TV‖ / ‖x_sin_TV‖ — literalmente "cuánta energía
   puso el regularizador en direcciones que el dato no ve". Esto es lo que
   nuestras dos versiones (`tau_frecuencia`, `tau_incertidumbre`, avances
   1.4-1.6) intentaban aproximar sin tener una capa 3 real que medir. Con
   la capa 3 construida, τ deja de ser una aproximación.
5. **Calibración de ruido por discrepancia** (principio de Morozov) —
   coincide con el mismo principio que usamos en `E1_deconvolucion/nucleo.py`
   (avance-1.3) para la parada de Richardson-Lucy, llegado de forma
   independiente. Buena señal de que es el enfoque correcto.
6. **Rechazo robusto real** (Tukey redescendente vía IRLS) para fusión de
   ráfaga con outliers (movimiento de objetos, etc.) — más principiado que
   "Charbonnier y confiar", según sus propios comentarios en el código.
7. **Validación contra verdad de referencia** en el mismo script (no solo
   certificado): PSNR/SSIM del método vs. bicúbica, puerta E1 explícita.

## Resultado reportado por el usuario (Colab, GPU)

```
Verdad de referencia: 512x288 · Ráfaga sintética: 6 frames a 256x144
E3: error medio de alineación 0.013 px LR  ->  🟢 VERDE (umbral 0.2 px)
Diversidad de fase: x=0.68, y=0.77  ->  fases bien repartidas
sigma_n: MAD=0.00515  ->  calibrado por discrepancia a 0.00380 (real: 0.00400, error 5%)
Certificado: consistencia ratio=1.00 ✓ | tau=0.1130 -> nivel "Comercial" (<=0.15)
E1: PSNR bicúbica 29.06dB | método 31.70dB | ventaja +2.64dB  ->  🟢 VERDE
    SSIM bicúbica 0.7893  | método 0.8652  | ventaja +0.0759
Tiempo total: 16.3s (GPU)
```

Tres puertas en verde en una sola corrida (E1, E3, y un certificado
consistente con τ en rango "Comercial"), con auto-calibración de ruido que
acertó dentro del 5% del valor real — resultado sólido.

## Por qué esto no se puede correr en el entorno del proyecto tal cual

`torch` no tiene wheel para Python 3.14 (la versión de `.venv/` en la raíz
del repo, usada por E0/E1/E2). Se creó un venv dedicado:

```
experimentos/E3_rafaga/.venv312/   (Python 3.12, torch 2.2.2 CPU, torchvision, matplotlib)
```

Nota: hubo que fijar `numpy<2` en este venv — torch 2.2.2 está compilado
contra la ABI de NumPy 1.x y con NumPy 2.x lanzaba un warning de
incompatibilidad binaria al importar (`_ARRAY_API not found`). Con
`numpy==1.26.4` importa limpio.

## Adaptación local

Se copió el script a `experimentos/E3_rafaga/experimento.py`, quitando la
dependencia de `google.colab.files` (reemplazada por lectura local de
imágenes) y forzando `torch.device("cpu")` explícito — CLAUDE.md: sin GPU,
sin Metal/MPS en el Mac de destino. `plt.show()` se reemplazó por guardar
la figura comparativa a archivo (no hay display en una sesión de terminal).

## Hallazgo de esta sesión: costo en CPU

Corriendo el mismo experimento (modo validación, imagen real de
`E1_deconvolucion/fuente/`) en el Mac, sin GPU: **más de 12 minutos de
CPU** solo para llegar a la fase de reconstrucción, frente a los 16.3s
totales reportados en Colab con GPU. Esto es un hallazgo real y relevante
para CLAUDE.md ("MacBook Pro 2015, 8GB, Intel... Sin GPU"): el enfoque de
optimización por descenso de gradiente con PyTorch (300+ iteraciones ×
varias reconstrucciones × estimación de pose piramidal con cientos de
pasos por nivel y por frame) puede no ser práctico en CPU en el hardware
de destino sin reducir drásticamente iteraciones/resolución, o sin
portarlo a una formulación cerrada/no iterativa por gradiente para el caso
CPU.

## Resultado de la corrida local (Mac, CPU, misma foto real de E1/E2)

```
Verdad de referencia: 512x288 · Ráfaga sintética: 6 frames a 256x144
E3: error medio de alineación 0.019 px LR  ->  🟢 VERDE (umbral 0.2 px)
Diversidad de fase: x=0.71, y=0.80  ->  fases bien repartidas
sigma_n: MAD=0.00618  ->  calibrado por discrepancia a 0.00408 (real: 0.00400, error 2%)
Certificado: consistencia ratio=1.00 ✓ | tau=0.1331 -> nivel "Comercial" (<=0.15)
E1: PSNR bicúbica 28.45dB | método 32.26dB | ventaja +3.81dB  ->  🟢 VERDE
    SSIM bicúbica 0.7882  | método 0.8837  | ventaja +0.0955
Tiempo total: 663.7 s (CPU, Mac)  vs  16.3 s (GPU, Colab)  ->  ~41x más lento
```

Se reproduce el resultado de Colab sobre una foto real distinta (una de las
10 de `E1_deconvolucion/fuente/`), con resultados igual de sólidos —
incluso mejor ventaja en E1 (+3.81dB vs +2.64dB) y calibración de ruido
más precisa (2% de error vs 5%). **El hallazgo de velocidad se confirma:
~41x más lento en CPU que en GPU**, con los parámetros originales
(6 frames, 300 iteraciones × 2 reconstrucciones, pirámide de pose a 4
niveles). Sin reducir estos parámetros, este pipeline no es práctico para
uso repetido en el Mac de destino.

## Siguiente paso

Construir un MVP local que empaquete este pipeline con parámetros
reducidos para viabilidad en CPU — hecho en `avance-1.9.md`
(`experimentos/E3_rafaga/mvp.py` + `nucleo_torch.py`).
