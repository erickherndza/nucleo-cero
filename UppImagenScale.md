# UppImagenScale — Plan maestro de construcción

> Documento de especificación para Claude Code.
> Objetivo: construir un servicio de **mejora de resolución real** de fotografías,
> sin generación ni alucinación de detalle.

---

## 0. Contexto y regla de oro

Este proyecto NO es un upscaler. No usa redes generativas, no inventa píxeles,
no "imagina" detalle plausible. Todo lo que aparece en la salida debe ser
**derivable de los datos de entrada**.

### El modelo directo

Toda foto capturada responde a:

```
y = D · H · x + n
```

- `x` = escena real (alta resolución, lo que queremos estimar)
- `H` = convolución con la PSF (óptica + difracción + movimiento) → filtro paso-bajo
- `D` = decimación del sensor (muestreo)
- `n` = ruido
- `y` = la imagen que tenemos

### Regla de oro (criterio de aceptación de TODO el proyecto)

Toda estimación `x̂` debe cumplir **consistencia de reproyección**:

```
‖ D · H · x̂  −  y ‖  ≈  ‖n‖
```

Es decir: si degradamos nuestro resultado con el mismo modelo físico,
debemos recuperar la entrada original. Un upscaler generativo **falla este test**.
El nuestro no puede fallarlo.

Esta comprobación no es opcional ni un extra: es el producto.
Es lo único que un competidor de IA generativa no puede ofrecer.

### De dónde sale la información real

| Fuente | Ganancia | Por qué es legítima |
|---|---|---|
| Archivo RAW en vez de JPEG | Alta | El demosaico y el JPEG descartan datos que el RAW conserva |
| Burst / ráfaga con desplazamiento sub-píxel | Alta | Cada frame muestrea una fase distinta; el aliasing se desdobla algebraicamente (muestreo generalizado de Papoulis). Más frames = más ecuaciones |
| Deconvolución con PSF conocida | Media | Deshace una operación conocida, acotada por el SNR |
| Apilado de N frames | Media | El ruido cae como √N |

### Límites que NO se deben cruzar

- Factor máximo por defecto: **2.0×**. Nunca ofrecer más de 3× ni con burst.
  (Referencia: los métodos de reconstrucción se agotan cerca de 1.6× bajo
  traslación local; más allá, cualquier "mejora" viene del prior, no de los datos.)
- Si la entrada es un solo JPEG recomprimido, el techo real es ~1.5×.
  El sistema debe **decirlo**, no fingir que puede más.

---

## 1. Arquitectura

Restricción de infraestructura: **solo Banahosting (hosting compartido) + MacBook local.**
Sin Render, sin DigitalOcean, sin VPS.

```
Cliente
   │ sube fotos
   ▼
┌─────────────────────────────┐
│  BANAHOSTING (compartido)   │   Python 3.8.20 bajo Passenger
│  - Formulario + portal      │   Flask + MySQL
│  - Tabla `trabajos` = cola  │   SOLO tareas livianas
│  - Endpoints con token      │   NUNCA procesamiento
│  - Correos de notificación  │
└─────────────────────────────┘
   ▲                        │
   │ sube resultado         │ el Mac pregunta cada N minutos
   │                        ▼
┌─────────────────────────────┐
│  MacBook Pro 2015 (worker)  │   Python 3.11+
│  - Pipeline completo        │   numpy, scipy, opencv, rawpy
│  - Procesa por tiles        │   CPU, sin GPU
└─────────────────────────────┘
```

**Por qué el Mac consulta y no al revés:** el Mac está detrás de un router,
sin IP pública. Siempre inicia él la conexión saliente. Cero puertos abiertos,
cero túneles, cero IP fija.

**Por qué el procesamiento no puede ir en Banahosting:** los límites LVE de
CloudLinux (PMEM ~1 GB, ~1 core, timeout de request 60-120 s) y el hecho de que
Passenger vive por request, no como demonio. Además, Python 3.8 congela el stack
numérico en numpy 1.24.4 / scipy 1.10.1 (2023).

---

## 2. Estructura del repositorio

```
UppImagenScale/
├── README.md
├── UppImagenScale.md          ← este documento
├── CLAUDE.md                  ← instrucciones permanentes (crear en Fase 0)
├── .gitignore
│
├── worker/                    ← corre en el Mac, Python 3.11+
│   ├── requirements.txt
│   ├── config.example.yaml
│   ├── run.py                 ← loop de polling contra el front
│   ├── cli.py                 ← uso manual sin servidor
│   ├── client.py              ← cliente HTTP
│   └── uppimagen/
│       ├── __init__.py
│       ├── io_img.py          ← carga RAW/JPEG → lineal float32
│       ├── psf.py             ← estimación de PSF
│       ├── align.py           ← alineación sub-píxel
│       ├── merge.py           ← fusión de burst
│       ├── deconv.py          ← deconvolución regularizada
│       ├── tiling.py          ← procesamiento por bloques
│       ├── pipeline.py        ← orquestador
│       ├── fidelity.py        ← test de consistencia (LA REGLA DE ORO)
│       └── report.py          ← informe de fidelidad para el cliente
│
├── tests/
│   ├── test_fidelity.py
│   ├── test_align.py
│   └── fixtures/
│
└── front/                     ← sube a Banahosting, Python 3.8.20
    ├── passenger_wsgi.py
    ├── requirements.txt
    ├── schema.sql
    ├── .env.example
    └── app/
        ├── __init__.py
        ├── models.py
        ├── routes_public.py
        ├── routes_worker.py
        ├── auth.py
        ├── mailer.py
        ├── static/
        └── templates/
```

---

## 3. Fases de construcción

Construir **en orden**. Cada fase debe quedar funcionando y commiteada antes
de pasar a la siguiente.

> **Nota de negocio importante:** al terminar la Fase 2 el servicio ya es
> vendible de forma manual (el cliente envía archivos, se procesan en el Mac,
> se entregan). Las fases 3-5 solo automatizan la entrega. No construir
> infraestructura antes de tener clientes reales.

| Fase | Entregable | Valor |
|---|---|---|
| 0 | Scaffolding, CLAUDE.md, .gitignore, venv | — |
| 1 | Pipeline completo como CLI local | **El producto** |
| 2 | Test de fidelidad + informe | **El diferenciador** |
| 3 | Front Flask + MySQL en Banahosting | Automatiza entrada |
| 4 | Worker de polling | Automatiza proceso |
| 5 | Despliegue y endurecimiento | Producción |

---

## 4. FASE 0 — Scaffolding

Crear la estructura de carpetas, el `.gitignore`, y `CLAUDE.md` con este contenido:

```markdown
# CLAUDE.md — UppImagenScale

## Regla no negociable
Este proyecto NO genera ni alucina detalle. Prohibido introducir modelos
generativos, GANs, difusión, o cualquier red que sintetice píxeles.
Toda mejora debe pasar el test de consistencia de reproyección de
`worker/uppimagen/fidelity.py`.

## Dos entornos, dos versiones de Python
- `worker/` → Python 3.11+, corre en el Mac. numpy/scipy/opencv/rawpy modernos.
- `front/`  → Python 3.8.20, corre en Banahosting bajo Passenger.
  SOLO dependencias Python puro (no compilar nada).
  NUNCA importar numpy, scipy, opencv ni rawpy aquí.

## Restricciones de máquina (MacBook Pro 2015, 8 GB, Intel)
- Procesar SIEMPRE por tiles. El consumo debe ser constante
  independientemente del tamaño de la imagen.
- Sin GPU. Sin Metal/MPS. Todo CPU.
- No usar Docker para el pipeline (la VM de Docker Desktop consume 2-4 GB).

## Convenciones
- Todo el procesamiento numérico en float32 y en LUZ LINEAL
  (deshacer gamma al cargar, reaplicar al guardar).
- Código y comentarios en español.
- Cada módulo con su test antes de darlo por terminado.

## Debug
Seguir: Reproducir → Aislar → Hipótesis → Verificar → Fix mínimo.
```

Y el `.gitignore`:

```
__pycache__/
*.pyc
.venv/
venv/
.env
config.yaml
worker/salidas/
worker/entradas/
*.dng
*.cr2
*.nef
*.arw
.DS_Store
```

---

## 5. FASE 1 — Pipeline de procesamiento (el núcleo)

### 5.1 `io_img.py` — carga y linealización

**Crítico:** toda la matemática ocurre en **luz lineal**. Cargar un JPEG y
deconvolucionar sobre valores con gamma sRGB produce halos y resultados falsos.

```python
def cargar(ruta) -> tuple[np.ndarray, dict]:
    """Devuelve (imagen float32 en [0,1] LINEAL, metadatos)."""
```

- **RAW** (`.dng .cr2 .nef .arw`): usar `rawpy` con parámetros que **desactiven**
  todo el "embellecimiento" del pipeline de cámara:
  ```python
  raw.postprocess(
      output_bps=16,
      no_auto_bright=True,
      gamma=(1, 1),              # lineal, sin gamma
      use_camera_wb=True,
      demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
      fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
      output_color=rawpy.ColorSpace.raw,
  )
  ```
  Cualquier nitidez o reducción de ruido aplicada por la cámara contamina el
  modelo directo y rompe el test de fidelidad.

- **JPEG/PNG/TIFF**: cargar y **deshacer la gamma sRGB** explícitamente
  (la inversa exacta de sRGB, no `x**2.2` aproximado).

- Registrar en metadatos: si viene de RAW o JPEG, si hay EXIF de apertura/ISO,
  y una estimación del nivel de ruido `sigma_n` (desviación robusta en zonas planas,
  por MAD sobre el detalle de una wavelet o un Laplaciano).

Guardar con `guardar()` reaplicando gamma y a 16 bits (TIFF/PNG) por defecto.

### 5.2 `psf.py` — estimación de la PSF

No se puede deconvolucionar lo que no se modela.

- **v1 (paramétrica):** PSF gaussiana isotrópica `G(sigma)`. Estimar `sigma`
  midiendo la **Edge Spread Function**: detectar bordes fuertes y rectos
  (Canny + Hough), muestrear el perfil perpendicular con precisión sub-píxel,
  derivar → Line Spread Function, ajustar gaussiana.
- Fallback: si no hay bordes utilizables, `sigma = 0.8 px` (difracción típica).
- **v2 (opcional):** añadir disco de desenfoque para defocus.
- La PSF debe estar **normalizada a suma 1** siempre.

```python
def estimar_psf(img, metodo="esf") -> np.ndarray  # kernel 2D normalizado
```

### 5.3 `align.py` — alineación sub-píxel

Aquí es donde se recupera información real. La precisión sub-píxel es todo.

1. **Elegir referencia:** el frame más nítido = máxima varianza del Laplaciano.
2. **Grueso:** `cv2.phaseCorrelate` → traslación global con precisión sub-píxel.
3. **Fino:** `cv2.findTransformECC` con `MOTION_EUCLIDEAN`
   (o `MOTION_HOMOGRAPHY` si hay perspectiva), criterio `1e-6`, sobre la
   luminancia y con pirámide gaussiana para robustez.
4. **Rechazo de frames:** descartar los que tengan
   - desplazamiento > 3% de la dimensión (ya no es temblor de mano),
   - nitidez < 60% de la del frame de referencia,
   - correlación ECC por debajo de umbral.
5. **Verificación clave:** los desplazamientos deben tener **partes fraccionarias
   bien distribuidas**. Si todos los frames caen en la misma fase sub-píxel,
   NO hay información nueva que desdoblar → avisar y no prometer ganancia.
   Registrar la distribución de fases en el informe.

```python
def alinear(frames) -> tuple[list[np.ndarray], list[dict]]  # (alineados, transformadas)
```

### 5.4 `merge.py` — fusión del burst

Algoritmo (splatting con pesos, estilo kernel regression):

```
1. Crear lienzo alta resolución HR de tamaño (H*s, W*s), acumuladores
   `num` (numerador) y `den` (denominador) a cero.
2. Para cada frame k con su transformada T_k:
     Para cada píxel p del frame:
       posición HR = T_k(p) * s
       repartir su valor sobre los vecinos HR con un kernel gaussiano
       de radio ~1 px HR, ponderando por:
         w = w_gauss * w_robustez * w_nitidez_frame
3. HR = num / max(den, eps)
4. Donde den sea muy bajo (huecos), marcar como "sin cobertura"
   y rellenar por interpolación — y REGISTRARLO en el informe.
```

**Robustez (objetos en movimiento):** tras alinear, calcular mediana y MAD por
píxel entre frames. Contribuciones que se desvíen > 3·MAD reciben `w_robustez`
decreciente. Esto evita fantasmas sin inventar nada.

**Caso de un solo frame:** no hay fusión. Se salta a deconvolución directamente
y el factor máximo se limita a 1.5×.

### 5.5 `deconv.py` — deconvolución regularizada

- **Richardson-Lucy con regularización TV** como método principal.
- Iteraciones: 10-30. **Más iteraciones amplifican el ruido** — no es "más nítido",
  es más artefacto. Parada automática cuando el residuo deje de bajar
  significativamente.
- Peso de regularización ligado al ruido estimado: `lambda ≈ k · sigma_n`.
- **Wiener** como opción rápida, con `NSR = sigma_n² / potencia_señal`.
- Operar en luz lineal, canal por canal (o sobre luminancia + crominancia
  suavizada, que es más estable).

```python
def richardson_lucy_tv(img, psf, iters=20, lam=0.002) -> np.ndarray
```

Tras cada iteración, verificar que no aparezcan valores negativos ni
ringing excesivo (comprobar overshoot en bordes).

### 5.6 `tiling.py` — memoria constante

Sin esto, un RAW de 24 MP en float32 son ~290 MB por frame y un burst de 8
no cabe en 8 GB de RAM.

- Tiles de **512×512** con solapamiento de **64 px**.
- Mezcla con ventana de Hann 2D para que no se vean costuras.
- El solapamiento debe ser mayor que el radio de la PSF × iteraciones,
  o aparecerán artefactos de borde.
- Procesar los frames del burst **tile a tile**, no imagen completa a imagen completa.
- Objetivo medible: **consumo < 400 MB** con cualquier tamaño de entrada.
  Añadir un test que lo verifique con `tracemalloc`.

### 5.7 `pipeline.py` — orquestador

```python
def procesar(rutas, factor=2.0, salida=None, perfil="equilibrado") -> Resultado
```

Flujo: cargar → estimar PSF → alinear → (fusionar) → deconvolucionar →
verificar fidelidad → guardar + informe.

`Resultado` debe incluir: ruta de salida, métricas de fidelidad, factor
realmente alcanzado, avisos, y tiempo de proceso.

### 5.8 `cli.py`

```bash
python -m worker.cli procesar ./entradas/burst_01/ --factor 2 --salida ./salidas/
python -m worker.cli verificar ./salidas/resultado.tif --original ./entradas/burst_01/
```

Debe funcionar **sin ningún servidor**. Es la herramienta con la que se atienden
los primeros clientes manualmente.

---

## 6. FASE 2 — Test de fidelidad (el diferenciador)

`fidelity.py` implementa la regla de oro. Es el módulo más importante del repo.

### 6.1 Consistencia de reproyección (la prueba real)

```python
def consistencia_reproyeccion(x_est, y_orig, psf, factor) -> dict:
    """
    Degrada la estimación con el mismo modelo físico y la compara
    con la entrada original.
        y_rep = D(H(x_est))
        residuo = ||y_rep - y_orig||
    Si residuo ≈ nivel de ruido → la salida es consistente con los datos.
    Si residuo >> ruido → se inventó información. FALLO.
    """
```

Devolver: RMSE del residuo, `sigma_n` estimado, ratio `residuo/sigma_n`,
y **veredicto booleano** (`consistente` si ratio < 1.5).

**Este test debe ejecutarse siempre y su resultado debe acompañar cada entrega.**

### 6.2 Prueba de degradación controlada

```python
def prueba_degradacion(img_alta_res, factor) -> dict:
```

Tomar una imagen de alta resolución conocida → degradarla con el modelo
(`H` y luego `D`) → reconstruirla con el pipeline → comparar contra el original.
Métricas: PSNR, SSIM, y mapa de diferencias amplificado.

