# Método de Recuperación Certificada

> Especificación de construcción. **Reemplaza a `UppImagenScale.md`**, que quedó
> obsoleto: pedía un escalador con verificación, no un instrumento de medición.
>
> Base teórica: documento *Medido o Inventado*. Este documento no la repite —
> la aplica.

---

## 0 · Cómo usar este documento

Esto **no es un plan de construcción**. Es un **programa experimental falsable**.

La diferencia importa. Un plan de construcción asume que el método funciona y
solo hay que escribirlo. Aquí no lo asumimos: hay hipótesis que pueden ser
falsas, y la arquitectura del programa está diseñada para **descubrirlo barato y
temprano**.

Cada etapa tiene:

- una **pregunta** concreta que responde,
- lo **mínimo** que hay que construir para responderla,
- un **criterio de continuación** (verde),
- un **criterio de muerte** (rojo) — qué resultado significa *parar o redirigir*.

Las etapas están ordenadas por **riesgo descendente y coste ascendente**: la
primera responde la pregunta más peligrosa con el menor trabajo posible.

**No avanzar de etapa con la puerta en rojo.** Un rojo no es un fracaso del
proyecto; es información que costó días en vez de meses.

---

## 1 · Regla no negociable

El sistema **nunca** rellena el núcleo con un prior generativo aprendido.

El relleno ocurre por capas, en orden de verificabilidad, y se detiene cuando el
presupuesto de invención se agota:

| Capa | Qué es | Coste en τ |
|---|---|---|
| **0** | Restricciones físicas: no-negatividad, soporte finito, rango válido | 0 |
| **1** | Deconvolución hasta el límite de ruido | ≈ 0 |
| **2** | Mediciones adicionales: ráfaga, recurrencia interna, canal | 0 — *encogen* el núcleo |
| **3** | Regularización conservadora (TV / difusión anisotrópica) | > 0, medido |
| **4** | — | **No existe** |

Las capas 0–2 no gastan presupuesto. Solo la 3 gasta, y falla por **omisión**,
nunca por fabricación.

---

## 2 · Las dos métricas

Todo el sistema gira alrededor de estas dos, y ambas acompañan cada entrega.

**Consistencia** — no contradice la medición:

```
‖ D·H·x̂ − y ‖  ≈  ‖n‖
```

**Compromiso mínimo** — no invierte energía donde no puede ver:

```
τ  =  ‖x_núcleo‖ / ‖x_rango‖
```

La consistencia es **necesaria pero no suficiente**: un generativo con proyección
sobre el conjunto consistente la aprueba con nota perfecta. `τ` es la que
realmente sostiene la garantía.

---

## 3 · El programa experimental

### E0 — ¿Existe margen real en las imágenes de clientes?

**La pregunta más peligrosa del proyecto, y la más barata de responder.**

Si las imágenes reales resultan estar recortadas con filtro antialias, su banda
no fue atenuada sino **eliminada**, y no hay nada que recuperar. Todo el método
se apoya en que exista contenido atenuado bajo el ruido.

**Construir (mínimo):** carga de imagen, linealización, FFT, espectro de potencia
promediado radialmente, y un clasificador de la **forma del corte**.

**Corpus:** 50 imágenes representativas de lo que recibirás — fotos de WhatsApp,
imágenes de web, escaneos antiguos, fotos de móvil, capturas. No uses datasets
académicos aquí: la pregunta es sobre *tus* clientes.

**Medir, por imagen:**

- `f_eff / f_N` — dónde muere la energía real frente al Nyquist propio
- **tipo de corte**, que es el dato decisivo:

| Forma del corte | Causa | ¿Recuperable? |
|---|---|---|
| Caída suave, gaussiana | Desenfoque óptico o de movimiento | **Sí** — atenuado, presente |
| Muro abrupto | Reducción previa con antialias | **No** — eliminado |
| Energía plegada en Nyquist | Reducción sin antialias | Solo con múltiples fases |

- `s_libre = f_N / f_eff` cuando el corte es suave

> **Contraintuición clave:** una imagen borrosa tiene **más** margen honesto que
> una nítida. Lo blando es oportunidad; lo recortado limpiamente no.

**🟢 Verde:** ≥ 60% del corpus muestra corte suave con `s_libre ≥ 1.4`.

**🔴 Rojo:** mayoría con muro abrupto. **No significa cerrar el negocio** —
significa que el producto es *limpieza y restauración* (ruido, artefactos de
compresión, color), no resolución. Reposicionar y seguir, con honestidad sobre
el factor.

**Tiempo:** 1–2 días.

---

### E1 — ¿La deconvolución alcanza el límite predicho?

