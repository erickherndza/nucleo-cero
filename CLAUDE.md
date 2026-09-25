# CLAUDE.md — nucleo-cero (mejora de fotos de WhatsApp sin inventar caras)

## Qué es esto ahora (actualizado 2026-09-24)

nucleo-cero pasó de ser el "Método de Recuperación Certificada" (capas 0-3,
sin priors generativos) a ser un pipeline de mejora de fotos que **sí** usa
modelos generativos preentrenados: Real-ESRGAN para el fondo y GFPGAN /
CodeFormer para caras, con verificación de identidad SFace para descartar
restauraciones que cambiaron demasiado a la persona.

El proyecto anterior (experimentos E0-E3, `METODO.md`, los avances 1.0-1.12,
`nucleo_cero.ipynb` original de 16MB) quedó archivado sin borrar en `old/`
— sigue ahí por si hace falta consultarlo, pero ya no es el método activo
ni las puertas E0-E3 aplican a lo que hay en la raíz.

## Archivos clave

- `nucleo_cero.ipynb` — notebook para **Google Colab** (Entorno de
  ejecución → Cambiar tipo → **GPU T4**). Es el pipeline en sí.
- `upscale.md` — misma fuente que el notebook, en Markdown con explicación
  de cada celda, tabla de resultados medidos, comparación con Krea 2
  Identity Edit y referencia completa de parámetros. Si el notebook y este
  archivo alguna vez difieren, `upscale.md` es más fácil de diffear/leer.
- `imagenes mejoradas/`, `imagenes-demo/` — fotos de prueba usadas para
  medir el pipeline (PSNR/SSIM/similitud de identidad).
- `old/` — proyecto clásico archivado (no activo).

## Cómo funciona el pipeline

```
foto WhatsApp ─┬─► Real-ESRGAN ×4 → reducir a tamaño final ─► FONDO (limpio, si usar_esrgan=True)
               ├─► bicúbica + enfoque ────────────────────► bajo cada CARA (fiel)
               └─► YuNet detecta caras ─► alinear 512×512 desde la original
                        └─► GFPGAN restaura ─► mezcla 50 % ─► ¿SFace ≥ 0.80?
                                                  sí → se pega · no → queda la fiel
```

Las caras se alinean y recortan siempre desde la foto **original**, nunca
desde la versión ya ampliada por ESRGAN (evita restaurar sobre información
ya inventada). Caras < 64 px no se restauran (muy poca información real
para verificar nada): quedan con la versión fiel bicúbica.

Existe además una alternativa **100% clásica** (sin IA, sin pesos
preentrenados): `deconvolucion_clasica()` en `nucleo.py` — bicúbica +
deconvolución Richardson-Lucy + unsharp mask. Se usa en la CELDA 4
("Reforzar") del notebook, sobre las mismas fotos ya subidas en la CELDA 3,
como alternativa de comparación cuando el resultado con IA no convence.

## Estructura del notebook (5 celdas, actualizada 2026-09-24)

1. **CELDA 1** — instala `spandrel`/`spandrel_extra_arches`, descarga los
   pesos (~450MB).
2. **CELDA 2** — escribe `nucleo.py` (`%%writefile`): todas las funciones,
   incluida `mejorar_foto()` (IA) y `deconvolucion_clasica()` (clásica).
3. **CELDA 3** — `files.upload()` → procesa con `mejorar_foto()` → guarda en
   `salidas_sueltas/`.
4. **CELDA 4** — reforzar: corre `deconvolucion_clasica()` sobre las mismas
   fotos de la Celda 3 (variable `subidas`), sin volver a subir nada.
5. **CELDA 5** — zip de `salidas_sueltas/` (versión IA + clásica) + descarga.

Las celdas viejas (lote desde carpeta de Drive, celda de auditoría con foto
de referencia, celda de limpieza de fotos demo) se eliminaron — ya no son
parte del flujo activo. Quedan como documentación de referencia después de
la Celda 2 las secciones "Referencia de parámetros", "Cómo leer el reporte
por cara", "Problemas comunes" y "Licencias".

## Invariantes verificados (no re-descubrir)

- **Verificación de identidad no es opcional**: cada cara restaurada se
  compara (SFace, similitud coseno) contra la cara original. Si la
  similitud cae bajo `umbral_identidad` (0.80 por defecto), se descarta la
  restauración y queda la versión fiel — no hay forma de que una cara
  "cambiada" pase sin que el reporte lo marque.
