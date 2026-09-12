"""
E1 — ¿La deconvolución alcanza el límite predicho?

Ver METODO.md §3 (E1) y §4 (Fase B, Fase D) para la especificación completa.

Modelo directo simulado: y = D( H * x ) + ruido, con H (PSF gaussiana) y
D (decimación por promedio, factor entero) COMPLETAMENTE CONOCIDOS — a
diferencia de E0, aquí sí hay una verdad (`x`) contra la que comparar.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

# --- E/S y conversión a luz lineal (duplicado deliberado de E0_margen/medir.py:
#     cada experimento es independiente y puede ser código sucio, CLAUDE.md) ---


def srgb_a_lineal(canal: np.ndarray) -> np.ndarray:
    a = 0.055
    lin = np.where(canal <= 0.04045, canal / 12.92, ((canal + a) / (1 + a)) ** 2.4)
    return lin.astype(np.float32)


def cargar_gris_lineal(ruta) -> np.ndarray:
    img = Image.open(ruta).convert("L")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return srgb_a_lineal(arr)


def recorte_mas_nitido(img: np.ndarray, tam: int = 512) -> np.ndarray:
    """Recorre la imagen en una rejilla de recortes de tam×tam y devuelve el
    de mayor varianza de Laplaciano (más detalle real, evita cielos/paredes
    lisas que no sirven para probar deconvolución)."""
    h, w = img.shape
    if h < tam or w < tam:
        raise ValueError(f"imagen demasiado chica ({h}x{w}) para un recorte de {tam}")
    lap_kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)

    mejor_var, mejor_recorte = -1.0, None
    paso = tam // 2
    for y0 in range(0, h - tam + 1, paso):
        for x0 in range(0, w - tam + 1, paso):
            recorte = img[y0 : y0 + tam, x0 : x0 + tam]
            lap = convolucionar(recorte, lap_kernel)
            var = float(lap.var())
            if var > mejor_var:
                mejor_var, mejor_recorte = var, recorte
    return mejor_recorte


# --- Operadores del modelo directo ---


def kernel_gaussiano(sigma: float) -> np.ndarray:
    radio = max(1, int(np.ceil(3 * sigma)))
    eje = np.arange(-radio, radio + 1)
    xx, yy = np.meshgrid(eje, eje)
    k = np.exp(-(xx**2 + yy**2) / (2 * sigma**2))
    return (k / k.sum()).astype(np.float64)


def convolucionar(img: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Convolución 'same' vía FFT con padding por reflexión (evita el
    envolvimiento circular y el oscurecimiento de bordes de un padding con
    ceros)."""
    kh, kw = kernel.shape
    ph, pw = kh // 2, kw // 2
    img_pad = np.pad(img, ((ph, ph), (pw, pw)), mode="reflect")
    H, W = img_pad.shape
    kernel_pad = np.zeros((H, W), dtype=np.float64)
    kernel_pad[:kh, :kw] = kernel
    kernel_pad = np.roll(kernel_pad, (-ph, -pw), axis=(0, 1))
    resultado = np.fft.ifft2(np.fft.fft2(img_pad) * np.fft.fft2(kernel_pad)).real
    return resultado[ph : ph + img.shape[0], pw : pw + img.shape[1]]


def decimar_promedio(img: np.ndarray, factor: int) -> np.ndarray:
    h, w = img.shape
    h2, w2 = h // factor, w // factor
    recorte = img[: h2 * factor, : w2 * factor]
    return recorte.reshape(h2, factor, w2, factor).mean(axis=(1, 3))


def adjunto_decimar_promedio(z: np.ndarray, factor: int, forma_hr: tuple[int, int]) -> np.ndarray:
    """Adjunto de decimar_promedio: D(u) = promedio por bloque (peso 1/factor²
    por píxel de u), así que D^T(z) reparte cada z entre su bloque, con el
    mismo peso 1/factor² (no 1, para que <Du,z> == <u, D^T z>)."""
    up = np.repeat(np.repeat(z, factor, axis=0), factor, axis=1) / (factor**2)
    out = np.zeros(forma_hr, dtype=z.dtype)
    out[: up.shape[0], : up.shape[1]] = up
    return out


