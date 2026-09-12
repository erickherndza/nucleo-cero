# E0 — Resultados

**Estado: PENDIENTE.** Falta el corpus de 50 imágenes reales de clientes
(WhatsApp, web, escaneos antiguos, fotos de móvil, capturas) en
`experimentos/E0_margen/corpus/`.

Cómo correrlo una vez esté el corpus:

```
source .venv/bin/activate
python experimentos/E0_margen/medir.py experimentos/E0_margen/corpus/ --salida experimentos/E0_margen/resultados_e0.csv
```

## Criterio de la puerta (METODO.md §3)

- 🟢 Verde: ≥ 60% del corpus con corte suave y `s_libre ≥ 1.4`
- 🔴 Rojo: mayoría con muro abrupto → el producto es limpieza/restauración, no
  resolución (no cierra el proyecto, lo reposiciona)

## Resultado

_(completar a mano tras correr `medir.py` sobre el corpus real — no
interpretar a favor si es ambiguo)_

- Imágenes medidas:
- Fracción corte suave + s_libre ≥ 1.4:
- Veredicto:
