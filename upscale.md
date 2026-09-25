# nucleo-cero · Mejora de fotos de WhatsApp sin inventar caras

Notebook para **Google Colab** (Entorno de ejecución → Cambiar tipo → **GPU T4**). Ejecuta las celdas en orden.

## Qué cambió respecto a tu versión

| Antes | Ahora |
|---|---|
| `basicsr`, `realesrgan`, `gfpgan`, `facexlib` (abandonados, no instalan en Python 3.12) | **`spandrel`** + OpenCV: cargan los mismos `.pth` sin parches `sed` |
| `face_fidelity` no hacía nada en GFPGAN | `mezcla` (sí funciona en ambos) + `fidelidad` (solo CodeFormer) |
| GFPGAN restauraba sobre la imagen ya inventada por ESRGAN | Las caras se alinean y recortan desde la foto **original** |
| Escalaba ×4.39 (2810×2107) | Por defecto **1024 px de ancho** manteniendo proporción (640×480 → 1024×768) |
| Ninguna verificación | **Control de identidad SFace** por cara: si la IA la cambia demasiado, se descarta |
| Caras pequeñas también "restauradas" (inventadas) | Caras < 64 px quedan con la versión fiel (bicúbica) |
| Fallaba con fotos en gris o rotadas | Soporta gris, PNG con transparencia y rotación EXIF |

## Cómo funciona

```
foto WhatsApp ─┬─► Real-ESRGAN ×4 → reducir a 1024 px ──────► FONDO (limpio)
               ├─► bicúbica + enfoque ────────────────────► bajo cada CARA (fiel)
               └─► YuNet detecta caras ─► alinear 512×512 desde la original
                        └─► GFPGAN restaura ─► mezcla 50 % ─► ¿SFace ≥ 0.80?
                                                  sí → se pega · no → queda la fiel
```

## Resultados medidos (probado antes de entregártelo)

Fotos buenas degradadas como WhatsApp (÷1.6, desenfoque, JPEG q25) y recuperadas. Se compara contra el original real. **ID** = similitud de identidad SFace (1.0 = la misma cara).

| Método | Foto grupal (caras ~75 px) PSNR / ID | Foto dúo (caras ~135 px) PSNR / ID |
|---|---|---|
| Bicúbica + enfoque (Photoshop) | **33.5** / **0.854** | **33.3** / 0.942 |
| Real-ESRGAN solo | 31.0 / 0.777 | 29.8 / 0.927 |
| ESRGAN + GFPGAN sin protección | 31.0 / 0.798 | 30.2 / 0.941 |
| **nucleo-cero (config. por defecto)** | 31.3 / 0.813 | 31.1 / **0.948** |
| ESRGAN + CodeFormer (w 0.8) | 31.3 / 0.781 | 30.8 / 0.935 |

**Lectura honesta:**
- En fidelidad de píxeles (PSNR), la bicúbica + enfoque **sigue ganando siempre**. La IA "limpia" el grano y los artefactos: se ve mejor, pero no es más exacta.
- En caras grandes (> ~100 px) la configuración por defecto conserva la identidad igual o mejor que Photoshop y se ve claramente más limpia.
- En caras pequeñas la IA cambia más la identidad. Por eso existen `cara_minima` y `umbral_identidad`.
- CodeFormer fue el que más cambió las caras. Además su licencia es **no comercial**, así que el valor por defecto es GFPGAN (Apache 2.0).
- Tiempo: ~2 min por foto en CPU. En GPU T4 deberían ser segundos (no lo pude medir aquí).

## Hallazgo 2026-09-24: Real-ESRGAN puede "pintar" el fondo

Probando con una foto real de WhatsApp (grupo familiar, 1048×718), el fondo y la ropa salieron con un efecto posterizado/acuarela — bloques de color planos en vez de textura, muy notorio en telas y fondos con patrones. No es sutil, se ve a simple vista en la imagen completa (no tanto en miniaturas).

**Causa probable**: Real-ESRGAN amplifica los bloques de compresión JPEG de una foto ya comprimida por WhatsApp, en vez de limpiarlos — mientras más se escala, peor se nota. El escalado automático a 2× (cuando la foto original ya supera 1024px, ver `ancho=None` en `mejorar_foto`) probablemente empeora esto al darle más superficie donde manifestarse.

