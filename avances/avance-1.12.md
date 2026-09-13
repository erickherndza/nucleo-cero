# Avance 1.12 — leído el notebook completo de Colab; el fix real del efecto acuarela

**Fecha:** 2026-09-12

## Contexto

`SETUP.md` (compartido por el usuario) pedía mover 4 archivos de una
"bitácora" (`bitacora.py`, `registro.jsonl`, `integracion_colab.py`,
`README.md`) que no aparecían en ningún lado. Se intentó leer el notebook
de Colab directamente vía el conector de Google Drive (ya conectado, sin
pedir permiso adicional) — `get_file_metadata` funcionó, pero
`download_file_content` falló de forma persistente con "session expired"
(3 intentos, incluido con `exportMimeType` explícito) para el mime type
`application/vnd.google.colaboratory`. Es una limitación real del
conector para este tipo de archivo, no un problema de permisos.

**Solución**: el usuario subió el notebook completo (`nucleo_cero.ipynb`,
16.7MB, 15 celdas) directo desde Colab a `main` en GitHub ("Created using
Colab"). Se bajó con `git pull` y se procesó con Python (extrayendo solo
el código de las celdas, sin cargar las salidas/imágenes pesadas).

## Confirmado: la bitácora no existe en ningún lado

Se buscaron las 4 palabras clave (`bitacora`, `registro.jsonl`,
`integracion_colab`, `README`, `writefile`, `BITACORA`) en las 15 celdas
del notebook: **cero coincidencias**. `SETUP.md` describía un sistema que
se planeó pero nunca se llegó a construir/exportar — no algo que existía
y se perdió. Se descarta esa parte de `SETUP.md` hasta que exista de
verdad.

## El hallazgo real: qué arregló el efecto acuarela

Las 15 celdas muestran la evolución completa, de la más básica a la más
reciente. Se pudo rastrear el cambio exacto entre la versión que producía
acuarela y la que no:

| Celda | `LAMBDA_TV` | `MAX_LADO` | `epsilon` Charbonnier | Resultado |
|---|---|---|---|---|
| 10-11 | 8.0 | 512 | (por defecto, chico) | — (igual a lo que ya teníamos) |
| 12 | 8.0 | **2400** | (por defecto, chico) | Efecto acuarela (lo que reportó el usuario) |
| 13 | **6.0** | 2400 | **1e-3** | Arreglado |
| 14 ("v2.2", la más reciente) | 6.0 | 2400 | 1e-3 | Arreglado + puerta de fase (`UMBRAL_FASE=0.30`) |

**El fix no fue "cambiar de TV a Charbonnier-TV"** — eso ya lo teníamos
desde avance-1.8, con un epsilon tan chico (1e-8) que en la práctica se
comporta casi como TV/L1 puro. El fix real fue **subir epsilon a 1e-3**
(mil veces más grande) junto con bajar `LAMBDA_TV` de 8.0 a 6.0. Un
epsilon de Charbonnier grande extiende el régimen cuadrático (más
parecido a L2, que no favorece aplanar por tramos) sobre un rango más
ancho de gradientes típicos de textura real — eso es lo que evita el
"staircasing" que se ve como acuarela cuando el término de datos ya no
alcanza para restringir todos los píxeles nuevos de un lienzo grande.

## Cambios aplicados a nuestro código

`experimentos/E3_rafaga/nucleo_torch.py`: `tv()` ahora toma `epsilon` como
parámetro, con default `1e-3` (antes `1e-8`), documentado con el porqué y
la referencia a las celdas del notebook.

`experimentos/E3_rafaga/mvp.py`: `LAMBDA_TV` de `8.0` a `6.0`.

## Validado a nuestra escala (perfil rápido, no se pudo probar 2400px en CPU)

Misma foto de siempre (`IMG_20260425_190354.jpg`), mismo perfil rápido,
antes vs. después del cambio:

| Métrica | Antes (avance-1.11) | Después |
|---|---|---|
| τ | 0.1431 | **0.0692** |
| Ventaja PSNR (E1) | +2.26 dB | **+4.20 dB** |
| Ratio residuo/ruido | 1.00 | 0.99 |

Mejora en todos los números, no solo "ya no hace acuarela" — el cambio
parece una mejora general, no un parche específico para 2400px.

**No se pudo validar a 2400px localmente**: por el hallazgo de
avance-1.8 (~41x más lento en CPU que en GPU), una corrida a esa
resolución con el perfil `completo` tomaría probablemente 1-2 horas en
este Mac. Queda pendiente si el usuario quiere confirmarlo en Colab con
estos mismos valores ya integrados en nuestro código, o aceptar la
evidencia de la celda 14 (que sí se validó ahí, con la imagen que ya
revisamos) como suficiente.

## Estado

Repo actualizado y comiteado. El notebook `nucleo_cero.ipynb` (16.7MB)
quedó en la raíz del repo tras el pull — pendiente de decidir si conviene
moverlo a `experimentos/` o dejarlo fuera de git por su peso (ver
`.gitignore` — no se tocó todavía).

## Pendiente

1. Decidir qué hacer con `SETUP.md`: la parte de estructura de carpetas
   (`bitacora/`, `metodo/`, `tests/`, `ejemplo-minimo/`) y el `CLAUDE.md`
   nuevo siguen siendo relevantes, pero su descripción del estado del
   proyecto (E0/E2 "pendientes") no coincide con lo ya cerrado en esta
   sesión — aclarar antes de aplicarlo.
2. Decidir si `nucleo_cero.ipynb` se queda versionado en el repo (16.7MB)
   o se excluye por peso, igual que las imágenes reales.
3. Confirmar en Colab (GPU) que estos mismos parámetros, ya integrados en
   `nucleo_torch.py`/`mvp.py`, siguen sin dar acuarela a 2400px reales.
