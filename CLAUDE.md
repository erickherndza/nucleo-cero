# CLAUDE.md — Método de Recuperación Certificada

## Regla no negociable
Prohibido cualquier prior generativo aprendido (GAN, difusión, redes que
sinteticen píxeles). El núcleo se rellena por capas 0-3 en orden de
verificabilidad. No existe capa 4.

## Esto es un programa experimental
Cada etapa tiene una puerta con criterio verde y criterio rojo, definidos en
METODO.md §3. NO avanzar de etapa con la puerta en rojo. Si un resultado es
ambiguo, decirlo en vez de interpretarlo a favor.

Código de experimentos/ puede ser sucio y directo. Código de metodo/ no: ahí
solo entra lo que ya pasó su puerta.

## Invariantes técnicos
- Todo el cómputo en LUZ LINEAL (deshacer gamma al cargar, reaplicar al guardar)
- RAW sin auto-brillo, sin reducción de ruido, sin nitidez, gamma lineal
- Procesamiento por tiles: < 400 MB de RAM con cualquier tamaño de entrada
- float32 para cómputo, 16 bits para guardar
- Sin GPU (MacBook Pro 2015 Intel). Sin Docker para el pipeline.
- Código y comentarios en español

## Las dos métricas acompañan toda salida
consistencia: ‖DHx̂ − y‖ ≈ ‖n‖
tau:          ‖x_núcleo‖ / ‖x_rango‖
La consistencia sola NO basta: un generativo proyectado la aprueba.

## Debug
Reproducir → Aislar → Hipótesis → Verificar → Fix mínimo.