- El umbral de identidad es **binario** en la versión actual de
  `mejorar_foto()`: si `sim < umbral_identidad`, la restauración se
  descarta por completo (no existe una zona gris de mezcla parcial —
  `banda_transicion` que mencionaban avances previos ya no está en el
  código; no asumir que existe sin verificar primero).
- **`ancho` por defecto ahora es `None`, no `1024` fijo**: si la foto
  original ya supera 1024px de ancho, escala ×2 en vez de reducirla — antes
  del fix (2026-09-24) una foto de WhatsApp más grande de lo normal se
  reducía en vez de mejorarse. Ver `mejorar_foto()` en `nucleo.py`.
- **Real-ESRGAN puede posterizar/"pintar" el fondo** en fotos ya
  comprimidas por WhatsApp — confirmado en prueba real 2026-09-24 (ver
  hallazgo completo en `upscale.md`). Fix: `usar_esrgan=False` en
  `CONFIG_SUELTA` dentro de la Celda 3. No asumir que Real-ESRGAN siempre
  mejora el fondo sin verificar la imagen completa (el efecto no se nota
  en miniaturas, solo a resolución real).
- **`unsharp_mask` de scikit-image necesita `channel_axis=2`, no `-1`**: con
  eje negativo `slice_at_axis` corta filas en vez de canales y el resto del
  array queda sin inicializar → `deconvolucion_clasica()` devolvía una foto
  negra/basura (confirmado en skimage 0.25.2 y 0.26.0, fix 2026-09-25).
- **`deconvolucion_clasica()` v2 (2026-09-25)**: la versión anterior (RL 15
  iteraciones + unsharp 1.0 en RGB) distorsionaba: 24.31 dB contra 31.38 de
  una bicúbica pura (foto demo degradada ×1/1.6, JPEG q35). Tenía marco
  oscuro (RL sin relleno), halos y ruido JPEG amplificado. La v2 quita ruido
  (NL-means h=3) → bicúbica → RL 5 iteraciones con pad reflect + unsharp
  0.3, solo en luminancia: 31.53 dB / SSIM 0.8827, la única variante medida
  que supera a la bicúbica. Más iteraciones o más `amount` bajan el PSNR.
  `fondo_clasico=True` (en `CONFIG_SUELTA`) la usa como fondo de
  `mejorar_foto()` cuando `usar_esrgan=False`.
- **CodeFormer es NO comercial** (S-Lab License 1.0). El restaurador por
  defecto es GFPGAN (Apache 2.0) precisamente por esto — no cambiar el
  default a CodeFormer para clientes que pagan.
- Real-ESRGAN (BSD-3) y GFPGAN (Apache 2.0) sí permiten uso comercial;
  YuNet/SFace de OpenCV Zoo también (Apache 2.0 / MIT).
- Sin GPU el pipeline corre en CPU (~2 min/foto). Con GPU T4 de Colab
  (gratuita) debería bajar a segundos.
- **Lectura honesta de resultados** (medida, no asumida): en fidelidad de
  píxeles (PSNR) la bicúbica + enfoque sigue ganando siempre — la IA limpia
  ruido y artefactos, se ve mejor, pero no es más exacta. En caras grandes
  (>~100px) el pipeline conserva identidad igual o mejor que Photoshop y se
  ve más limpio. En caras pequeñas la IA cambia más la identidad: por eso
  existen `cara_minima` y `umbral_identidad`. Ver `upscale.md` para la
  tabla completa.
- No hay Docker ni entorno local fijo para este pipeline: corre en Colab.
  `.venv/` y `.pytest_cache/` en la raíz son restos del proyecto clásico
  archivado en `old/` y no hacen falta para este notebook.

## Las dos métricas que ya NO aplican aquí (sí aplicaban en `old/`)

`old/CLAUDE.md` documentaba consistencia + τ como certificado obligatorio
de todo resultado. Este pipeline no las produce: su única señal de
confianza es la similitud SFace por cara, comparada contra un umbral fijo.
No presentar salidas de este pipeline como si tuvieran las garantías del
método certificado anterior.

## Convenciones

Código y comentarios en español.