**Pregunta:** ¿podemos realmente llegar hasta donde `|H(f)| = σ_n`, o la
estimación de PSF es demasiado mala para que sirva?

**Construir:** estimación de PSF por función de dispersión de borde (ESF),
deconvolución Richardson–Lucy con regularización TV, y medición del ancho de
banda resultante.

**Prueba:** sobre imágenes degradadas sintéticamente, donde la verdad es conocida
y la PSF aplicada también. Empieza con PSF conocida (para aislar la
deconvolución), luego con PSF estimada (para evaluar la estimación).

**Medir:**

- Banda recuperada frente a `f_max` predicho
- PSNR y SSIM frente a bicúbica al mismo factor
- Error de la PSF estimada contra la real

**🟢 Verde:** banda recuperada ≥ 80% de `f_max` predicho, y ventaja ≥ 2 dB sobre
bicúbica de forma consistente.

**🔴 Rojo:** no supera a bicúbica consistentemente. Casi siempre el culpable es
la **estimación de PSF**, no la deconvolución. Aislar: si con PSF conocida sí
funciona, el problema es E1-b (estimación) y hay que resolverlo antes de seguir.

**Tiempo:** ~1 semana.

---

### E2 — ¿El certificado predice el error?

**Esta es LA puerta. Si falla, el diferenciador del producto no existe.**

**Pregunta:** cuando el sistema dice "esta región es incierta", ¿es ahí donde
están los errores?

**Construir:** descomposición rango–núcleo operativa, cálculo de `τ` global y por
región.

**Prueba:** degradar originales de alta resolución con el modelo directo,
reconstruir, y comparar `τ` por región contra el error real medido contra la
verdad.

**Medir:** correlación de Spearman entre `τ(región)` y `error(región)`.

**🟢 Verde:** correlación ≥ 0.6, estable a través de tipos de contenido.

**🔴 Rojo:** sin correlación. El certificado no mide lo que afirma medir. Esto es
el núcleo del producto: hay que resolverlo o el proyecto no tiene propuesta de
valor distinta. Antes de abandonar, revisar si el fallo está en la segmentación
por regiones y no en `τ`.

> Nota de método: el PSNR frente a bicúbica es la prueba de **rendimiento**. La
> correlación de esta etapa es la prueba de **honestidad**. La segunda es la que
> vendes.

**Tiempo:** 1–2 semanas.

---

### E3 — ¿La ráfaga entrega la ganancia prometida?

**Pregunta:** ¿la alineación sub-píxel alcanza la precisión necesaria para
desplegar el aliasing?

**Construir:** selección de frame de referencia (máxima varianza del Laplaciano),
correlación de fase, refinamiento ECC, fusión por splatting con pesos, rechazo
robusto de outliers.

**Prueba:** ráfagas sintéticas con desplazamientos conocidos primero; ráfagas
reales de móvil después.

**Medir:**

- Error de estimación del desplazamiento (en píxeles)
- **Distribución de fases sub-píxel** — si todos los frames caen en la misma
  fase, no hay información nueva y hay que decirlo
- Ganancia de banda frente a un solo frame

**🟢 Verde:** con K = 8 bien distribuidos, ganancia de banda ≥ 1.6× sobre un solo
frame.

**🔴 Rojo:** error de alineación > 0.2 px. Sin precisión sub-píxel no hay
desdoblamiento posible. Revisar pirámide gaussiana y criterio de convergencia
antes de descartar.

**Tiempo:** 1–2 semanas.

---

### E4 — ¿La recurrencia interna aporta algo medible?

**Pregunta:** ¿las repeticiones de parches son mediciones útiles o ruido?

**Construir:** búsqueda de parches auto-similares con verificación de que la
recurrencia es real y no coincidencia.

**Medir:** ganancia en regiones de alta recurrencia frente a regiones de baja
recurrencia, en la misma imagen.

**🟢 Verde:** ganancia claramente fuera del ruido en zonas repetitivas.

**🔴 Rojo:** ganancia dentro del margen de error. **No bloquea el proyecto** —
se descarta la capa y se sigue. Es la única etapa cuyo rojo es descartable.

**Tiempo:** ~1 semana.

---

### E5 — Pipeline completo y certificado

Integración de lo que sobrevivió, mapa de resolución efectiva, informe de
entrega. Solo después de que E0–E3 estén en verde.

---

## 4 · Especificación del método

Referencia técnica de las fases. Construir solo lo que cada experimento exija.

### Fase A · Diagnóstico

Siete magnitudes extraídas de la propia imagen, antes de tocar nada:

1. **Ancho de banda efectivo** `f_eff` — espectro radial, dónde muere la energía
2. **Tipo de corte** — suave / muro / plegado *(el dato decisivo)*
3. **Ruido** `σ_n` — MAD sobre coeficientes de detalle wavelet en zonas planas
4. **PSF** — por ESF: bordes rectos fuertes → perfil perpendicular sub-píxel →
   derivada → ajuste paramétrico. Fallback `σ = 0.8 px`. Normalizada a suma 1.
5. **Daño de compresión** — retícula 8×8 de JPEG, escalonamiento de cuantización
6. **Clase de contenido por región** — liso / textura / texto / repetitivo
7. **Densidad de recurrencia interna** — fracción con parches auto-similares

### Fase B · Techo honesto

Ganancia libre por restauración, válida **solo si el corte es suave**:

```
s_libre = f_N / f_eff
```

Límite exacto de la deconvolución, donde el ruido ahoga la inversión:

```
f_max :  |H(f)| = σ_n
```

Ganancias que **encogen el núcleo** (no gastan presupuesto):

- Ráfaga: hasta √K en factor lineal, condicionado al reparto de fases
- Recurrencia interna: por región, según repeticiones fiables
- Diversidad de canal: Bayer + aberración lateral. Solo RAW, y solo donde la
  escena sea localmente acromática — la aberración lateral vale **cero en el eje
  óptico**

Techo compuesto:

```
s_max = mín( s_libre · s_mediciones ,  s_difracción )
```

Para imágenes web la difracción casi nunca es el límite activo. **El límite real
lo ponen la compresión y el remuestreo previo.**

### Fase C · Presupuesto de invención

Invertir la pregunta: fijar `τ` y resolver para `s`.

```
s* = máx { s : τ(s) ≤ τ_presupuesto }
```

Niveles de servicio:

| Nivel | τ máximo | Mercado |
|---|---|---|
| Forense | ≤ 0.01 | Peritaje, evidencia, seguros |
| Archivo | ≤ 0.05 | Patrimonio, documentación |
| Comercial | ≤ 0.15 | Catálogo, inmobiliaria, prensa |

El cliente elige confianza; el sistema devuelve tamaño.

### Fase D · Reconstrucción por capas

El orden de la §1, deteniéndose cuando el presupuesto se agota.

**Invariantes de implementación:**

- Todo el cómputo en **luz lineal**. Deconvolucionar sobre gamma sRGB produce
  halos que parecen nitidez y son artefacto.
- Carga de RAW con **todo el embellecimiento de cámara desactivado**: sin
  auto-brillo, sin reducción de ruido, sin nitidez, gamma lineal. Si la cámara ya
  tocó la imagen, el modelo directo deja de ser válido y el test de fidelidad
  pierde sentido.
- Procesamiento **por tiles** de 512 px con solapamiento ≥ 64 px y mezcla por
  ventana de Hann. El solapamiento debe superar el radio de la PSF × iteraciones.
  Objetivo verificable: **< 400 MB de RAM con cualquier tamaño de entrada.**
- Richardson–Lucy: 10–30 iteraciones con parada por estancamiento del residuo.
  Más iteraciones no es más nitidez, es más artefacto.
- Para regularizadores no cuadráticos (TV), el gradiente conjugado no basta:
  primal-dual, ADMM o split Bregman.
- Perona–Malik necesita la regularización de Catté et al.; su forma original está
  mal planteada.

### Fase E · Resolución efectiva variable

Retícula de píxeles uniforme, **resolución efectiva declarada por región**:

- **Verde** — componente de rango dominante; medido
- **Ámbar** — relleno conservador de capa 3; estructura plausible, textura no
  afirmada
- **Rojo** — requeriría invención; no se entrega detalle

La frase que esto permite firmar: *"la matrícula tiene resolución efectiva X; la
pared detrás tiene Y"*. Ningún producto del mercado puede decirlo.

### Fase F · Calibración

La validación no es estética. Es si el certificado predice el error — el
procedimiento de E2, ejecutado de forma continua sobre un corpus creciente.

---

## 5 · Expectativas realistas

| Entrada | Factor honesto esperable |
|---|---|
| JPEG blando, corte gaussiano | 1.3 – 1.8× |
| Lo anterior + ráfaga | 2.0 – 2.5× |
| Regiones con recurrencia fuerte | hasta 3× localmente |
| Redimensionado previo con antialias | ~1.0× — nada que recuperar |

**La mejora percibida será mucho mayor que el factor.** Quitar ruido, deshacer
artefactos de compresión, corregir desenfoque y recuperar color producen una
diferencia visual dramática incluso a 1.5×. El cliente no mide pares de línea por
milímetro.

Eso es lo que se vende. El factor es la letra pequeña honesta, no el titular.