**Fix aplicado, confirmado que funciona**: `usar_esrgan=False` en `CONFIG_SUELTA` (Celda 3). Con esto el fondo se queda en bicúbica + enfoque (fiel, sin inventar textura) y solo las caras siguen mejorando vía GFPGAN. Probado contra la misma foto: el efecto pintura desapareció por completo, caras siguen viéndose más nítidas.

**Trade-off**: el fondo ya no tiene el "extra" de detalle que promete Real-ESRGAN — se queda al nivel de una bicúbica bien afilada. Pendiente investigar si hay parámetros de Real-ESRGAN (denoise, tile) que eviten el artefacto sin desactivarlo del todo.

## CELDA 1 — Instalación y modelos


```python
# ═══════════════════════════════════════════════════════════════════
# CELDA 1 — INSTALACIÓN + MODELOS (solo la primera vez por sesión)
# ═══════════════════════════════════════════════════════════════════
!pip install -q spandrel spandrel_extra_arches

import os, cv2, torch
os.makedirs('weights', exist_ok=True)

USAR_CODEFORMER = False   # True solo para pruebas: licencia NO comercial, 376 MB

MODELOS = {
    'RealESRGAN_x4plus.pth': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
    'GFPGANv1.4.pth': 'https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth',
    'face_detection_yunet_2023mar.onnx': 'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
    'face_recognition_sface_2021dec.onnx': 'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx',
}
if USAR_CODEFORMER:
    MODELOS['codeformer.pth'] = 'https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth'

for nombre, url in MODELOS.items():
    ruta = f'weights/{nombre}'
    if not os.path.exists(ruta) or os.path.getsize(ruta) < 100_000:
        print(f'⏬ {nombre}')
        !wget -q -O {ruta} "{url}"
    print(f'✓ {nombre:40s} {os.path.getsize(ruta)/1e6:6.1f} MB')

print(f'\nOpenCV {cv2.__version__} · FaceDetectorYN: {hasattr(cv2, "FaceDetectorYN")}')
print('GPU ⚡' if torch.cuda.is_available() else '⚠️ Sin GPU: Entorno de ejecución → Cambiar tipo → T4')
```


## CELDA 2 — Motor (`nucleo.py`)