def degradar(x_verdad: np.ndarray, sigma_psf: float, factor: int, sigma_ruido: float, rng: np.random.Generator):
    kernel = kernel_gaussiano(sigma_psf)
    borrosa = convolucionar(x_verdad, kernel)
    y = decimar_promedio(borrosa, factor)
    y = y + rng.normal(0, sigma_ruido, size=y.shape)
    return y.astype(np.float64), kernel


# --- Reconstrucción ---


def bicubica_hasta(y: np.ndarray, forma_hr: tuple[int, int]) -> np.ndarray:
    im = Image.fromarray(y.astype(np.float32), mode="F")
    im = im.resize((forma_hr[1], forma_hr[0]), Image.BICUBIC)
    return np.asarray(im, dtype=np.float64)


def richardson_lucy_sr(
    y: np.ndarray,
    kernel: np.ndarray,
    factor: int,
    forma_hr: tuple[int, int],
    sigma_ruido: float,
    iteraciones_max: int = 30,
    margen_discrepancia: float = 1.0,
) -> tuple[np.ndarray, int]:
    """RL generalizado para el operador directo A = D_factor ∘ H_kernel.

    Parada por PRINCIPIO DE DISCREPANCIA (Morozov): se detiene en cuanto el
    residuo ‖A x_k − y‖² baja hasta el nivel del ruido conocido, σ_n².

    No se usa "para cuando el residuo deja de bajar" — se probó y falla: el
    residuo baja monótonamente incluso mientras el algoritmo ya está
    sobreajustando al ruido (ver test_nucleo.py y avance correspondiente).
    Sin esta parada, RL empeora con cada iteración extra pasado el óptimo,
    exactamente lo que CLAUDE.md advierte ("más iteraciones no es más
    nitidez, es más artefacto")."""
    x = bicubica_hasta(y, forma_hr)
    x = np.clip(x, 1e-6, None)

    unos = np.ones_like(y)
    normalizador = np.maximum(convolucionar(adjunto_decimar_promedio(unos, factor, forma_hr), kernel), 1e-6)
    piso_discrepancia = margen_discrepancia * sigma_ruido**2

    iteraciones_hechas = 0
    for i in range(iteraciones_max):
        prediccion = np.maximum(decimar_promedio(convolucionar(x, kernel), factor), 1e-6)
        razon = y / prediccion
        correccion = convolucionar(adjunto_decimar_promedio(razon, factor, forma_hr), kernel)
        x = x * correccion / normalizador
        x = np.clip(x, 0.0, None)
        iteraciones_hechas = i + 1

        residuo = float(np.mean((prediccion - y) ** 2))
        if residuo <= piso_discrepancia:
            break

    return x, iteraciones_hechas


# --- Métricas ---


def psnr(a: np.ndarray, b: np.ndarray, max_i: float = 1.0) -> float:
    mse = float(np.mean((a - b) ** 2))
    if mse <= 0:
        return float("inf")
    return 10.0 * np.log10(max_i**2 / mse)


_VENTANA_SSIM = kernel_gaussiano(1.5)  # 11x11 aprox, estándar para SSIM


def ssim(a: np.ndarray, b: np.ndarray, L: float = 1.0) -> float:
    C1, C2 = (0.01 * L) ** 2, (0.03 * L) ** 2
    mu_a = convolucionar(a, _VENTANA_SSIM)
    mu_b = convolucionar(b, _VENTANA_SSIM)
    var_a = convolucionar(a * a, _VENTANA_SSIM) - mu_a**2
    var_b = convolucionar(b * b, _VENTANA_SSIM) - mu_b**2
    cov_ab = convolucionar(a * b, _VENTANA_SSIM) - mu_a * mu_b
    num = (2 * mu_a * mu_b + C1) * (2 * cov_ab + C2)
    den = (mu_a**2 + mu_b**2 + C1) * (var_a + var_b + C2)
    return float(np.mean(num / den))


