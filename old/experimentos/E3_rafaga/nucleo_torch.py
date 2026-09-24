# =============================================================================
#  EXPERIMENTOS E1 + E3 — Reconstrucción por modelo directo con ráfaga
#  Método de Recuperación Certificada
#
#  Adaptado de una versión para Google Colab (E1_E3_colab.py, provista por
#  el usuario) para correr localmente en el Mac, sobre las fotos reales de
#  experimentos/E1_deconvolucion/fuente/, en CPU (CLAUDE.md: sin GPU).
#
#  Requiere el venv de Python 3.12 en experimentos/E3_rafaga/.venv312/
#  (torch todavía no tiene wheel para Python 3.14, la versión del resto
#  del proyecto — ver avance correspondiente).
#
#  Este archivo es la LIBRERÍA (sin CLI). El punto de entrada es
#  experimentos/E3_rafaga/mvp.py.
#
#  QUÉ RESPONDE ESTE SCRIPT
#    E1: ¿la reconstrucción por modelo directo supera a bicúbica, y cuánto?
#    E3: ¿la alineación alcanza precisión sub-píxel < 0.2 px?
#        ¿la ráfaga aporta resolución real o solo reduce ruido?
#
#  DIFERENCIAS CLAVE frente a una versión ingenua:
#    1. La pose W_k va DENTRO del operador directo. Los datos NO se alinean.
#       (alinear los datos destruye la diversidad de fase que da la ganancia)
#    2. Un único operador A = D·H·W_k, usado por síntesis y reconstrucción.
#    3. Todo el cómputo en LUZ LINEAL.
#    4. Se mide contra la verdad de referencia, no solo contra bicúbica.
#    5. Se reporta la diversidad de fase sub-píxel: si no la hay, se dice.
#    6. Se calcula tau (energía de núcleo) y la consistencia.
#    7. Rechazo robusto real (Tukey redescendente), no "Charbonnier y confiar".
# =============================================================================

import math

import torch
import torch.nn.functional as F
import torchvision.transforms.functional as TF
from PIL import Image

dev = torch.device("cpu")  # CLAUDE.md: sin GPU, sin Metal/MPS

# ----------------------------------------------------------------------------
#  1. COLOR — sRGB <-> luz lineal
# ----------------------------------------------------------------------------


def srgb_a_lineal(x):
    return torch.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lineal_a_srgb(x):
    x = x.clamp(1e-8, 1.0)
    return torch.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


# ----------------------------------------------------------------------------
#  2. OPERADOR DIRECTO UNIFICADO      A_k(x) = D · H · W_k · x
# ----------------------------------------------------------------------------


def nucleo_gauss_1d(sigma, device):
    r = max(1, int(math.ceil(3.0 * sigma)))
    t = torch.arange(-r, r + 1, device=device, dtype=torch.float32)
    k = torch.exp(-(t**2) / (2 * sigma**2))
    return k / k.sum()


def desenfocar(x, k1d):
    C = x.shape[1]
    r = (k1d.numel() - 1) // 2
    kh = k1d.view(1, 1, 1, -1).expand(C, 1, 1, -1)
    kv = k1d.view(1, 1, -1, 1).expand(C, 1, -1, 1)
    x = F.conv2d(F.pad(x, (r, r, 0, 0), mode="reflect"), kh, groups=C)
    x = F.conv2d(F.pad(x, (0, 0, r, r), mode="reflect"), kv, groups=C)
    return x


def theta_de_params(p):
    c, s = torch.cos(p[2]), torch.sin(p[2])
    fila1 = torch.stack([c, -s, p[0]])
    fila2 = torch.stack([s, c, p[1]])
    return torch.stack([fila1, fila2]).unsqueeze(0)


def deformar(x, theta):
    grid = F.affine_grid(theta, x.shape, align_corners=False)
    return F.grid_sample(x, grid, mode="bicubic", padding_mode="reflection", align_corners=False)


def operador_directo(x_hr, p, k1d, factor):
    return F.avg_pool2d(desenfocar(deformar(x_hr, theta_de_params(p)), k1d), factor)


# ----------------------------------------------------------------------------
#  3. RUIDO — estimador MAD de Donoho sobre detalle diagonal
# ----------------------------------------------------------------------------


def estimar_sigma(x, bloque=24, pct=0.15):
    d = x[:, :, 0::2, 0::2] - x[:, :, 0::2, 1::2] - x[:, :, 1::2, 0::2] + x[:, :, 1::2, 1::2]
    d = (d / 2.0).abs()
    H, W = d.shape[-2:]
    if H < bloque or W < bloque:
        return (d.median() / 0.6745).item()
    bh, bw = H // bloque, W // bloque
    d = d[:, :, : bh * bloque, : bw * bloque]
    bloques = d.unfold(2, bloque, bloque).unfold(3, bloque, bloque)
    mad = bloques.reshape(*bloques.shape[:4], -1).median(dim=-1).values.flatten()
    k = max(0, min(mad.numel() - 1, int(pct * mad.numel())))
    return (mad.sort().values[k] / 0.6745).item()