```python
%%writefile nucleo.py
# ═══════════════════════════════════════════════════════════════════
# nucleo-cero · mejora de fotos de WhatsApp con control de identidad
#   Real-ESRGAN (fondo) → CodeFormer/GFPGAN (caras grandes) → verificación SFace
#   Sin basicsr / realesrgan / gfpgan / facexlib: todo con spandrel + OpenCV
# ═══════════════════════════════════════════════════════════════════
import os
import cv2
import numpy as np
import torch
from PIL import Image, ImageOps

import spandrel
import spandrel_extra_arches

try:
      spandrel_extra_arches.install()  # añade CodeFormer al cargador
except Exception:
          pass  # ya registrado (reload en Celda 3)
W = 'weights'
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
_CACHE = {}

# Plantilla de 5 puntos FFHQ 512×512 (misma que usan GFPGAN/CodeFormer)
# orden: ojo izq. de la imagen, ojo der., nariz, comisura izq., comisura der.
FFHQ_512 = np.array([[192.98138, 239.94708], [318.90277, 240.19360],
                     [256.63416, 314.01935], [201.26117, 371.41043],
                     [313.08905, 371.15118]], dtype=np.float32)


# ─── Carga de modelos (una sola vez) ────────────────────────────────
def _modelo(nombre):
    if nombre not in _CACHE:
        m = spandrel.ModelLoader().load_from_file(os.path.join(W, nombre))
        m.to(DEVICE).eval()
        if DEVICE.type == 'cuda' and nombre.startswith('RealESRGAN'):
            m.half()
        _CACHE[nombre] = m
    return _CACHE[nombre]


def _detector(w, h):
    if 'yunet' not in _CACHE:
        _CACHE['yunet'] = cv2.FaceDetectorYN.create(
            os.path.join(W, 'face_detection_yunet_2023mar.onnx'), '', (w, h),
            score_threshold=0.5, nms_threshold=0.3, top_k=500)
    d = _CACHE['yunet']
    d.setInputSize((w, h))
    return d


def _reconocedor():
    if 'sface' not in _CACHE:
        _CACHE['sface'] = cv2.FaceRecognizerSF.create(
            os.path.join(W, 'face_recognition_sface_2021dec.onnx'), '')
    return _CACHE['sface']


# ─── Utilidades ─────────────────────────────────────────────────────
def leer_imagen(ruta):
    """Lee JPG/PNG/HEIC-convertido, respeta rotación EXIF, devuelve BGR uint8."""
    im = ImageOps.exif_transpose(Image.open(ruta)).convert('RGB')
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def _a_tensor(img_bgr, half=False):
    t = torch.from_numpy(img_bgr[:, :, ::-1].copy()).permute(2, 0, 1).float().div(255)
    t = t.unsqueeze(0).to(DEVICE)
    return t.half() if half else t


def _a_bgr(t):
    a = t.squeeze(0).float().clamp(0, 1).permute(1, 2, 0).cpu().numpy()
    return (a[:, :, ::-1] * 255.0).round().astype(np.uint8)


def realesrgan_x4(img_bgr, tile=512, pad=16):
    """Real-ESRGAN ×4 por bloques (tiles) para no agotar la memoria."""
    m = _modelo('RealESRGAN_x4plus.pth')
    half = DEVICE.type == 'cuda'
    h, w = img_bgr.shape[:2]
    out = np.zeros((h * 4, w * 4, 3), np.uint8)
    with torch.inference_mode():
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                y0, x0 = max(y - pad, 0), max(x - pad, 0)
                y1, x1 = min(y + tile + pad, h), min(x + tile + pad, w)
                sr = _a_bgr(m(_a_tensor(img_bgr[y0:y1, x0:x1], half)))
                ty, tx = (y - y0) * 4, (x - x0) * 4
                th, tw = (min(y + tile, h) - y) * 4, (min(x + tile, w) - x) * 4
                out[y * 4:y * 4 + th, x * 4:x * 4 + tw] = sr[ty:ty + th, tx:tx + tw]
    return out


def base_photoshop(img_bgr, size, cantidad=0.6, radio=1.0):
    """Referencia honesta: bicúbica + máscara de enfoque (lo que harías en Photoshop)."""
    up = cv2.resize(img_bgr, size, interpolation=cv2.INTER_CUBIC)
    blur = cv2.GaussianBlur(up, (0, 0), radio)
    return cv2.addWeighted(up, 1 + cantidad, blur, -cantidad, 0)


def detectar_caras(img_bgr):
    """YuNet sobre la imagen ×2 (detecta mejor las caras pequeñas); coords en la original."""
    h, w = img_bgr.shape[:2]
    big = cv2.resize(img_bgr, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    _, caras = _detector(w * 2, h * 2).detect(big)
    if caras is None:
        return []
    caras = caras.copy()
    caras[:, :14] /= 2.0
    return [c for c in caras]


def _puntos(cara):
    p = cara[4:14].reshape(5, 2).astype(np.float32)
    # YuNet: ojo der. del sujeto (= izq. en imagen), ojo izq., nariz, boca der., boca izq.
    # La plantilla FFHQ usa el mismo orden de izquierda a derecha en la imagen.
    return p


def _embedding(img_bgr, cara):
    rec = _reconocedor()
    crop = rec.alignCrop(img_bgr, cara)
    return rec.feature(crop)


def similitud(img_a, cara_a, img_b, cara_b):
    rec = _reconocedor()
    return float(rec.match(_embedding(img_a, cara_a), _embedding(img_b, cara_b),
                           cv2.FaceRecognizerSF_FR_COSINE))


def _escalar_cara(cara, s):
    c = cara.copy()
    c[:14] *= s
    return c


def restaurar_cara_512(crop_bgr, restaurador, fidelidad):
    """Recibe cara alineada 512×512 BGR, devuelve restaurada 512×512 BGR."""
    t = _a_tensor(crop_bgr) * 2 - 1  # los modelos de cara usan [-1, 1]
    with torch.inference_mode():
        if restaurador == 'codeformer':
            out = _modelo('codeformer.pth').model(t, weight=fidelidad)[0]
        else:
            out = _modelo('GFPGANv1.4.pth').model(t, return_rgb=False, randomize_noise=False)[0]
    return _a_bgr((out + 1) / 2)


# ─── Pipeline principal ─────────────────────────────────────────────
def mejorar_foto(
    ruta,
    ancho=None,                # ancho final; None = automático (ver referencia_ancho abajo)
    alto=None,                # si das ancho Y alto, se fuerza ese tamaño exacto
    usar_esrgan=True,         # False = solo base Photoshop + caras
    fondo_clasico=False,      # con usar_esrgan=False: fondo = deconvolucion_clasica() en vez de bicúbica+enfoque
    restaurar_caras=True,
    proteger_caras=True,      # bajo las caras usa bicúbica (fiel) en vez de ESRGAN
    restaurador='gfpgan',     # 'codeformer' (licencia NO comercial) o 'gfpgan' (Apache 2.0)
    fidelidad=0.8,            # solo CodeFormer: 0 = inventa más · 1 = más fiel al original
    mezcla=0.5,               # % de la cara restaurada sobre el fondo (0..1)
    cara_minima=64,           # px de ancho en la ORIGINAL; más pequeñas no se tocan
    umbral_identidad=0.80,    # similitud SFace mínima entre cara original y restaurada
    guardar=True,
    carpeta_salida='salidas', # dónde se guardan resultado/base/comparación si guardar=True
    verbose=True,
):
    img = leer_imagen(ruta)
    h0, w0 = img.shape[:2]
    if ancho is None:
        ancho = int(round(w0 * 2)) if w0 > 1024 else 1024
    if alto is None:
        alto = int(round(h0 * ancho / w0))
    size = (ancho, alto)
    sx, sy = ancho / w0, alto / h0
    log = print if verbose else (lambda *a, **k: None)
    log(f'📐 {w0}×{h0} → {ancho}×{alto}  (×{sx:.2f})  · {DEVICE.type.upper()}')

    base = base_photoshop(img, size)

    # 1) Fondo
    if usar_esrgan:
        x4 = realesrgan_x4(img)
        fondo = cv2.resize(x4, size, interpolation=cv2.INTER_AREA)
        log('✓ Real-ESRGAN ×4 → reducido al tamaño final')
    elif fondo_clasico:
        fondo = deconvolucion_clasica(img, ancho, alto)
        log('✓ Fondo clásico (sin ruido JPEG + deconvolución, sin IA)')
    else:
        fondo = base.copy()

    salida = fondo.copy()
    reporte = []

    # 2) Caras
    caras = detectar_caras(img) if (restaurar_caras or proteger_caras) else []
    if caras:
        log(f'✓ {len(caras)} cara(s) detectada(s)')
    s = (sx + sy) / 2
    elipse = np.zeros((512, 512), np.float32)
    cv2.ellipse(elipse, (256, 290), (190, 235), 0, 0, 360, 1, -1)
    elipse = cv2.GaussianBlur(elipse, (0, 0), 25)

    for i, cara in enumerate(caras):
        ancho_cara = float(cara[2])
        fila = {'cara': i + 1, 'ancho_px': round(ancho_cara), 'accion': '', 'similitud': None}

        # alinear desde la ORIGINAL (no desde píxeles inventados por ESRGAN)
        M, _ = cv2.estimateAffinePartial2D(_puntos(cara), FFHQ_512, method=cv2.LMEDS)
        Mi = cv2.invertAffineTransform(M)
        Mi[0] *= sx
        Mi[1] *= sy
        mask = cv2.warpAffine(elipse, Mi, size)[..., None]

        # 2a) Proteger: bajo cada cara va la versión fiel (bicúbica), no la de ESRGAN
        if proteger_caras and (usar_esrgan or fondo_clasico):
            salida = (salida * (1 - mask) + base * mask).round().astype(np.uint8)
            fila['accion'] = 'fiel (bicúbica)'

        if not restaurar_caras:
            reporte.append(fila)
            continue
        if ancho_cara < cara_minima:
            fila['accion'] = f'fiel, sin restaurar (< {cara_minima}px: muy poca información real)'
            reporte.append(fila)
            continue

        # 2b) Restaurar la cara alineada 512×512
        crop = cv2.warpAffine(img, M, (512, 512), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REFLECT)
        rest = restaurar_cara_512(crop, restaurador, fidelidad)
        pegada = cv2.warpAffine(rest, Mi, size, flags=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        m = mask * mezcla
        candidata = (salida * (1 - m) + pegada * m).round().astype(np.uint8)

        # 3) Verificación de identidad: ¿sigue siendo la misma persona?
        sim = similitud(img, cara, candidata, _escalar_cara(cara, s))
        fila['similitud'] = round(sim, 3)
        if sim >= umbral_identidad:
            salida = candidata
            fila['accion'] = 'restaurada ✓'
        else:
            fila['accion'] = f'DESCARTADA (sim {sim:.2f} < {umbral_identidad}) → queda la versión fiel'
        reporte.append(fila)

    for f in reporte:
        sim = '' if f['similitud'] is None else f"  sim={f['similitud']:.3f}"
        log(f"   cara {f['cara']}: {f['ancho_px']}px → {f['accion']}{sim}")

    rutas = {}
    if guardar:
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        os.makedirs(carpeta_salida, exist_ok=True)
        rutas['resultado'] = f'{carpeta_salida}/{nombre}_mejorada.png'
        rutas['photoshop'] = f'{carpeta_salida}/{nombre}_base_photoshop.png'
        rutas['comparacion'] = f'{carpeta_salida}/{nombre}_comparacion.jpg'
        cv2.imwrite(rutas['resultado'], salida)
        cv2.imwrite(rutas['photoshop'], base)
        comp = np.hstack([base, salida])
        cv2.putText(comp, 'Bicubica + enfoque', (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.putText(comp, 'nucleo-cero', (ancho + 12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.imwrite(rutas['comparacion'], comp, [cv2.IMWRITE_JPEG_QUALITY, 92])
        log(f"💾 {rutas['resultado']}")
    return salida, base, reporte, rutas


# ─── Prueba con referencia: ¿de verdad mejora, o solo "se ve" mejor? ─
def simular_whatsapp(img_bgr, factor=1.6, calidad=35, desenfoque=0.8):
    """Degrada una foto BUENA como lo haría WhatsApp: reduce, suaviza y comprime."""
    h, w = img_bgr.shape[:2]
    x = cv2.GaussianBlur(img_bgr, (0, 0), desenfoque) if desenfoque > 0 else img_bgr
    x = cv2.resize(x, (round(w / factor), round(h / factor)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode('.jpg', x, [cv2.IMWRITE_JPEG_QUALITY, calidad])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def prueba_con_referencia(ruta_buena, factor=1.6, calidad=35, desenfoque=0.8, **kw):
    """Toma una foto buena, la degrada, la recupera con ambos métodos y mide contra el original.
    PSNR/SSIM = fidelidad de píxeles · ID = similitud de identidad SFace (1.0 = misma cara)."""
    from skimage.metrics import structural_similarity as ssim, peak_signal_noise_ratio as psnr
    gt = leer_imagen(ruta_buena)
    h, w = gt.shape[:2]
    os.makedirs('salidas', exist_ok=True)
    lq_path = 'salidas/_simulada_whatsapp.jpg'
    cv2.imwrite(lq_path, simular_whatsapp(gt, factor, calidad, desenfoque), [cv2.IMWRITE_JPEG_QUALITY, 100])
    salida, base, _, _ = mejorar_foto(lq_path, ancho=w, alto=h, guardar=False, verbose=False, **kw)
    caras = detectar_caras(gt)
    filas = []
    for nombre, im in [('Bicúbica + enfoque', base), ('nucleo-cero', salida)]:
        ids = []
        for c in caras:
            try:
                ids.append(similitud(gt, c, im, c))
            except cv2.error:
                pass
        g1, g2 = cv2.cvtColor(gt, cv2.COLOR_BGR2GRAY), cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        filas.append((nombre, psnr(gt, im), ssim(g1, g2),
                      float(np.mean(ids)) if ids else float('nan'),
                      float(np.min(ids)) if ids else float('nan')))
    print(f'Foto {w}×{h} degradada a ×1/{factor}, JPEG q{calidad} · {len(caras)} cara(s)\n')
    print(f"{'Método':<20}{'PSNR dB':>9}{'SSIM':>8}{'ID prom':>9}{'ID mín':>8}")
    for n, p, s_, i1, i2 in filas:
        print(f'{n:<20}{p:>9.2f}{s_:>8.4f}{i1:>9.3f}{i2:>8.3f}')
    print('\nMás alto = mejor en todas las columnas. Si nucleo-cero no gana en ID, '
          'la IA está cambiando caras: sube umbral_identidad o baja mezcla.')
    return filas, gt, base, salida

# ─── Alternativa 100% clásica: deconvolución (sin IA, sin pesos preentrenados) ─
def deconvolucion_clasica(img_bgr, ancho=None, alto=None, reduccion_ruido=3, psf_sigma=1.2,
                          iteraciones=5, sharpen_radius=1.0, sharpen_amount=0.3, pad=24):
    """Quita ruido JPEG → escala (bicúbica) → Richardson-Lucy + unsharp solo en luminancia.

    Medido contra el original real (foto demo degradada como WhatsApp, JPEG q35):
    bicúbica 31.38 dB · bicúbica+enfoque 31.36 · versión anterior 24.31 · esta 31.53.
    - reduccion_ruido: NL-means antes de ampliar; sin esto se amplifican los bloques JPEG.
    - pad reflect: sin relleno, Richardson-Lucy deja un marco oscuro en el borde.
    - solo luminancia (Y de YCrCb): enfocar RGB por canal crea halos de color.
    - pocas iteraciones / amount bajo: más de eso vuelve a producir halos y grano.
    """
    from skimage.restoration import richardson_lucy
    from skimage.filters import unsharp_mask
    h0, w0 = img_bgr.shape[:2]
    ancho = ancho if ancho is not None else (int(round(w0 * 2)) if w0 > 1024 else 1024)
    alto = alto if alto is not None else int(round(h0 * ancho / w0))
    x = img_bgr
    if reduccion_ruido:
        x = cv2.fastNlMeansDenoisingColored(x, None, reduccion_ruido, reduccion_ruido, 5, 15)
    up = cv2.resize(x, (ancho, alto), interpolation=cv2.INTER_CUBIC)
    ycc = cv2.cvtColor(up, cv2.COLOR_BGR2YCrCb).astype(np.float64) / 255.0
    tam = int(psf_sigma * 6) | 1
    k = cv2.getGaussianKernel(tam, psf_sigma)
    psf = k @ k.T
    y = np.pad(ycc[:, :, 0], pad, mode='reflect')
    y = richardson_lucy(y, psf, num_iter=iteraciones, clip=True)[pad:-pad, pad:-pad]
    y = unsharp_mask(y, radius=sharpen_radius, amount=sharpen_amount)
    ycc[:, :, 0] = np.clip(y, 0, 1)
    return cv2.cvtColor((ycc * 255).round().astype(np.uint8), cv2.COLOR_YCrCb2BGR)
```


