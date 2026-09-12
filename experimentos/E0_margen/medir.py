"""
E0 — ¿Existe margen real en las imágenes de clientes?

Ver METODO.md §3 (E0) y §4 (Fase A, Fase B) para la especificación completa.

Uso:
    python medir.py corpus/ --salida resultados.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from PIL import Image

EXTENSIONES_VALIDAS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

# Umbrales del criterio verde de E0 (METODO.md §3)
S_LIBRE_MINIMO = 1.4
FRACCION_VERDE_MINIMA = 0.60


@dataclass
class MedicionE0:
    archivo: str
    f_eff_sobre_f_n: float
    tipo_corte: str
    s_libre: float | None  # solo tiene sentido si tipo_corte == "suave"


def srgb_a_lineal(canal: np.ndarray) -> np.ndarray:
    """Deshace la codificación gamma sRGB. Necesario porque el espectro de
    una imagen en gamma mezcla frecuencias que no están ahí (CLAUDE.md)."""
    a = 0.055
    lin = np.where(canal <= 0.04045, canal / 12.92, ((canal + a) / (1 + a)) ** 2.4)
    return lin.astype(np.float32)


def cargar_gris_lineal(ruta: Path) -> np.ndarray:
    try:
        img = Image.open(ruta).convert("L")
    except Exception as e:
        raise ValueError(f"no se pudo leer la imagen: {ruta} ({e})") from e
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return srgb_a_lineal(arr)


def espectro_radial(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Espectro de potencia promediado radialmente.

    Devuelve (freqs, potencia) con freqs normalizada en [0, 1], donde
    1.0 == frecuencia de Nyquist del eje corto de la imagen.
    """
    h, w = img.shape
    f = np.fft.fftshift(np.fft.fft2(img))
    potencia = np.abs(f) ** 2

    cy, cx = h // 2, w // 2
    y, x = np.indices((h, w))
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2).astype(np.int64)
    r_nyquist = min(cx, cy)

    suma = np.bincount(r.ravel(), potencia.ravel())
    cuenta = np.bincount(r.ravel())
    perfil = suma[: r_nyquist + 1] / np.maximum(cuenta[: r_nyquist + 1], 1)
    freqs = np.arange(len(perfil)) / r_nyquist
    return freqs, perfil


def _db(potencia: np.ndarray) -> np.ndarray:
    return 10.0 * np.log10(potencia + 1e-12)


def _suavizar(dB: np.ndarray, ventana: int) -> np.ndarray:
    ventana = max(3, ventana | 1)  # impar, mínimo 3
    kernel = np.ones(ventana) / ventana
    # padding por repetición de borde: con mode="same" el cero implícito en
    # los extremos simula una caída falsa en f=0 que no existe en la señal.
    relleno = ventana // 2
    dB_relleno = np.pad(dB, relleno, mode="edge")
    return np.convolve(dB_relleno, kernel, mode="valid")


BANDA_REFERENCIA = (0.05, 0.25)
UMBRAL_DEPARTURE_DB = -3.0  # cuánto debe caer bajo la tendencia natural para contar como "corte extra"
UMBRAL_PISO_DB = 3.0  # margen sobre el piso medido para decir "llegó al piso"
ANCHO_SUAVE_MIN = 0.12
ANCHO_MURO_MAX = 0.04


def _tendencia_natural(freqs: np.ndarray, dB: np.ndarray, banda=BANDA_REFERENCIA) -> np.ndarray:
    """Ajusta dB ~ a + b·log10(f) en una banda de referencia de baja
    frecuencia, asumida libre de cualquier corte adicional — solo la caída
    ~1/f^n que tiene CUALQUIER imagen natural. Devuelve esa tendencia
    extrapolada a todo el rango de frecuencias.

    Sin esto, comparar niveles absolutos de dB confunde la caída natural
    (que por sí sola ya abarca casi todo el rango DC→Nyquist) con un corte
    adicional real: toda imagen "parece" tener una transición ancha si el
    punto de referencia es el nivel en continua (ver avance-1.1.md)."""
    mask = (freqs >= banda[0]) & (freqs <= banda[1])
    if mask.sum() < 5:
        mask = freqs > 0
    logf_banda = np.log10(freqs[mask])
    b, a = np.polyfit(logf_banda, dB[mask], 1)
    freqs_seguras = np.where(freqs > 0, freqs, freqs[freqs > 0].min())
    return a + b * np.log10(freqs_seguras)