def espectro_radial(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Densidad espectral de potencia (PSD) promediada radialmente.

    Se divide por H·W (Parseval) para que quede en las mismas unidades que
    una varianza de intensidad — así se puede comparar directamente contra
    σ_ruido² sin factores de escala escondidos. Sin este /()H·W), la
    "potencia" cruda queda ~H·W veces más grande que la varianza real, y
    cualquier comparación contra un piso de ruido absoluto sale mal por ese
    factor (bug real encontrado al validar f_max_teorico/banda_recuperada,
    ver avance correspondiente)."""
    h, w = img.shape
    f = np.fft.fftshift(np.fft.fft2(img))
    densidad = (np.abs(f) ** 2) / (h * w)
    cy, cx = h // 2, w // 2
    y, x = np.indices((h, w))
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2).astype(np.int64)
    r_nyquist = min(cx, cy)
    suma = np.bincount(r.ravel(), densidad.ravel())
    cuenta = np.bincount(r.ravel())
    perfil = suma[: r_nyquist + 1] / np.maximum(cuenta[: r_nyquist + 1], 1)
    freqs = np.arange(len(perfil)) / r_nyquist
    return freqs, perfil


def f_max_teorico(freqs: np.ndarray, S_verdad: np.ndarray, sigma_psf: float, sigma_ruido: float) -> float:
    """Frecuencia (normalizada al Nyquist del recorte HR) donde la señal
    borrosa predicha, |H(f)|²·S(f), cae al nivel del ruido añadido, σ_n².

    Nota de método: METODO.md §4 escribe el criterio como '|H(f)| = σ_n'
    sin más contexto de unidades. Aquí se usa la forma con el espectro real
    de la verdad, S(f), porque comparar un OTF adimensional directo contra
    una desviación estándar de intensidad mezcla unidades; con S(f) medido
    de la propia imagen la comparación de potencias sí es consistente.
    """
    H2 = np.exp(-(np.pi**2) * (sigma_psf**2) * (freqs**2))
    señal_predicha = H2 * S_verdad
    piso = sigma_ruido**2
    por_debajo = señal_predicha <= piso
    if not por_debajo.any():
        return float(freqs[-1])
    return float(freqs[np.argmax(por_debajo)])


def banda_recuperada(x_estimado: np.ndarray, x_verdad: np.ndarray) -> float:
    """Frecuencia (normalizada) hasta la que el error de reconstrucción se
    mantiene por debajo de la potencia de la SEÑAL VERDADERA en esa
    frecuencia (criterio SNR ≥ 1) — más allá de eso, se está reconstruyendo
    más ruido que señal.

    Nota de método: la primera versión comparaba el error contra el piso de
    ruido crudo σ_n² (la lectura literal de METODO.md §4). Con datos reales
    eso daba 0% en las 10 imágenes de control, sin excepción — no por un
    hallazgo real, sino porque cualquier deconvolución amplifica ruido en el
    dominio de la imagen (el operador invertido tiene ganancia > 1 donde
    |H(f)| es chico), así que ningún método real baja el error de
    reconstrucción hasta el nivel del ruido crudo del sensor, en ninguna
    frecuencia. Comparar contra la potencia de la señal misma (no contra el
    ruido) es el criterio de ancho de banda estándar en recuperación de
    señales, y sí distingue casos reales entre sí."""
    freqs, S_verdad = espectro_radial(x_verdad)
    _, error_radial = espectro_radial(x_estimado - x_verdad)
    por_encima = error_radial >= S_verdad
    if not por_encima.any():
        return float(freqs[-1])
    return float(freqs[np.argmax(por_encima)])