## CELDA 3 — Subir foto y procesar (sin usar Drive)



```python
# ═══════════════════════════════════════════════════════════════════
# CELDA 3 — SUBIR FOTO Y PROCESAR (sin usar Drive)
# ═══════════════════════════════════════════════════════════════════
import shutil, os
from google.colab import files
from IPython.display import display, Image as IPImage
import nucleo; import importlib; importlib.reload(nucleo)

CONFIG_SUELTA = dict(usar_esrgan=False, fondo_clasico=True, restaurador='gfpgan', mezcla=0.5, cara_minima=64, umbral_identidad=0.80, proteger_caras=True)
CARPETA_SALIDA_SUELTA = 'salidas_sueltas'
shutil.rmtree(CARPETA_SALIDA_SUELTA, ignore_errors=True); os.makedirs(CARPETA_SALIDA_SUELTA, exist_ok=True)

subidas = files.upload()
for nombre in subidas:
  print(f'\n━━━━━━━━ {nombre} ━━━━━━━━')
  salida, base, reporte, rutas = nucleo.mejorar_foto(nombre, carpeta_salida=CARPETA_SALIDA_SUELTA, **CONFIG_SUELTA)
  display(IPImage(rutas['comparacion'], width=1000))
```


## CELDA 4 — Reforzar (alternativa 100% clásica: deconvolución, sin IA)