Esto da los números para la propuesta comercial: "recuperamos X dB sobre
interpolación bicúbica, con consistencia verificada".

### 6.3 Comparación contra la línea base

Siempre reportar frente a **interpolación bicúbica** al mismo factor.
Si el pipeline no supera claramente a bicúbica, no hay servicio que vender
en ese caso concreto, y el sistema debe decirlo.

### 6.4 `report.py` — informe para el cliente

Generar un HTML autocontenido por trabajo con:

- Comparación antes/después (deslizador)
- Mapa de diferencias
- Tabla de métricas: consistencia, PSNR vs bicúbica, SSIM
- **Sello de fidelidad**: "Verificado — sin generación de detalle",
  con el ratio residuo/ruido como evidencia numérica
- Factor efectivo alcanzado y avisos (frames descartados, zonas sin cobertura)

Este informe es parte del entregable. Es lo que justifica el precio.

---

## 7. FASE 3 — Front en Banahosting

### Restricciones obligatorias

- Python **3.8.20** bajo **Passenger**.
- **Solo dependencias Python puro.** No hay compilador en el shared.
- Jamás importar numpy/scipy/opencv/rawpy aquí.

### `front/requirements.txt`

```
Flask==3.0.3
SQLAlchemy==2.0.36
PyMySQL==1.1.1
requests==2.31.0
python-dotenv==1.0.1
```

`PyMySQL`, no `mysqlclient` — este último requiere compilar y fallará.

### `passenger_wsgi.py`

```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import crear_app
application = crear_app()
```

Passenger busca literalmente el objeto `application`. Configurar en cPanel:
- **Application startup file:** `passenger_wsgi.py`
- **Application Entry point:** `application`

Recarga tras cambios: botón *Restart* del Python Selector o `touch tmp/restart.txt`.

### `schema.sql`

```sql
CREATE TABLE trabajos (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  token_publico   CHAR(32) NOT NULL UNIQUE,
  cliente_email   VARCHAR(255) NOT NULL,
  estado          ENUM('pendiente','reclamado','procesando','listo','error')
                  NOT NULL DEFAULT 'pendiente',
  factor          DECIMAL(3,1) NOT NULL DEFAULT 2.0,
  params_json     TEXT,
  worker_id       VARCHAR(64),
  intentos        TINYINT NOT NULL DEFAULT 0,
  error_msg       TEXT,
  metricas_json   TEXT,
  creado_en       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  iniciado_en     DATETIME,
  terminado_en    DATETIME,
  purgar_en       DATETIME,
  INDEX idx_estado (estado, creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE archivos (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  trabajo_id  INT NOT NULL,
  tipo        ENUM('origen','resultado','informe') NOT NULL,
  nombre      VARCHAR(255) NOT NULL,
  ruta        VARCHAR(512) NOT NULL,
  bytes       BIGINT NOT NULL,
  sha256      CHAR(64),
  creado_en   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE,
  INDEX idx_trabajo (trabajo_id, tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Rutas públicas (`routes_public.py`)

| Ruta | Método | Función |
|---|---|---|
| `/` | GET | Landing + formulario |
| `/subir` | POST | Crea trabajo, guarda archivos, devuelve token |
| `/estado/<token>` | GET | Estado del trabajo para el cliente |
| `/descargar/<token>/<archivo_id>` | GET | Entrega del resultado |

### Rutas del worker (`routes_worker.py`)

Todas protegidas con `Authorization: Bearer <WORKER_TOKEN>`, comparado con
`hmac.compare_digest` (nunca `==`).

| Ruta | Método | Función |
|---|---|---|
| `/api/trabajos/siguiente` | POST | Reclama **atómicamente** un trabajo pendiente |
| `/api/archivos/<id>/descargar` | GET | Descarga un original |
| `/api/trabajos/<id>/estado` | POST | Actualiza progreso |
| `/api/trabajos/<id>/resultado` | POST | Sube resultado + informe + métricas |

**Reclamo atómico** (evita que dos workers tomen el mismo trabajo):

```sql
UPDATE trabajos
   SET estado='reclamado', worker_id=:wid, iniciado_en=NOW(), intentos=intentos+1
 WHERE estado='pendiente'
 ORDER BY creado_en ASC
 LIMIT 1;