---

## 6 · Estructura del repositorio

```
/
├── METODO.md                  ← este documento
├── FUNDAMENTOS.md             ← base teórica
├── CLAUDE.md
│
├── experimentos/              ← el trabajo real de las primeras semanas
│   ├── E0_margen/
│   │   ├── corpus/            (50 imágenes reales, no versionadas)
│   │   ├── medir.py
│   │   └── RESULTADOS.md      ← la puerta, escrita a mano
│   ├── E1_deconvolucion/
│   ├── E2_calibracion/
│   ├── E3_rafaga/
│   └── E4_recurrencia/
│
├── metodo/                    ← solo lo que sobrevivió a su experimento
│   ├── diagnostico.py         (Fase A)
│   ├── techo.py               (Fase B)
│   ├── presupuesto.py         (Fase C)
│   ├── capas/                 (Fase D)
│   ├── certificado.py         (Fase E)
│   └── calibracion.py         (Fase F)
│
├── tests/
└── cli.py
```

**Regla:** nada entra en `metodo/` hasta que su experimento esté en verde. Los
experimentos pueden ser código sucio; `metodo/` no.

---

## 7 · CLAUDE.md

```markdown
# CLAUDE.md — Método de Recuperación Certificada

## Regla no negociable
Prohibido cualquier prior generativo aprendido (GAN, difusión, redes que
sinteticen píxeles). El núcleo se rellena por capas 0-3 en orden de
verificabilidad. No existe capa 4.

## Esto es un programa experimental
Cada etapa tiene una puerta con criterio verde y criterio rojo, definidos en
METODO.md §3. NO avanzar de etapa con la puerta en rojo. Si un resultado es
ambiguo, decirlo en vez de interpretarlo a favor.

Código de experimentos/ puede ser sucio y directo. Código de metodo/ no: ahí
solo entra lo que ya pasó su puerta.

## Invariantes técnicos
- Todo el cómputo en LUZ LINEAL (deshacer gamma al cargar, reaplicar al guardar)
- RAW sin auto-brillo, sin reducción de ruido, sin nitidez, gamma lineal
- Procesamiento por tiles: < 400 MB de RAM con cualquier tamaño de entrada
- float32 para cómputo, 16 bits para guardar
- Sin GPU (MacBook Pro 2015 Intel). Sin Docker para el pipeline.
- Código y comentarios en español

## Las dos métricas acompañan toda salida
consistencia: ‖DHx̂ − y‖ ≈ ‖n‖
tau:          ‖x_núcleo‖ / ‖x_rango‖
La consistencia sola NO basta: un generativo proyectado la aprueba.

## Debug
Reproducir → Aislar → Hipótesis → Verificar → Fix mínimo.
```

---

## 8 · Qué significa "no funcionó"

Cada puerta en rojo tiene una salida distinta. Ninguna es abandonar el trabajo
hecho.

| Puerta | Si sale rojo | Adónde va el proyecto |
|---|---|---|
| **E0** | Las imágenes reales no tienen banda recuperable | Producto = limpieza y restauración, no resolución. El certificado sigue teniendo valor |
| **E1** | La deconvolución no supera bicúbica | Aislar PSF vs. algoritmo. Si es la PSF, es un problema acotado y resoluble |
| **E2** | El certificado no predice el error | **La más grave.** Revisar segmentación antes que τ. Si τ realmente no correlaciona, el producto pierde su diferenciador y hay que replantear |
| **E3** | La alineación no alcanza precisión sub-píxel | Sin ráfaga, techo ≈ `s_libre`. El servicio existe, más modesto |
| **E4** | La recurrencia no aporta | Se descarta la capa. No afecta a nada más |

**El único resultado que invalida la propuesta de valor es E2 en rojo.** Todos
los demás reducen el alcance sin tumbar el producto.

Por eso E2 debe ejecutarse **antes** de invertir en ráfaga, recurrencia,
infraestructura o front. Es la pregunta cara disfrazada de barata.

---

## 9 · Orden de trabajo

```
E0  (1-2 días)   → ¿hay margen?           → puerta
E1  (1 semana)   → ¿deconvolución sirve?  → puerta
E2  (1-2 sem.)   → ¿el certificado mide?  → PUERTA CRÍTICA
E3  (1-2 sem.)   → ¿la ráfaga aporta?     → puerta
E4  (1 semana)   → ¿la recurrencia aporta? → puerta (descartable)
E5               → integración y certificado
```

Después de E2 en verde ya hay algo vendible manualmente: diagnóstico +
restauración + certificado, atendido a mano desde el Mac. La infraestructura
viene cuando el procesamiento manual quite horas, no antes.