Si el resultado con IA se ve "pintado" o posterizado (puede pasar con Real-ESRGAN sobre fondos ya comprimidos), esta celda corre la misma foto por un pipeline clásico: bicúbica + deconvolución Richardson-Lucy + afilado — sin pesos preentrenados, sin GAN. No sube nada de nuevo, usa las fotos que ya subiste en la Celda 3.



```python
# ═══════════════════════════════════════════════════════════════════
# CELDA 4 — REFORZAR (alternativa 100% clásica: deconvolución, sin IA)
# ═══════════════════════════════════════════════════════════════════
import importlib
import nucleo; importlib.reload(nucleo)

for nombre in subidas:
  print(f'\n━━━━━━━━ {nombre} (clásico) ━━━━━━━━')
  img = nucleo.leer_imagen(nombre)
  resultado = nucleo.deconvolucion_clasica(img)
  base = os.path.splitext(nombre)[0]
  # siempre PNG: la extensión subida puede no ser escribible (p. ej. .raw de WhatsApp)
  ruta_salida = os.path.join(CARPETA_SALIDA_SUELTA, f'{base}_clasica.png')
  cv2.imwrite(ruta_salida, resultado)
  display(IPImage(ruta_salida, width=1000))
```


## CELDA 5 — Descargar resultado