def clasificar_corte(freqs: np.ndarray, potencia: np.ndarray) -> tuple[float, str]:
    """Clasifica la forma del corte espectral (METODO.md §3, tabla E0).

    Devuelve (f_eff / f_N, tipo) con tipo en {"suave", "muro", "plegado"}.
    """
    dB = _db(potencia)
    dB_suave = _suavizar(dB, ventana=max(3, len(dB) // 40))
    tendencia = _tendencia_natural(freqs, dB_suave)
    residuo = dB_suave - tendencia  # ~0 mientras sigue la caída natural

    alta = (freqs >= 0.85) & (freqs <= 1.0)
    piso_dB = np.median(dB_suave[alta]) if alta.any() else dB_suave[-1]

    zona = np.where(freqs > BANDA_REFERENCIA[1])[0]
    if len(zona) == 0:
        zona = np.arange(len(freqs))

    en_piso = dB_suave[zona] <= piso_dB + UMBRAL_PISO_DB
    idx_piso = zona[np.argmax(en_piso)] if en_piso.any() else zona[-1]
    f_eff = freqs[idx_piso]

    se_aparta = residuo[zona] <= UMBRAL_DEPARTURE_DB
    if se_aparta.any():
        idx_departure = zona[np.argmax(se_aparta)]
        f_departure = freqs[idx_departure]
        ancho_transicion = f_eff - f_departure
        if ancho_transicion >= ANCHO_SUAVE_MIN:
            tipo = "suave"
        elif ancho_transicion <= ANCHO_MURO_MAX:
            tipo = "muro"
        else:
            tipo = "ambiguo"
    else:
        # nunca se aparta de su propia tendencia natural antes de llegar al
        # piso: no hay corte adicional detectable, solo la caída natural.
        tipo = "suave"

    # Energía plegada: repunte cerca de Nyquist por encima del mínimo previo.
    # Se evalúa aparte porque es una firma distinta (no monótona), no un
    # caso más de ancho de transición.
    zona_borde = freqs >= 0.95
    zona_previa = (freqs >= 0.70) & (freqs < 0.95)
    if zona_borde.any() and zona_previa.any():
        if np.max(dB_suave[zona_borde]) > np.min(dB_suave[zona_previa]) + 2.0:
            tipo = "plegado"

    return float(f_eff), tipo


def medir_imagen(ruta: Path) -> MedicionE0:
    img = cargar_gris_lineal(ruta)
    freqs, potencia = espectro_radial(img)
    f_eff_norm, tipo = clasificar_corte(freqs, potencia)
    s_libre = (1.0 / f_eff_norm) if (tipo == "suave" and f_eff_norm > 0) else None
    return MedicionE0(str(ruta.name), f_eff_norm, tipo, s_libre)


def medir_corpus(directorio: Path) -> list[MedicionE0]:
    archivos = sorted(p for p in directorio.iterdir() if p.suffix.lower() in EXTENSIONES_VALIDAS)
    resultados = []
    for archivo in archivos:
        try:
            resultados.append(medir_imagen(archivo))
        except ValueError as e:
            print(f"  [omitida] {e}", file=sys.stderr)
    return resultados


def veredicto(mediciones: list[MedicionE0]) -> tuple[float, bool]:
    if not mediciones:
        return 0.0, False
    ok = sum(1 for m in mediciones if m.tipo_corte == "suave" and (m.s_libre or 0) >= S_LIBRE_MINIMO)
    fraccion = ok / len(mediciones)
    return fraccion, fraccion >= FRACCION_VERDE_MINIMA


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("corpus", type=Path, help="directorio con las imágenes del corpus")
    ap.add_argument("--salida", type=Path, default=Path("resultados_e0.csv"))
    args = ap.parse_args()

    mediciones = medir_corpus(args.corpus)
    if not mediciones:
        print(f"No se encontraron imágenes válidas en {args.corpus}", file=sys.stderr)
        sys.exit(1)

    with open(args.salida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(mediciones[0]).keys()))
        w.writeheader()
        for m in mediciones:
            w.writerow(asdict(m))

    fraccion, es_verde = veredicto(mediciones)
    print(f"\n{len(mediciones)} imágenes medidas. Resultados en {args.salida}")
    print(f"Fracción con corte suave y s_libre >= {S_LIBRE_MINIMO}: {fraccion:.0%}")
    print("VEREDICTO:", "🟢 VERDE" if es_verde else "🔴 ROJO", f"(umbral: {FRACCION_VERDE_MINIMA:.0%})")


if __name__ == "__main__":
    main()
