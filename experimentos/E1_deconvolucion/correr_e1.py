"""
Corre el experimento E1 sobre las imágenes reales en fuente/.

Para cada imagen: recorta la región más nítida (512x512), la degrada con
una PSF y ruido CONOCIDOS, reconstruye con Richardson-Lucy y compara contra
bicúbica al mismo factor. Ver METODO.md §3 (E1) para el criterio de la
puerta.

Uso:
    python correr_e1.py fuente/ --salida resultados_e1.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from nucleo import (
    bicubica_hasta,
    cargar_gris_lineal,
    degradar,
    espectro_radial,
    f_max_teorico,
    banda_recuperada,
    psnr,
    recorte_mas_nitido,
    richardson_lucy_sr,
    ssim,
)

EXTENSIONES_VALIDAS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

# Parámetros del modelo directo simulado — fijos y documentados, no ajustados
# por imagen (eso sería trampa: E1 mide si el algoritmo llega al límite
# TEÓRICO conocido, no si se le puede afinar caso por caso).
TAM_RECORTE = 512
SIGMA_PSF = 1.2
FACTOR = 2
SIGMA_RUIDO = 0.01
SEMILLA = 20260912

# Criterio verde de E1 (METODO.md §3)
BANDA_MINIMA_FRACCION = 0.80
VENTAJA_MINIMA_DB = 2.0


@dataclass
class MedicionE1:
    archivo: str
    psnr_rl: float
    psnr_bicubica: float
    ventaja_db: float
    ssim_rl: float
    ssim_bicubica: float
    f_max_teorico: float
    f_recuperada: float
    fraccion_de_f_max: float
    iteraciones_rl: int


def medir_imagen(ruta: Path, rng: np.random.Generator) -> MedicionE1:
    img = cargar_gris_lineal(ruta)
    x_verdad = recorte_mas_nitido(img, TAM_RECORTE).astype(np.float64)

    y, kernel = degradar(x_verdad, SIGMA_PSF, FACTOR, SIGMA_RUIDO, rng)
    x_rl, iteraciones = richardson_lucy_sr(y, kernel, FACTOR, x_verdad.shape, SIGMA_RUIDO)
    x_bicubica = bicubica_hasta(y, x_verdad.shape)

    psnr_rl, psnr_bicubica = psnr(x_rl, x_verdad), psnr(x_bicubica, x_verdad)
    ssim_rl, ssim_bicubica = ssim(x_rl, x_verdad), ssim(x_bicubica, x_verdad)

    freqs, S_verdad = espectro_radial(x_verdad)
    f_max = f_max_teorico(freqs, S_verdad, SIGMA_PSF, SIGMA_RUIDO)
    f_rec = banda_recuperada(x_rl, x_verdad)
    fraccion = f_rec / f_max if f_max > 0 else 0.0

    return MedicionE1(
        archivo=ruta.name,
        psnr_rl=psnr_rl,
        psnr_bicubica=psnr_bicubica,
        ventaja_db=psnr_rl - psnr_bicubica,
        ssim_rl=ssim_rl,
        ssim_bicubica=ssim_bicubica,
        f_max_teorico=f_max,
        f_recuperada=f_rec,
        fraccion_de_f_max=fraccion,
        iteraciones_rl=iteraciones,
    )


def veredicto(mediciones: list[MedicionE1]) -> dict:
    if not mediciones:
        return {"es_verde": False}
    banda_ok = [m.fraccion_de_f_max >= BANDA_MINIMA_FRACCION for m in mediciones]
    ventaja_ok = [m.ventaja_db >= VENTAJA_MINIMA_DB for m in mediciones]
    return {
        "fraccion_banda_ok": sum(banda_ok) / len(mediciones),
        "fraccion_ventaja_ok": sum(ventaja_ok) / len(mediciones),
        "ventaja_db_media": float(np.mean([m.ventaja_db for m in mediciones])),
        "fraccion_f_max_media": float(np.mean([m.fraccion_de_f_max for m in mediciones])),
        "es_verde": (sum(banda_ok) / len(mediciones) >= 0.8) and (sum(ventaja_ok) / len(mediciones) >= 0.8),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fuente", type=Path)
    ap.add_argument("--salida", type=Path, default=Path("resultados_e1.csv"))
    args = ap.parse_args()

    rng = np.random.default_rng(SEMILLA)
    archivos = sorted(p for p in args.fuente.iterdir() if p.suffix.lower() in EXTENSIONES_VALIDAS)
    if not archivos:
        print(f"No se encontraron imágenes en {args.fuente}", file=sys.stderr)
        sys.exit(1)

    mediciones = []
    for archivo in archivos:
        try:
            m = medir_imagen(archivo, rng)
            mediciones.append(m)
            print(f"  {archivo.name}: ventaja={m.ventaja_db:+.2f}dB  banda={m.fraccion_de_f_max:.0%}")
        except ValueError as e:
            print(f"  [omitida] {archivo.name}: {e}", file=sys.stderr)

    with open(args.salida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(mediciones[0]).keys()))
        w.writeheader()
        for m in mediciones:
            w.writerow(asdict(m))

    v = veredicto(mediciones)
    print(f"\n{len(mediciones)} imágenes medidas. Resultados en {args.salida}")
    print(f"Parámetros: sigma_psf={SIGMA_PSF} factor={FACTOR} sigma_ruido={SIGMA_RUIDO} recorte={TAM_RECORTE}px")
    print(f"Ventaja media sobre bicúbica: {v['ventaja_db_media']:+.2f} dB")
    print(f"Fracción media de f_max recuperado: {v['fraccion_f_max_media']:.0%}")
    print(f"% imágenes con ventaja >= {VENTAJA_MINIMA_DB}dB: {v['fraccion_ventaja_ok']:.0%}")
    print(f"% imágenes con banda >= {BANDA_MINIMA_FRACCION:.0%} de f_max: {v['fraccion_banda_ok']:.0%}")
    print("VEREDICTO:", "🟢 VERDE" if v["es_verde"] else "🔴 ROJO")


if __name__ == "__main__":
    main()