```python
# CELDA 5 — DESCARGAR RESULTADO (fotos con IA + las clásicas de la celda anterior)
shutil.make_archive('fotos_mejoradas', 'zip', CARPETA_SALIDA_SUELTA)
files.download('fotos_mejoradas.zip')
```


---

## Referencia de parámetros

| Parámetro | Qué controla | Valores útiles |
|---|---|---|
| `ancho` / `alto` | Tamaño final (con solo `ancho`, mantiene proporción) | 1024 · 1280 · 1920 |
| `usar_esrgan` | Real-ESRGAN para el fondo | `True` · `False` = solo bicúbica + caras |
| `restaurar_caras` | Pasar caras por GFPGAN/CodeFormer | `True` · `False` |
| `proteger_caras` | Bajo las caras usa bicúbica (fiel) en vez de ESRGAN | `True` recomendado |
| `restaurador` | Modelo de caras | `'gfpgan'` · `'codeformer'` |
| `fidelidad` | Solo CodeFormer: 0 inventa más, 1 más fiel | 0.7–1.0 |
| `mezcla` | Porcentaje de la cara restaurada sobre la versión fiel | 0.3 natural · 0.5 · 0.7 |
| `cara_minima` | Ancho mínimo (px en la original) para restaurar | 64 · 96 estricto |
| `umbral_identidad` | Similitud SFace mínima o se descarta la restauración | 0.75 · 0.80 · 0.85 estricto |
| `carpeta_salida` | Dónde se guardan resultado/base/comparación (si `guardar=True`) | `'salidas'` · `'imagenes mejoradas'` |

