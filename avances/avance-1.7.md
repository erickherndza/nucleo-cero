# Avance 1.7 — checkpoint y plan: primer pipeline integrado

**Fecha:** 2026-09-12
**Estado:** planificación — retomar cuando se restablezca el límite (≈1h).

## Resumen de dónde quedó el proyecto

| Puerta | Estado | Resultado |
|---|---|---|
| E0 — ¿hay margen real? | 🔴 Cerrada | 27% del corpus con corte suave + s_libre≥1.4 (umbral 60%). Producto con más fundamento: limpieza/restauración, no resolución. No cierra el proyecto (METODO.md §8). |
| E1 — ¿la deconvolución llega al límite? | 🟡 Parcial | Ventaja sobre bicúbica confirmada y validada (+3.47dB, 80% de imágenes ≥2dB). Ancho de banda vs. límite teórico sin resolver (da >100%, `f_max_teorico` mal calibrado — avance-1.3). Solo probado con PSF **conocida**, falta PSF **estimada** (E1-b). |
| E2 — ¿el certificado predice el error? | 🟢 Cerrada | τ por sensibilidad al ruido (bootstrap) vs. error relativo: +0.82 de correlación, 9/10 imágenes ≥0.6. Esta es la puerta que más importa (§8) y quedó en verde. |
| E3 — ráfaga | No iniciada | |
| E4 — recurrencia interna | No iniciada | |

Todo el código y los avances están comiteados hasta `avance-1.6`
(`git log --oneline` en la raíz del repo).

## Objetivo de la próxima sesión

Construir un **primer pipeline integrado** (diagnóstico + reconstrucción +
certificado) sobre 1-2 fotos reales, para tener algo end-to-end que se
pueda ver y evaluar visualmente — no para cerrar E5 formalmente (METODO.md
§3 dice que E5 va "solo después de que E0–E3 estén en verde", y E0 está en
rojo y E3 no se ha corrido). Esto es un **prototipo de prueba**, no la
integración final: vive en `experimentos/`, no en `metodo/`.

## Alcance explícito de este primer test (limitaciones a propósito)

- **PSF asumida, no estimada.** E1-b (estimación por ESF) no se construyó
  todavía — se usará un valor fijo razonable (o el mismo `σ_psf=1.2` usado
  en los experimentos), documentando esto como limitación conocida.
- **Sin capa 3 / TV.** Solo deconvolución (capa 1, Richardson-Lucy con
  parada por discrepancia).
- **Sin ráfaga ni recurrencia** (E3, E4 no corridas).
- Sobre una foto real de baja calidad (no una degradación sintética con
  verdad conocida) — a diferencia de E1/E2, aquí no hay verdad contra qué
  comparar; el certificado es lo único que se puede ofrecer como garantía.

## Qué construir

Nueva carpeta `experimentos/E5_pipeline_prueba/`:

1. **`pipeline.py`** — función end-to-end, reutilizando lo ya validado:
   - Diagnóstico rápido: reutilizar `E0_margen/medir.py` (`espectro_radial`,
     `clasificar_corte`) sobre la imagen de entrada real.
   - Reconstrucción: `E1_deconvolucion/nucleo.py` (`richardson_lucy_sr`),
     con PSF asumida — aquí NO hay degradación sintética que aplicar, la
     imagen YA es la entrada real de baja calidad. Ojo: el modelo directo
     de E1 asume que SE CONOCE el factor de escalado deseado; para esta
     prueba, fijar un factor (por ejemplo 2×) como el "cuánto pedimos
     agrandar", no como algo medido.
   - Certificado: `E2_calibracion/nucleo.py` (`reconstrucciones_bootstrap`,
     `tau_incertidumbre`) — K=4 reconstrucciones con distintas
     realizaciones de ruido SINTÉTICO ENCIMA de la imagen real (para
     simular sensibilidad, ya que no hay múltiples capturas reales).
   - Salida: imagen reconstruida (PNG) + mapa de confianza por región
     (verde/ámbar/rojo, Fase E de METODO.md §4) + informe en texto plano
     con los números clave (f_eff, tipo de corte, τ medio, regiones de
     baja confianza).

2. **`correr_pipeline.py`** — CLI: `python correr_pipeline.py <imagen>
   --salida <carpeta>`.

3. **Prueba manual**: correr sobre 1-2 fotos del corpus de E0 o de la
   fuente de E1 (elegir una representativa del 27% "suave" y, si se
   quiere comparar, una del "muro" para ver cómo se comporta cuando no hay
   margen real).

## Qué NO resuelve este avance

No cierra E1 (banda teórica), no corre E1-b (PSF estimada), no corre E3/E4,
no promueve nada a `metodo/`. Es deliberadamente un prototipo desechable
para ver el pipeline funcionando de punta a punta antes de invertir en
integrarlo bien.

## Retomar

Cuando se restablezca el límite: leer este archivo, confirmar el alcance
con el usuario si algo cambió, y empezar por `experimentos/E5_pipeline_prueba/pipeline.py`.
