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
foto WhatsApp ─┬─► Real-ESRGAN ×4 → reducir a 1024 px ──────► FONDO (limpio)
               ├─► bicúbica + enfoque ────────────────────► bajo cada CARA (fiel)
               └─► YuNet detecta caras ─► alinear 512×512 desde la original
                        └─► GFPGAN restaura ─► mezcla 50 % ─► ¿SFace ≥ 0.80?
                                                  sí → se pega · no → queda la fiel
```

Las caras se alinean y recortan siempre desde la foto **original**, nunca
desde la versión ya ampliada por ESRGAN (evita restaurar sobre información
ya inventada). Caras < 64 px no se restauran (muy poca información real
para verificar nada): quedan con la versión fiel bicúbica.

## Invariantes verificados (no re-descubrir)

- **Verificación de identidad no es opcional**: cada cara restaurada se
  compara (SFace, similitud coseno) contra la cara original. Si la
  similitud cae bajo `umbral_identidad` (0.80 por defecto), se descarta la
  restauración y queda la versión fiel — no hay forma de que una cara
  "cambiada" pase sin que el reporte lo marque.
- **`banda_transicion`** (0.10 por defecto) evita el salto binario feo en
  fotos grupales: en la franja justo bajo el umbral, la mezcla se reduce
  proporcionalmente en vez de aceptar/rechazar todo o nada. Con
  `banda_transicion=0` se recupera el comportamiento binario antiguo.
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
