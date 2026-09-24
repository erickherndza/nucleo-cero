# Avance 1.11 — puerta preventiva de fase (v1.0 del usuario) + proyecto renombrado

**Fecha:** 2026-09-12

## 1. Retroalimentación del "Certificado Técnico v1.0" (Colab)

El usuario compartió una especificación consolidada de su trabajo en Colab
tras el hallazgo del efecto acuarela (avance previo, MAX_LADO=2400) y una
imagen de validación (`~/Desktop/imagen_reconstruida_validacion.png`,
1352×2400) que se revisó: sin efecto acuarela, textura de piel y tela
conservada, sin artefactos de "pintura al óleo".

**Verificación antes de portar nada**: se revisó `nucleo_torch.py` — la
función `tv()` que ya teníamos (desde avance-1.8, del primer script
compartido) **ya era Charbonnier-TV** (`sqrt(dx²+eps)`, no `abs(dx)`), así
que el "Fase 3" de la v1.0 del usuario (transición a Charbonnier-TV) ya
estaba incluido desde el principio en lo que integramos — coincide con que
nunca vimos el efecto acuarela en nuestras pruebas de avance-1.8/1.9/1.10.

**Lo que sí era nuevo y se portó**: la **puerta de fase preventiva**. La
v1.0 del usuario aborta la reconstrucción ANTES de optimizar si
`min(diversidad_de_fase) < 0.30`, en vez de solo advertir y seguir (que es
lo que hacía nuestro `mvp.py`). Se corrigió esto en
`experimentos/E3_rafaga/mvp.py`:

- Nueva constante `UMBRAL_DIVERSIDAD_FASE = 0.30` (antes: 0.35, solo de
  advertencia, sin abortar).
- Nueva función `_abortar_por_fase()`: si la ráfaga no pasa el umbral, no
  se ejecuta ninguna reconstrucción — se escribe un informe de rechazo
  explicando por qué (METODO.md §3, E3: "si todos los frames caen en la
  misma fase... hay que decirlo").

**Validado:**
- Caso sintético con fase agrupada (0.15, 0.20) → aborta correctamente,
  sin gastar cómputo, informe de rechazo generado.
- La ráfaga real de avance-1.10 (fase 0.74/0.48, bien repartida) → sigue
  procesándose normal, no la bloquea el nuevo umbral (su problema era
  inconsistencia del modelo, no falta de diversidad de fase — hallazgos
  distintos, ambos reales).

## 2. Hallazgo no planeado: el proyecto fue renombrado en disco

A media sesión, el directorio del proyecto pasó de
`/Users/erickhernandez/proyectos/UppImagenScale` a
`/Users/erickhernandez/proyectos/nucleo-cero` (mismo `.git`, mismo
historial de commits — un rename, no una copia ni una pérdida de datos).

**Efecto colateral**: los scripts `activate` de AMBOS venvs
(`.venv/` en la raíz y `experimentos/E3_rafaga/.venv312/`) tienen la ruta
absoluta VIEJA grabada dentro (`venv` de Python la fija al crear el
entorno, no la recalcula). Tras el rename, `source .../activate` seguía
"funcionando" sin error pero dejaba `PATH` apuntando a un directorio que
ya no existe, así que `python`/`pip` dejaban de encontrarse
(`command not found`).

**Diagnóstico**: los símlinks del propio intérprete
(`.venv312/bin/python3.12 -> /usr/local/opt/python@3.12/bin/python3.12`)
apuntan a la instalación del sistema, que no se movió — esos siguen
funcionando bien. El problema es solo el `PATH` que arma `activate`.

**Solución adoptada**: invocar el binario del venv **directamente por su
ruta**, sin pasar por `source activate`:

```bash
experimentos/E3_rafaga/.venv312/bin/python3.12 experimentos/E3_rafaga/mvp.py ...
.venv/bin/python3.14 experimentos/E0_margen/medir.py ...
```

Esto funciona igual de bien (Python detecta el venv por la ubicación real
del ejecutable invocado, no por el `PATH`) y es más robusto a futuros
renames. No hizo falta recrear ningún venv.

## Nota sobre memoria entre sesiones

El sistema de memoria de este asistente guarda notas de proyecto en una
carpeta ligada a la ruta del repositorio. Como la ruta cambió
(`UppImagenScale` → `nucleo-cero`), una sesión nueva que arranque desde
`nucleo-cero` podría no ver automáticamente memorias guardadas bajo la
ruta vieja (por ejemplo, la decisión de no usar modelos generativos). No
es un problema de datos perdidos — está todo en `CLAUDE.md` y en este
mismo repositorio — pero vale la pena saberlo si una sesión futura parece
"no recordar" contexto de decisiones tomadas bajo el nombre anterior.

## Estado

`mvp.py` con puerta preventiva de fase, probado en ambos casos (rechazo y
paso). Venvs verificados y funcionando desde la nueva ruta.
