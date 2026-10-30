# Reporte para cuando despiertes (se actualiza solo con lo verificado)

## Dónde está todo
- **Notebooks** (Jupyter del Mac mini, carpeta `notebooks/`): `00_INDICE_resumen` → `01_hardware` → `02_dataset_sintetico` → `03_baselines` → **`04_revisor_de_patrones`** (el experimento principal).
- **Registro de decisiones y resultados, con fecha:** `finetune/FINETUNE_LOG.md` (secciones 7, 8 y 9 son los criterios fijados *antes* de ver resultados).
- **Catálogo para la presentación:** `finetune/HALLAZGOS_fraudes_que_el_motor_pasa.md` (8 familias propias + 48 esquemas del equipo rojo, con ejemplos reales y la cita de la empresa de referencia).

## Qué se hizo mientras dormías
1. **Equipo rojo ronda 2:** 6 agentes inventaron 24 esquemas nuevos (total 48). Verifiqué con el motor real que **todos sus recibos pasan** (168 historiales, 1,764 recibos).
2. **Controles limpios corregidos:** el generador tenía defectos (comercios que no encajaban con lo vendido, viajes incoherentes, textos repetidos). Corregidos; con controles limpios Haiku da **11 % de falsas alarmas** (antes 44 %).
3. **Conjunto de entrenamiento del revisor:** 810 ejemplos (429 con patrón, 381 limpios) + 42 de validación; 12 de los 48 esquemas **apartados** para examen.
4. **Línea base congelada** (Haiku con prompt): esquemas apartados 54 % de los historiales (45/84), familias no vistas 78 % (47/60), familias vistas 88 % (35/40), falsas alarmas 11 % (10/91).
5. **Cola nocturna en el Mac mini** (`queue_night.sh`, caffeinate activo): clasificador (Qwen3-4B, 400 pasos) → **revisor** (Qwen3-4B, 400 pasos, 16 capas LoRA) → examen del revisor entrenado → examen del clasificador entrenado → pruebas del modelo base sin entrenar.

## Cómo leer el resultado final
Cuando termine, en el mini: `~/finetune_project/night.log` marca cada etapa. Para calificar el revisor entrenado:
`scp` de `~/finetune_project/results/reviewer_ft.json` y luego `python3 finetune/data_synth/pipeline/score_ft.py reviewer_ft.json tuned`.
**Criterios fijados antes:** "se acerca" = detección en esquemas+familias no vistos ≥ 58.9 % y falsas alarmas ≤ 16 %; "supera" = ≥ 68.9 % con falsas alarmas ≤ 11 %. Con ~100 historiales por examen no se puede afirmar superioridad con intervalos solapados.

## Lo que NO sé todavía (se llena al terminar)
- Si el Qwen entrenado alcanza los criterios.
- Cuánto tarda el entrenamiento real (estimo 3-4 h por entrenamiento).

## Honestidad para tu presentación
- No prometo que el modelo propio le gane al de frontera. Si no lo hace, el hallazgo igual se defiende: *el LLM con prompt detecta esquemas que ninguna regla anticipada ve; el modelo propio es la versión local y controlada*.
- Los patrones son sintéticos (míos y de agentes de Claude). Detectarlos no prueba que se cace fraude real.
- Qwen3-4B (no Qwen3.5): Qwen3.5 no entra en 16 GB con MLX. Hay que decirlo.
- Riesgo de términos de Anthropic por generar datos con Claude: registrado, no verificado.


## RESULTADOS FINALES (actualizado)
- Revisor tuneado (Qwen3-4B): E1+E2 recall 86.1% vs Haiku 63.9%; falsas alarmas 0% vs 11%. Cumple "approaches" y "beats" (criterio congelado).
- Clasificador tuneado: 90.4% vs Haiku 98.3% / Sonnet 98.8% → no supera a frontier (sí +26 pts vs su base).
- Caveat principal: train y eval salen del mismo generador (Claude); falta validar con datos de otro autor/reales antes de afirmar nada fuera de este benchmark.
- Detalle y fallos por esquema: FINETUNE_LOG.md §10.

## Actualización: Sonnet 5.5 como revisor (mismos 275 historiales)
E1+E2: tuneado 86% / 0% FA; Sonnet 76% / 10% FA; Haiku 64% / 11% FA. Por receipt: F1 tuneado 74 vs Sonnet 72 (empate); recall en dólares 71% vs 80% (Sonnet gana); precisión 76% vs 90% (Sonnet gana). Ver FINETUNE_LOG.md §11.