# ----------------------------------------------------------------------------
#  4. ALINEACIÓN PIRAMIDAL HASTA ESCALA COMPLETA
# ----------------------------------------------------------------------------


def _grad_xy(x):
    return (x[:, :, :, 1:] - x[:, :, :, :-1]), (x[:, :, 1:, :] - x[:, :, :-1, :])


def estimar_pose(ref_lr, mov_lr, niveles=4, escala_vueltas=1.0):
    p = torch.zeros(3, device=dev, requires_grad=True)
    H0, W0 = ref_lr.shape[-2:]

    plan = []
    for nivel in range(niveles - 1, -1, -1):
        esc = 2**nivel
        h, w = H0 // esc, W0 // esc
        if h >= 24 and w >= 24:
            plan.append((esc, h, w))
    if not plan:
        plan = [(1, H0, W0)]

    for idx, (esc, h, w) in enumerate(plan):
        if esc == 1:
            r, m = ref_lr, mov_lr
        else:
            r = TF.resize(ref_lr, [h, w], antialias=True)
            m = TF.resize(mov_lr, [h, w], antialias=True)
        m = m - m.mean()
        paso = [0.03, 0.012, 0.005, 0.002][min(idx, 3)]
        vueltas = max(20, int([200, 250, 300, 400][min(idx, 3)] * escala_vueltas))
        opt = torch.optim.Adam([p], lr=paso)
        mdx, mdy = _grad_xy(m)
        for _ in range(vueltas):
            opt.zero_grad()
            a = deformar(r, theta_de_params(p))
            a = a - a.mean()
            adx, ady = _grad_xy(a)
            perdida = (
                torch.sqrt((a - m) ** 2 + 1e-6).mean()
                + torch.sqrt((adx - mdx) ** 2 + 1e-6).mean()
                + torch.sqrt((ady - mdy) ** 2 + 1e-6).mean()
            )
            perdida.backward()
            opt.step()
    return p.detach()


def theta_a_px(p, H, W):
    return (p[0].item() * W / 2.0, p[1].item() * H / 2.0)


# ----------------------------------------------------------------------------
#  5. DIAGNÓSTICO DE FASE SUB-PÍXEL
# ----------------------------------------------------------------------------


def diversidad_de_fase(desplazamientos_px, factor):
    fases = []
    for dx, dy in desplazamientos_px:
        fases.append(((dx / factor) % 1.0, (dy / factor) % 1.0))
    div = []
    for eje in (0, 1):
        ang = torch.tensor([2 * math.pi * f[eje] for f in fases])
        R = torch.sqrt(torch.cos(ang).mean() ** 2 + torch.sin(ang).mean() ** 2)
        div.append(1.0 - R.item())
    return fases, div


# ----------------------------------------------------------------------------
#  6. PESOS ROBUSTOS — Tukey redescendente
# ----------------------------------------------------------------------------


def pesos_tukey(residuo, c):
    a = (residuo / c) ** 2
    w = (1.0 - a) ** 2
    return torch.where(a <= 1.0, w, torch.zeros_like(w))


# ----------------------------------------------------------------------------
#  7. REGULARIZADOR DECLARADO — variación total (capa 3)
# ----------------------------------------------------------------------------


def tv(x, epsilon=1e-3):
    """Charbonnier-TV. El valor de epsilon importa mucho, no es un detalle
    numérico: con epsilon≈1e-8 (equivalente a TV/L1 puro) el regularizador
    favorece soluciones por tramos constantes — a MAX_LADO=2400 esto se vio
    como el efecto "acuarela"/staircase (retroalimentación del usuario,
    notebook nucleo_cero.ipynb, celda 12: LAMBDA_TV=8.0, epsilon chico,
    2400px → acuarela). Subir epsilon a 1e-3 (celda 13 del mismo notebook)
    extiende el régimen cuadrático (más parecido a L2, no favorece
    aplanar) sobre un rango más ancho de gradientes típicos de textura
    real, y fue justo lo que eliminó el efecto acuarela — no el cambio de
    L1 a Charbonnier en sí (eso ya lo teníamos desde avance-1.8) sino este
    valor de epsilon en particular."""
    dx = x[:, :, :, 1:] - x[:, :, :, :-1]
    dy = x[:, :, 1:, :] - x[:, :, :-1, :]
    return torch.sqrt(dx**2 + epsilon**2).mean() + torch.sqrt(dy**2 + epsilon**2).mean()


