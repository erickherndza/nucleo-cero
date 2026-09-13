"""
MVP local del pipeline E1+E3+certificado (ver avance-1.8.md).

Dos modos:
  validacion  — sube 1 imagen nítida. Fabrica una ráfaga sintética con
                desplazamientos conocidos, degrada, reconstruye y compara
                contra la verdad. Responde E1 y E3 con números.
  produccion  — sube >= 2 fotos de una ráfaga real. No hay verdad de
                referencia: solo se emite el certificado (tau + consistencia).

Dos perfiles de velocidad (CLAUDE.md: Mac sin GPU — ver avance-1.8.md,
el perfil "completo" tomó ~11 min en CPU frente a 16.3s en GPU):
  rapido    — para iterar rápido durante desarrollo/pruebas (~1-2 min)
  completo  — parámetros del experimento original (~10-15 min en CPU)

Uso:
    source experimentos/E3_rafaga/.venv312/bin/activate
    python experimentos/E3_rafaga/mvp.py validacion foto.jpg --perfil rapido
    python experimentos/E3_rafaga/mvp.py produccion foto1.jpg foto2.jpg foto3.jpg
"""
from __future__ import annotations

import argparse
import math
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch

import nucleo_torch as nt

SEMILLA = 7

PERFILES = {
    # factor, k_frames, sigma_psf, ruido_sint, iters, max_lado, escala_vueltas
    "rapido": dict(factor=2, k_frames=4, sigma_psf=1.1, ruido_sint=0.004, iters=100, max_lado=256, escala_vueltas=0.35),
    "completo": dict(factor=2, k_frames=6, sigma_psf=1.1, ruido_sint=0.004, iters=300, max_lado=512, escala_vueltas=1.0),
}
LAMBDA_TV = 8.0
LR_RECON = 0.03


@dataclass
class Certificado:
    consistencia_rmse: float
    ratio_residuo_ruido: float
    tau: float
    nivel_servicio: str
    sigma_n: float
    fases_ok: bool
    div_fase: tuple[float, float]
    err_alineacion_px: float | None = None  # solo validación


UMBRAL_CONSISTENCIA = 1.5  # mismo umbral que ya se usa para el símbolo ✓/✗ del certificado


def _nivel_servicio(tau: float, ratio_residuo_ruido: float) -> str:
    """El nivel de servicio solo tiene sentido si el modelo ajustó bien a
    los datos. τ bajo con un ajuste inconsistente no es "alta confianza":
    es que el certificado no puede responder por el resultado (avance-1.10
    — ráfaga real de sujetos vivos, ratio=3.07, tau seguía diciendo
    "Comercial" como si nada, sin mirar la inconsistencia)."""
    if ratio_residuo_ruido >= UMBRAL_CONSISTENCIA:
        return "NO CONFIABLE — el modelo no ajusta bien a estos datos (ver ratio residuo/ruido)"
    if tau <= 0.01:
        return "Forense (<=0.01)"
    if tau <= 0.05:
        return "Archivo (<=0.05)"
    if tau <= 0.15:
        return "Comercial (<=0.15)"
    return "FUERA DE PRESUPUESTO"


