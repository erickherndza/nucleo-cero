# ═══════════════════════════════════════════════════════════════════
# nucleo-cero · motor: mejora de fotos de WhatsApp con control de identidad
#   Real-ESRGAN (fondo) → CodeFormer/GFPGAN (caras grandes) → verificación SFace
#   Sin basicsr / realesrgan / gfpgan / facexlib: todo con spandrel + OpenCV
# Misma lógica que la CELDA 2 de nucleo_cero_v2.ipynb; solo cambian rutas y dispositivo.
# ═══════════════════════════════════════════════════════════════════
import os
import cv2
import numpy as np
import torch
from PIL import Image, ImageOps

import spandrel
import spandrel_extra_arches

from .config import DEVICE, PESOS

try:
    spandrel_extra_arches.install()  # añade CodeFormer al cargador
except Exception:
    pass  # ya registrado
W = PESOS
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
