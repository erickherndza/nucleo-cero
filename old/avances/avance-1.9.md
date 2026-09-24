# Avance 1.9 — MVP del pipeline E1+E3+certificado, probado sobre fotos reales

**Fecha:** 2026-09-12

## Qué se construyó

A partir del script adaptado en avance-1.8, se separó en:

- **`experimentos/E3_rafaga/nucleo_torch.py`** — librería pura (color,
  operador directo, ruido, alineación piramidal, diagnóstico de fase,
  pesos robustos Tukey, TV, reconstrucción, certificado, métricas, carga
  de imagen). Sin CLI, sin configuración fija — todo parametrizado.
- **`experimentos/E3_rafaga/mvp.py`** — CLI con dos modos y dos perfiles:
  - `validacion` / `produccion` (igual que el script original)
  - `--perfil rapido` (nuevo) / `--perfil completo` (los parámetros
    originales)

## Por qué hacía falta el perfil "rápido"

El perfil `completo` (K=6 frames, 300 iteraciones, recorte 512px) tomó
663.7s (~11 min) en el Mac sin GPU (avance-1.8). Para poder iterar y
probar el MVP varias veces en esta sesión hacía falta algo más rápido:
`rapido` usa K=4, 100 iteraciones, recorte 256px, y reduce a un 35% las
iteraciones de la pirámide de alineación de pose.

## Prueba de punta a punta

Corrido en modo validación sobre una foto real distinta de las ya usadas
en E1/E2 (`IMG_20260425_193144.jpg`), perfil rápido:

```
Verdad de referencia: 256x144 · Ráfaga sintética: 4 frames a 128x72
E3: error medio de alineación 0.014 px LR  ->  🟢 VERDE
Diversidad de fase: x=0.36, y=0.69  ->  repartidas
Certificado: ratio=1.00 ✓ | tau=0.1431 -> nivel "Comercial"
E1: PSNR bicúbica 28.40dB | método 30.66dB | ventaja +2.26dB  ->  🟢 VERDE
    SSIM bicúbica 0.8000  | método 0.8472  | ventaja +0.0472
Tiempo total: 44.9s (perfil rápido, CPU)
```

**Ambas puertas siguen en verde incluso con el perfil reducido**, aunque
con menos margen que el perfil completo (+2.26dB vs +3.81dB) — esperable
con menos frames y menos iteraciones, y justo el margen que se pierde al
recortar para velocidad.

Salida generada por el MVP (`experimentos/E3_rafaga/salida/`, no
versionada — regenerable):
- `..._comparacion.png` — bicúbica / método / verdad, lado a lado
- `..._reconstruida.png` — solo la imagen final, para entrega
- `..._informe.md` — el certificado completo en texto

Inspección visual de la comparación: el resultado del método muestra
textura reconocible en la ropa y bordes más definidos en la cara y el
fondo (pared de ladrillo) frente a la bicúbica, visualmente cercano a la
verdad de referencia — consistente con el número de PSNR/SSIM.

## Estado

MVP funcional, probado en modo validación con dos perfiles y dos fotos
reales distintas. **No probado todavía en modo producción** (requiere una
ráfaga real de al menos 2 fotos de la misma escena estática, que no
existe todavía en el corpus del usuario — las 10 fotos de
`E1_deconvolucion/fuente/` son de escenas distintas, no una ráfaga).

## Pendiente

- Conseguir o capturar una ráfaga real (2+ fotos de la misma escena
  estática, con pequeño temblor de mano natural) para probar el modo
  producción de verdad — es el caso de uso real, no sintético.
- Decidir si este pipeline (PyTorch, capa 3/TV, τ por diferencia con/sin
  regularización) reemplaza o complementa el camino numpy-puro construido
  en E0-E2 — son dos bases de código distintas ahora mismo, con τ definido
  de forma distinta en cada una.
- El tiempo en CPU sigue siendo alto incluso en el perfil rápido para un
  factor 2x pequeño (256px de lado); una foto real de cliente (varios
  cientos o miles de píxeles más grande) tomaría bastante más — pendiente
  de medir con una imagen a tamaño más realista antes de considerar esto
  utilizable en producción real en el Mac.