def _reconstruir_y_certificar(observaciones, poses, k1d, cfg, sigma_0, iters, lam_tv_base, verbose):
    x_cal = nt.reconstruir(
        observaciones, poses, k1d, cfg["factor"], sigma_0, lam_tv_base * sigma_0,
        max(40, iters // 3), lr=LR_RECON, verbose=False,
    )
    _, ratio_cal = nt.consistencia(x_cal, observaciones, poses, k1d, cfg["factor"], sigma_0)
    factor_cal = min(3.0, max(0.2, ratio_cal))
    sigma_n = sigma_0 * factor_cal
    lam = lam_tv_base * sigma_n

    if verbose:
        print(f"  discrepancia medida = {ratio_cal:.2f}  ->  sigma_n corregido = {sigma_n:.5f}")

    x_rec = nt.reconstruir(observaciones, poses, k1d, cfg["factor"], sigma_n, lam, iters, lr=LR_RECON, verbose=verbose)
    x_min = nt.reconstruir(
        observaciones, poses, k1d, cfg["factor"], sigma_n, 0.0, iters, lr=LR_RECON, verbose=False
    )

    rmse, ratio = nt.consistencia(x_rec, observaciones, poses, k1d, cfg["factor"], sigma_n)
    tau = nt.tau_nucleo(x_rec, x_min)
    return x_rec, sigma_n, rmse, ratio, tau


def correr_validacion(ruta_imagen: Path, perfil: str, salida: Path) -> None:
    cfg = PERFILES[perfil]
    torch.manual_seed(SEMILLA)
    t0 = time.time()
    k1d = nt.nucleo_gauss_1d(cfg["sigma_psf"], nt.dev)

    x_verdad = nt.cargar(ruta_imagen, cfg["factor"], cfg["max_lado"])
    H, W = x_verdad.shape[-2:]
    print(f"Verdad de referencia: {W}x{H} (luz lineal) — perfil '{perfil}'")

    poses_reales, observaciones = [], []
    for k in range(cfg["k_frames"]):
        if k == 0:
            tx_px, ty_px, ang = 0.0, 0.0, 0.0
        else:
            tx_px = (torch.rand(1).item() - 0.5) * 2.0 * cfg["factor"]
            ty_px = (torch.rand(1).item() - 0.5) * 2.0 * cfg["factor"]
            ang = (torch.rand(1).item() - 0.5) * 0.004
        p = torch.tensor([tx_px * 2.0 / W, ty_px * 2.0 / H, ang], device=nt.dev)
        poses_reales.append(p)
        y = nt.operador_directo(x_verdad, p, k1d, cfg["factor"])
        y = (y + cfg["ruido_sint"] * torch.randn_like(y)).clamp(0, 1)
        observaciones.append(y)
    print(f"Ráfaga sintética: {cfg['k_frames']} frames a {W//cfg['factor']}x{H//cfg['factor']}")

    print("\n[E3] Estimando poses...")
    poses_est, errores_px = [torch.zeros(3, device=nt.dev)], []
    for k in range(1, cfg["k_frames"]):
        p_est = nt.estimar_pose(observaciones[0], observaciones[k], escala_vueltas=cfg["escala_vueltas"])
        poses_est.append(p_est)
        H_lr, W_lr = observaciones[0].shape[-2:]
        dx_e, dy_e = nt.theta_a_px(p_est, H_lr, W_lr)
        dx_r, dy_r = nt.theta_a_px(poses_reales[k], H_lr, W_lr)
        err = math.hypot(dx_e - dx_r, dy_e - dy_r)
        errores_px.append(err)
        print(f"    frame {k}: error {err:.3f} px LR")
    err_medio = sum(errores_px) / len(errores_px)
    print(f"  Error medio de alineación: {err_medio:.3f} px LR  ({'🟢 VERDE' if err_medio < 0.2 else '🔴 ROJO'}, umbral 0.2)")

    desplaz = [nt.theta_a_px(p, *observaciones[0].shape[-2:]) for p in poses_est]
    fases, div = nt.diversidad_de_fase(desplaz, cfg["factor"])
    fases_ok = min(div) >= 0.35
    print(f"\n[Diagnóstico] Diversidad de fase (x={div[0]:.2f}, y={div[1]:.2f}): "
          f"{'✓ repartidas' if fases_ok else '⚠ agrupadas — sin aporte de resolución'}")

    sigma_0 = nt.estimar_sigma(observaciones[0])
    print(f"\n[Ruido] sigma_n inicial = {sigma_0:.5f}")
    x_rec, sigma_n, rmse, ratio, tau = _reconstruir_y_certificar(
        observaciones, poses_est, k1d, cfg, sigma_0, cfg["iters"], LAMBDA_TV, verbose=True
    )

    cert = Certificado(rmse, ratio, tau, _nivel_servicio(tau, ratio), sigma_n, fases_ok, tuple(div), err_medio)

    import torchvision.transforms.functional as TF

    bicubico = TF.resize(
        observaciones[0], list(x_rec.shape[-2:]), interpolation=TF.InterpolationMode.BICUBIC, antialias=True
    ).clamp(0, 1)
    v_s, r_s, b_s = nt.lineal_a_srgb(x_verdad), nt.lineal_a_srgb(x_rec), nt.lineal_a_srgb(bicubico)
    p_rec, p_bic = nt.psnr(r_s, v_s), nt.psnr(b_s, v_s)
    s_rec, s_bic = nt.ssim(r_s, v_s), nt.ssim(b_s, v_s)

    tiempo = time.time() - t0
    salida.mkdir(parents=True, exist_ok=True)
    _guardar_comparacion(salida, ruta_imagen.stem, bicubico, x_rec, x_verdad, tau)
    _escribir_informe(
        salida / f"{ruta_imagen.stem}_informe.md", ruta_imagen.name, perfil, cfg, cert, tiempo,
        e1=dict(psnr_bicubica=p_bic, psnr_metodo=p_rec, ssim_bicubica=s_bic, ssim_metodo=s_rec),
    )
    print(f"\nTiempo total: {tiempo:.1f}s. Informe en {salida}/")


def correr_produccion(rutas: list[Path], perfil: str, salida: Path) -> None:
    if len(rutas) < 2:
        raise ValueError("Modo producción requiere al menos 2 fotos de la misma escena (ráfaga real).")
    cfg = PERFILES[perfil]
    torch.manual_seed(SEMILLA)
    t0 = time.time()
    k1d = nt.nucleo_gauss_1d(cfg["sigma_psf"], nt.dev)

    observaciones = [nt.cargar(r, cfg["factor"], cfg["max_lado"]) for r in rutas]
    print(f"Ráfaga real: {len(observaciones)} fotos, perfil '{perfil}'")

    print("\nEstimando poses...")
    poses = [torch.zeros(3, device=nt.dev)]
    for k in range(1, len(observaciones)):
        poses.append(nt.estimar_pose(observaciones[0], observaciones[k], escala_vueltas=cfg["escala_vueltas"]))

    desplaz = [nt.theta_a_px(p, *observaciones[0].shape[-2:]) for p in poses]
    fases, div = nt.diversidad_de_fase(desplaz, cfg["factor"])
    fases_ok = min(div) >= 0.35
    print(f"[Diagnóstico] Diversidad de fase (x={div[0]:.2f}, y={div[1]:.2f}): "
          f"{'✓ repartidas' if fases_ok else '⚠ agrupadas — sin aporte de resolución, solo baja ruido'}")

    sigma_0 = nt.estimar_sigma(observaciones[0])
    print(f"[Ruido] sigma_n inicial = {sigma_0:.5f}")
    x_rec, sigma_n, rmse, ratio, tau = _reconstruir_y_certificar(
        observaciones, poses, k1d, cfg, sigma_0, cfg["iters"], LAMBDA_TV, verbose=True
    )
    cert = Certificado(rmse, ratio, tau, _nivel_servicio(tau, ratio), sigma_n, fases_ok, tuple(div))

    import torchvision.transforms.functional as TF
    bicubico = TF.resize(
        observaciones[0], list(x_rec.shape[-2:]), interpolation=TF.InterpolationMode.BICUBIC, antialias=True
    ).clamp(0, 1)

    tiempo = time.time() - t0
    salida.mkdir(parents=True, exist_ok=True)
    _guardar_comparacion(salida, rutas[0].stem, bicubico, x_rec, None, tau)
    _escribir_informe(salida / f"{rutas[0].stem}_informe.md", rutas[0].name, perfil, cfg, cert, tiempo, e1=None)
    print(f"\nTiempo total: {tiempo:.1f}s. Informe en {salida}/")


def _guardar_comparacion(salida, nombre, bicubico, x_rec, x_verdad, tau):
    n = 3 if x_verdad is not None else 2
    fig, ax = plt.subplots(1, n, figsize=(6 * n, 6))

    def mostrar(eje, tensor, titulo):
        eje.imshow(nt.lineal_a_srgb(tensor).squeeze(0).permute(1, 2, 0).cpu().numpy())
        eje.set_title(titulo, fontsize=11)
        eje.axis("off")

    mostrar(ax[0], bicubico, "Bicúbica (línea base)")
    mostrar(ax[1], x_rec, f"Modelo directo · tau={tau:.3f}")
    if x_verdad is not None:
        mostrar(ax[2], x_verdad, "Verdad de referencia")
    plt.tight_layout()
    ruta = salida / f"{nombre}_comparacion.png"
    fig.savefig(ruta, dpi=120)
    plt.close(fig)

    # imagen reconstruida sola, para entrega
    import torchvision.transforms.functional as TF
    TF.to_pil_image(nt.lineal_a_srgb(x_rec).squeeze(0).cpu()).save(salida / f"{nombre}_reconstruida.png")


def _escribir_informe(ruta_md, nombre_entrada, perfil, cfg, cert: Certificado, tiempo, e1: dict | None):
    lineas = [
        f"# Informe de entrega — {nombre_entrada}",
        "",
        f"Perfil: `{perfil}` (factor={cfg['factor']}, k_frames={cfg['k_frames']}, iters={cfg['iters']}, "
        f"max_lado={cfg['max_lado']}px). Tiempo total: {tiempo:.1f}s.",
        "",
        "## Certificado",
        "",
        f"- Consistencia ‖A x̂ − y‖ = {cert.consistencia_rmse:.5f}  (σ_n = {cert.sigma_n:.5f})",
        f"- Ratio residuo/ruido = {cert.ratio_residuo_ruido:.2f} "
        f"({'✓ consistente' if cert.ratio_residuo_ruido < 1.5 else '✗ inconsistente'})",
        f"- τ (energía de núcleo) = {cert.tau:.4f}",
        f"- Nivel de servicio admisible: **{cert.nivel_servicio}**",
        f"- Diversidad de fase sub-píxel: x={cert.div_fase[0]:.2f}, y={cert.div_fase[1]:.2f} "
        f"({'fases repartidas, hay aliasing desplegable' if cert.fases_ok else 'fases agrupadas — la ráfaga solo reduce ruido, no aporta resolución'})",
    ]
    if cert.err_alineacion_px is not None:
        lineas.append(
            f"- E3 — error medio de alineación: {cert.err_alineacion_px:.3f} px LR "
            f"({'🟢 verde' if cert.err_alineacion_px < 0.2 else '🔴 rojo'}, umbral 0.2px)"
        )
    if e1 is not None:
        ventaja_psnr = e1["psnr_metodo"] - e1["psnr_bicubica"]
        ventaja_ssim = e1["ssim_metodo"] - e1["ssim_bicubica"]
        lineas += [
            "",
            "## E1 — contra la verdad de referencia (modo validación)",
            "",
            f"- PSNR bicúbica {e1['psnr_bicubica']:.2f}dB | método {e1['psnr_metodo']:.2f}dB | "
            f"ventaja {ventaja_psnr:+.2f}dB ({'🟢 verde' if ventaja_psnr >= 2.0 else '🔴 rojo'}, umbral 2dB)",
            f"- SSIM bicúbica {e1['ssim_bicubica']:.4f} | método {e1['ssim_metodo']:.4f} | "
            f"ventaja {ventaja_ssim:+.4f}",
        ]
    else:
        lineas += ["", "_(Modo producción: sin verdad de referencia, solo certificado.)_"]
    ruta_md.write_text("\n".join(lineas) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["validacion", "produccion"])
    ap.add_argument("imagenes", type=Path, nargs="+")
    ap.add_argument("--perfil", choices=list(PERFILES), default="rapido")
    ap.add_argument("--salida", type=Path, default=Path("salida"))
    args = ap.parse_args()

    if args.modo == "validacion":
        correr_validacion(args.imagenes[0], args.perfil, args.salida)
    else:
        correr_produccion(args.imagenes, args.perfil, args.salida)


if __name__ == "__main__":
    main()