# ----------------------------------------------------------------------------
#  8. RECONSTRUCCIÓN
# ----------------------------------------------------------------------------


def reconstruir(observaciones, poses, k1d, factor, sigma_n, lam_tv, iters, lr=0.03, robusto=True, verbose=True):
    H_lr, W_lr = observaciones[0].shape[-2:]
    H_hr, W_hr = H_lr * factor, W_lr * factor

    x = (
        TF.resize(observaciones[0], [H_hr, W_hr], interpolation=TF.InterpolationMode.BICUBIC, antialias=True)
        .clone()
        .clamp(0, 1)
    )
    x.requires_grad_(True)

    opt = torch.optim.Adam([x], lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=iters, eta_min=lr * 0.02)
    c_tukey = 4.685 * max(sigma_n, 1e-4)
    pesos = [torch.ones_like(o) for o in observaciones]
    historial = []

    for it in range(iters):
        if robusto and it % 25 == 0 and it > 0:
            with torch.no_grad():
                pesos = [
                    pesos_tukey(operador_directo(x, pk, k1d, factor) - y, c_tukey)
                    for y, pk in zip(observaciones, poses)
                ]

        opt.zero_grad()
        fidelidad = 0.0
        for y, pk, w in zip(observaciones, poses, pesos):
            r = operador_directo(x, pk, k1d, factor) - y
            fidelidad = fidelidad + (w * torch.sqrt(r**2 + 1e-6)).mean()
        perdida = fidelidad / len(observaciones) + lam_tv * tv(x)
        perdida.backward()
        opt.step()
        sched.step()
        with torch.no_grad():
            x.clamp_(0, 1)

        historial.append(perdida.item())
        if verbose and (it + 1) % 75 == 0:
            print(f"    iter {it+1:4d} | perdida {perdida.item():.6f} | paso {sched.get_last_lr()[0]:.5f}")

    if verbose:
        cola = historial[-40:]
        deriva = cola[-1] - min(cola)
        estado = "✓ estable" if deriva <= 1e-5 else "⚠ aún derivando: subir ITERS"
        print(f"    convergencia: {estado} (deriva final {deriva:+.2e})")

    return x.detach()


# ----------------------------------------------------------------------------
#  9. CERTIFICADO — consistencia y tau
# ----------------------------------------------------------------------------


def consistencia(x, observaciones, poses, k1d, factor, sigma_n):
    with torch.no_grad():
        res = [
            torch.sqrt(((operador_directo(x, pk, k1d, factor) - y) ** 2).mean()).item()
            for y, pk in zip(observaciones, poses)
        ]
    rmse = sum(res) / len(res)
    return rmse, rmse / max(sigma_n, 1e-6)


def tau_nucleo(x_con_tv, x_sin_tv):
    with torch.no_grad():
        num = torch.sqrt(((x_con_tv - x_sin_tv) ** 2).sum()).item()
        den = torch.sqrt((x_sin_tv**2).sum()).item()
    return num / max(den, 1e-12)


# ----------------------------------------------------------------------------
#  10. MÉTRICAS CONTRA LA VERDAD
# ----------------------------------------------------------------------------


def psnr(a, b):
    mse = ((a - b) ** 2).mean().item()
    return 10 * math.log10(1.0 / max(mse, 1e-12))


def ssim(a, b, sigma=1.5):
    k = nucleo_gauss_1d(sigma, a.device)
    mu_a, mu_b = desenfocar(a, k), desenfocar(b, k)
    saa = desenfocar(a * a, k) - mu_a**2
    sbb = desenfocar(b * b, k) - mu_b**2
    sab = desenfocar(a * b, k) - mu_a * mu_b
    C1, C2 = 0.01**2, 0.03**2
    s = ((2 * mu_a * mu_b + C1) * (2 * sab + C2)) / ((mu_a**2 + mu_b**2 + C1) * (saa + sbb + C2))
    return s.mean().item()


# ----------------------------------------------------------------------------
#  CARGA LOCAL (reemplaza el upload de Colab)
# ----------------------------------------------------------------------------


def cargar(ruta, factor, max_lado):
    img = Image.open(ruta).convert("RGB")
    t = TF.to_tensor(img).unsqueeze(0).to(dev)
    if max(t.shape[-2:]) > max_lado:
        esc = max_lado / max(t.shape[-2:])
        h = int(t.shape[-2] * esc) // factor * factor
        w = int(t.shape[-1] * esc) // factor * factor
        t = TF.resize(t, [h, w], antialias=True)
    else:
        h = t.shape[-2] // factor * factor
        w = t.shape[-1] // factor * factor
        t = t[:, :, :h, :w]
    return srgb_a_lineal(t.clamp(0, 1))
