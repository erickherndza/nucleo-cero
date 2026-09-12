"""
Corre el experimento E2 sobre las imágenes reales en E1_deconvolucion/fuente/.

Degrada cada imagen con el mismo modelo de E1, reconstruye, y por cada
región mide τ (certificado) y el error real contra la verdad. Ver
METODO.md §3 (E2) para el criterio de la puerta — LA que importa según §8.

Uso:
    python correr_e2.py --salida resultados_e2.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

from nucleo import (
    cargar_gris_lineal,
    error_rms,
    correlacion_spearman,
    reconstrucciones_bootstrap,
    regiones,
    tau_incertidumbre,
)

FUENTE_POR_DEFECTO = Path(__file__).resolve().parent.parent / "E1_deconvolucion" / "fuente"
EXTENSIONES_VALIDAS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

TAM_CROP = 1024
TAM_REGION = 128
SIGMA_PSF = 1.2
FACTOR = 2
SIGMA_RUIDO = 0.01
K_BOOTSTRAP = 4
SEMILLA = 20260912

CORRELACION_MINIMA_VERDE = 0.6


def recorte_central(img: np.ndarray, tam: int) -> np.ndarray:
    h, w = img.shape
    if h < tam or w < tam:
        raise ValueError(f"imagen demasiado chica ({h}x{w}) para un recorte de {tam}")
    y0, x0 = (h - tam) // 2, (w - tam) // 2
    return img[y0 : y0 + tam, x0 : x0 + tam]


def medir_imagen(ruta: Path, rng: np.random.Generator) -> list[dict]:
    img = cargar_gris_lineal(ruta)
    x_verdad = recorte_central(img, TAM_CROP).astype(np.float64)

    recons, _ = reconstrucciones_bootstrap(x_verdad, SIGMA_PSF, FACTOR, SIGMA_RUIDO, K_BOOTSTRAP, rng)
    x_rl_media = recons.mean(axis=0)

    filas = []
    for y0, x0 in regiones(x_verdad.shape, TAM_REGION):
        region_media = x_rl_media[y0 : y0 + TAM_REGION, x0 : x0 + TAM_REGION]
        region_verdad = x_verdad[y0 : y0 + TAM_REGION, x0 : x0 + TAM_REGION]
        filas.append(
            {
                "archivo": ruta.name,
                "fila": y0 // TAM_REGION,
                "columna": x0 // TAM_REGION,
                "tau": tau_incertidumbre(recons, y0, x0, TAM_REGION),
                "error_rms": error_rms(region_media, region_verdad),
            }
        )
    return filas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fuente", type=Path, default=FUENTE_POR_DEFECTO)
    ap.add_argument("--salida", type=Path, default=Path("resultados_e2.csv"))
    args = ap.parse_args()

    rng = np.random.default_rng(SEMILLA)
    archivos = sorted(p for p in args.fuente.iterdir() if p.suffix.lower() in EXTENSIONES_VALIDAS)
    if not archivos:
        print(f"No se encontraron imágenes en {args.fuente}", file=sys.stderr)
        sys.exit(1)

    todas_las_filas = []
    for archivo in archivos:
        try:
            filas = medir_imagen(archivo, rng)
            todas_las_filas.extend(filas)
            print(f"  {archivo.name}: {len(filas)} regiones")
        except ValueError as e:
            print(f"  [omitida] {archivo.name}: {e}", file=sys.stderr)

    with open(args.salida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(todas_las_filas[0].keys()))
        w.writeheader()
        w.writerows(todas_las_filas)

    taus = np.array([r["tau"] for r in todas_las_filas])
    errores = np.array([r["error_rms"] for r in todas_las_filas])
    corr = correlacion_spearman(taus, errores)

    print(f"\n{len(todas_las_filas)} regiones medidas en {len(archivos)} imágenes. Resultados en {args.salida}")
    print(f"Correlación de Spearman τ vs error real: {corr:.3f}")
    print("VEREDICTO:", "🟢 VERDE" if corr >= CORRELACION_MINIMA_VERDE else "🔴 ROJO", f"(umbral: {CORRELACION_MINIMA_VERDE})")

    # estabilidad por imagen (METODO.md §3: "estable a través de tipos de contenido")
    print("\nPor imagen:")
    for archivo in archivos:
        filas_img = [r for r in todas_las_filas if r["archivo"] == archivo.name]
        if not filas_img:
            continue
        t = np.array([r["tau"] for r in filas_img])
        e = np.array([r["error_rms"] for r in filas_img])
        c = correlacion_spearman(t, e)
        print(f"  {archivo.name}: corr={c:+.3f}  (n={len(filas_img)})")


if __name__ == "__main__":
    main()
