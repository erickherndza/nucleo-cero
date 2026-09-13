# CLAUDE.md — Método de Recuperación Certificada (nucleo-cero)

## Regla no negociable
Prohibido cualquier prior generativo aprendido (GAN, difusión, redes que
sinteticen píxeles). El núcleo se rellena por capas 0-3 en orden de
verificabilidad. No existe capa 4.

  capa 0  restricciones físicas (no-negatividad, soporte, rango)   coste τ = 0
  capa 1  deconvolución hasta el límite de ruido                   coste τ ≈ 0
  capa 2  mediciones adicionales (ráfaga, recurrencia interna)     ENCOGEN el núcleo
  capa 3  regularización conservadora (TV)                         coste τ > 0, medido

PyTorch (`experimentos/E3_rafaga/`) se usa como motor de optimización
diferenciable sobre el modelo clásico, NO como red generativa — no hay
pesos preentrenados ni aprendizaje de datos externos. No confundir "usa
una librería de deep learning" con "rompe la regla no negociable"; lo que
importa es si algo aprendido de fuera rellena información (prohibido).

## Esto es un programa experimental, no un plan de construcción
Cada etapa tiene una puerta con criterio verde y criterio rojo, definidos en
METODO.md §3. NO avanzar de etapa con la puerta en rojo. Si un resultado es
ambiguo, decirlo en vez de interpretarlo a favor.

Código de experimentos/ puede ser sucio y directo. Código de metodo/ no: ahí
solo entra lo que ya pasó su puerta. **Ahora mismo `metodo/` no existe
todavía** — nada ha pasado su puerta sin matices (ver estado abajo).

## Estado actual (verificado en esta sesión, no asumir el de documentos previos)

| Puerta | Estado | Detalle |
|---|---|---|
| **E0** — ¿hay margen real? | 🔴 **CERRADA, rojo** | avance-1.2: 27% del corpus con corte suave + s_libre≥1.4 (umbral 60%). No cierra el proyecto — reposiciona el producto hacia limpieza/restauración, no "aumento de resolución" (METODO.md §8). |
| **E1** — ¿deconvolución llega al límite? | 🟡 Parcial | Ventaja sobre bicúbica confirmada dos veces: numpy/RL (avance-1.3, +3.47dB) y torch/ráfaga (avance-1.8-1.12, +2.6 a +4.2dB). Ancho de banda vs. límite teórico sin resolver en la versión numpy (avance-1.3, `f_max_teorico` mal calibrado). Solo probado con PSF conocida, no estimada (falta E1-b). |
| **E2** — ¿el certificado predice el error? | 🟢 **CERRADA, verde** (una versión de τ) | avance-1.6: τ por sensibilidad al ruido (bootstrap, numpy) vs. error RELATIVO: +0.82 de correlación, 9/10 imágenes ≥0.6. **Ojo**: esta τ es DISTINTA de `tau_nucleo` del pipeline torch (diferencia con/sin TV) — esa nunca se validó por región contra error real, sigue abierta. |
| **E3** — ¿la ráfaga aporta resolución real? | 🟢 Verde en validación, con matices en producción | avance-1.8-1.12: modo validación (ráfaga sintética) en verde consistente. Modo producción con ráfaga real (avance-1.10): el certificado detectó inconsistencia real (sujetos vivos, no escena rígida) — el sistema funcionó bien al no ocultarlo, pero no es un "verde" sin condiciones. |

Hay **dos bases de código paralelas**: `experimentos/E0_margen`,
`E1_deconvolucion`, `E2_calibracion` (numpy puro, Python 3.14, `.venv/` en
la raíz) y `experimentos/E3_rafaga` (PyTorch, Python 3.12, venv dedicado
`.venv312/` — torch no tiene wheel para 3.14). Tienen definiciones de τ
distintas; no asumir que un hallazgo de una aplica a la otra sin verificar.

## Invariantes técnicos verificados en banco (no re-descubrir)
- Todo el cómputo en LUZ LINEAL (deshacer gamma al cargar, reaplicar al guardar).
- RAW sin auto-brillo, sin reducción de ruido, sin nitidez, gamma lineal
  (requisito de la especificación; ningún pipeline actual carga RAW todavía).
- UN SOLO operador directo (`A = D·H·W_k`) para síntesis y reconstrucción.
  Si difieren, se resuelve `A2·x = A1·x_real`: sesgo sistemático que no se
  va con más iteraciones.
- La pose que estima el alineador debe ser la DIRECTA (deforma la
  referencia hacia el frame k, no al revés). Estimarla al revés duplica el
  error de registro — síntoma: error de alineación ≈2× el desplazamiento real.
- Optimización iterativa (Richardson-Lucy o Adam) necesita parada por
  PRINCIPIO DE DISCREPANCIA (Morozov) — frenar cuando el residuo llega al
  nivel de ruido conocido, NO cuando "deja de bajar". Sin esto, RL empeora
  el resultado real aunque el residuo interno siga mejorando (avance-1.3).
- Todo bucle con Adam lleva decaimiento del paso (coseno) y reporta su
  deriva final. Con paso fijo orbita el óptimo e infla τ sin mejorar
  fidelidad — síntoma: la pérdida deja de bajar y empieza a subir.
- Charbonnier-TV: el `epsilon` importa, no es un detalle numérico.
  `epsilon≈1e-8` (≈ L1 puro) produce efecto acuarela/staircase a
  resoluciones grandes con pocos frames. `epsilon=1e-3` (con `LAMBDA_TV`
  más bajo, 6.0 en vez de 8.0) lo evita, y mejora el resultado en general,
  no solo a resoluciones grandes (avance-1.12).
- Puerta de fase preventiva: abortar la reconstrucción ANTES de optimizar
  si diversidad de fase < 0.30 — no basta con advertir y seguir
  (avance-1.11).
- τ debe compararse contra error de la MISMA normalización. Comparar un τ
  normalizado (cociente) contra error RMS absoluto da correlación
  invertida — no porque τ esté mal, sino porque las unidades no coinciden
  (avance-1.6).
- Procesamiento por tiles: objetivo <400MB de RAM con cualquier entrada.
  La especificación lo exige; ningún pipeline actual (numpy ni torch) lo
  implementa todavía.
- Sin GPU en local (MacBook Pro 2015 Intel, 8GB). Sin Docker para el
  pipeline. El pipeline torch corre en CPU local — ~41x más lento que GPU
  de Colab (avance-1.8); usar el perfil `rapido` de `mvp.py` para iterar,
  no el `completo`, salvo que se acepte esperar minutos u horas.
- Tras un rename de carpeta, los `activate` de los venvs quedan rotos
  (ruta absoluta grabada). Invocar el binario del venv directamente por
  ruta en vez de `source activate` (avance-1.11).

## Las dos métricas acompañan toda salida
consistencia: ‖D·H·x̂ − y‖ ≈ ‖ruido‖
τ:            ‖x_núcleo‖ / ‖x_rango‖
La consistencia sola NO basta: un generativo con proyección la aprueba.

## Debug
Reproducir → Aislar → Hipótesis → Verificar → Fix mínimo.

## Convenciones
Código y comentarios en español.