-- luego SELECT del que quedó con ese worker_id y estado='reclamado'
```

También: un trabajo en `reclamado`/`procesando` por más de 2 horas vuelve a
`pendiente` (el Mac pudo apagarse).

### El problema de los archivos grandes

Un RAW pesa 25-50 MB; un burst de 8 son ~400 MB. `upload_max_filesize` en shared
suele estar en 64-256 MB.

- **v1:** el cliente sube a su Drive/WeTransfer y pega el enlace en el formulario.
  Cero desarrollo, funciona desde el primer día.
- **v2:** subida por trozos con Uppy o Resumable.js, ensamblando en el servidor.
- **Obligatorio en ambos casos:** campo `purgar_en` y un cron diario que borre
  originales 7 días después de entregado. Sin esto el disco se llena en semanas.

---

## 8. FASE 4 — Worker de polling

`worker/run.py`:

```
bucle:
    POST /api/trabajos/siguiente
    si no hay trabajo → dormir INTERVALO (por defecto 300 s) y repetir
    descargar originales a carpeta temporal
    POST estado = 'procesando'
    ejecutar pipeline.procesar(...)
    ejecutar fidelity → si NO es consistente: marcar error, no entregar
    POST resultado + informe + métricas
    limpiar temporales
```

Requisitos:

- Reintentos con backoff exponencial ante fallos de red.
- `caffeinate -i` mientras haya trabajo activo, para que el Mac no duerma.
- Verificar `sha256` de cada descarga y subida.
- Registro en `worker/logs/` con rotación.
- Si el pipeline falla, reportar el error al front con mensaje útil, nunca dejar
  el trabajo colgado.
- **Nunca entregar un resultado que no pase el test de consistencia.**

`worker/config.example.yaml`:

```yaml
front_url: "https://erickhernandezarias.net/uppimagen"
worker_token: "CAMBIAR"
worker_id: "mac-2015"
intervalo_segundos: 300
factor_por_defecto: 2.0
directorio_temporal: "./tmp"
max_frames_burst: 12
```

---

## 9. FASE 5 — Despliegue y endurecimiento

1. Subir `front/` a Banahosting, crear la app en el Python Selector
   (3.8.20, startup file y entry point como en §7).
2. `pip install -r requirements.txt` dentro del venv que crea cPanel.
3. Importar `schema.sql` en MySQL vía phpMyAdmin.
4. Variables en `.env` (nunca en el repo): credenciales MySQL, `WORKER_TOKEN`,
   configuración SMTP.
5. Verificar en cPanel → **Resource Usage** que el front no se acerca a los
   límites LVE con tráfico normal.
6. Cron diario de purga de archivos vencidos.
7. HTTPS obligatorio en todos los endpoints del worker.
8. Rate limiting básico en `/subir` para evitar abuso.

---

## 10. Definición de "terminado"

El proyecto está listo cuando:

- [ ] `python -m worker.cli procesar ./entradas/burst_01/ --factor 2` produce
      un resultado y un informe HTML.
- [ ] El test de consistencia de reproyección se ejecuta y **pasa** sobre
      imágenes reales.
- [ ] El resultado supera medible y visiblemente a bicúbica al mismo factor.
- [ ] El consumo de RAM se mantiene por debajo de 400 MB con un RAW de 24 MP
      y burst de 8 (verificado con `tracemalloc` en un test).
- [ ] El front despliega en Banahosting sin error 500 y sin compilar nada.
- [ ] El worker completa un trabajo de punta a punta: subida → proceso → entrega.
- [ ] Existe al menos un caso documentado con números reales para la propuesta
      comercial.

---

## 11. Orden de trabajo sugerido con Claude Code

```
Fase 0  → scaffolding + CLAUDE.md + venv
Fase 1  → io_img → psf → align → merge → deconv → tiling → pipeline → cli
Fase 2  → fidelity → report        ← aquí ya se puede vender manualmente
Fase 3  → front Flask + schema
Fase 4  → worker de polling
Fase 5  → despliegue
```

Commit al terminar cada módulo, no al terminar cada fase.
Cada módulo con su test antes de pasar al siguiente.