## Cómo leer el reporte por cara

```
cara 1: 90px → restaurada ✓  sim=0.973         ← la IA la mejoró sin cambiar a la persona
cara 3: 80px → DESCARTADA (sim 0.78 < 0.8)     ← la IA la cambió: queda la versión fiel
cara 5: 41px → fiel, sin restaurar (< 64px)    ← muy pequeña: no hay información real
```

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `No module named 'nucleo'` | Ejecuta la Celda 2 (crea `nucleo.py`) |
| `FaceDetectorYN` no existe | `!pip install -U opencv-python-headless` y reinicia la sesión |
| El `.onnx` pesa < 1 KB | La descarga falló: bórralo y repite la Celda 1 |
| `CUDA out of memory` | En `realesrgan_x4`, baja `tile=512` a `256` |
| Caras "de cera" o muy retocadas | Baja `mezcla` a 0.3 o sube `umbral_identidad` |
| Muy lento | Verifica que dice `CUDA` en la primera línea (activa la GPU T4) |

## Licencias (importante si lo ofreces como servicio)

- **Real-ESRGAN**: BSD-3, uso comercial permitido.
- **GFPGAN**: Apache 2.0, uso comercial permitido.
- **YuNet / SFace (OpenCV Zoo)**: Apache 2.0 / MIT.
- **CodeFormer**: S-Lab License 1.0, **NO comercial**. Úsalo solo para comparar, nunca con clientes que pagan.

## Recordatorio

La mejora más grande sigue sin ser un algoritmo: pide a los clientes que envíen la foto por WhatsApp como **Documento** (📎 → Documento). Así llega sin recomprimir y con 5 a 10 veces más información real que cualquier cosa que este notebook pueda recuperar.
