# Handoff para Claude Code en el Mac mini (fine-tuning de Qwen3.5-4B)

Léelo completo antes de actuar. Habla en español, **conciso y directo** (respuesta primero, sin listas largas).

## Quién y qué
Candidato a una entrevista técnica de Oversight. Proyecto: "Expense Policy Validator" (5 componentes; solo el
Clasificador usa LLM: Haiku 5.5, prompt v3). El candidato **decide**; tú propones y construyes; todo se registra.
Meta: entrenar con LoRA un Qwen3.5-4B que haga SOLO el trabajo del clasificador (categoría de cada línea,
banda de confianza low/medium/high, description_en, destinatario) y demostrar que **iguala** a Haiku a menor costo,
local y con datos propios. No "supera": Haiku ya saca 65/65 en 28 recibos puntuados y 137-139/144 en held-out
(rango; un solo anotador). El motor determinista no se toca; el modelo entra como proveedor y falla cerrado ante JSON malo.

## Reglas duras
1. No modificar la carpeta `Expense-Policy-Validator-Junior-Mid/` (material original; solo lectura).
2. No entrenar con: los 32 recibos, las 144 líneas del held-out (`data_heldout/`), ni nada de `data_eval/`. No abrir `gold.jsonl`.
3. No tocar `validator/DECISIONS.md`, `AI_LOG.md`, README (congelados). El registro va en `finetune/FINETUNE_LOG.md`.
4. Nunca leer ni imprimir llaves (`.env`). No subir datos reales a servicios externos.
5. No inventar hechos; si no se verifica, dilo. Pide permiso antes de instalar paquetes o gastar dinero.
6. Registra cada decisión en `FINETUNE_LOG.md` con fecha y quién decidió.

## Decisiones ya tomadas (2026-10-28, por el candidato)
- Arrancar ya el fine-tuning (la pausa del handoff original se levantó).
- Los datos sintéticos los genera **Claude Sonnet 5.5** (gasta cuota de Claude: aceptado). Ver pregunta abierta sobre términos en el log.
- Se mostrará el entrenamiento en un **Jupyter notebook**.
- Entrenamiento: probable Mac local con MLX. Confirmar con una prueba corta de velocidad (~50 iteraciones); si una época del set más grande tarda demasiadas horas, usar Kaggle (solo datos sintéticos).

## Protocolo de evaluación (fijado ANTES de entrenar; no cambiarlo tras ver resultados)
Tres brazos en las mismas líneas: (a) Qwen3.5-4B sin tunear, (b) Qwen3.5-4B + LoRA, (c) Haiku 5.5 v3 (+ baseline de palabras clave).
Splits: sintético train / sintético validación / pruebas nunca vistas. El held-out ya se usó para elegir prompts: crear un
**set nuevo congelado (100-200 líneas)** antes de entrenar. Deduplicar (exacto y difuso) sintético vs 32 recibos y held-out.
Métricas: exactitud de categoría, F1 macro, F1 de restricted, disposición de punta a punta por el mismo motor, destinatario,
% JSON válido, % de errores con banda `low` (EXC-03), costo y latencia. Estadística: Clopper-Pearson/Wilson, pareado, bootstrap,
>=3 semillas, margen de no inferioridad fijado antes (propuesta: <=3 puntos bajo Haiku en el set congelado, F1 restricted no peor,
JSON válido >=99.5 %). Curva de datos (50/200/500/1000+). Auditar a mano ~100 etiquetas sintéticas. Reportar el sintético aparte
("optimista"). Revisar que no se degrade capacidad general y que las bandas de confianza sigan sirviendo a EXC-03.

## Gates
1. Qwen3.5-4B sin tunear como proveedor local (llama-server) medido en held-out + 32 recibos.
2. Sintéticos con Sonnet 5.5 desde políticas y taxonomía, etiquetas por construcción (nunca de la clave de respuestas); auditar y deduplicar.
3. LoRA SFT (guía: rank ~16 para <2K ejemplos, 1 época, varias semillas) + evaluación del protocolo.
4. Reporte honesto, incluido un resultado negativo.

## Qué hay y qué falta en el Mac mini
- Pendiente: confirmar RAM del Mac mini, instalar `mlx_lm` en un entorno aparte, descargar `Qwen/Qwen3.5-4B` (en el MacBook Air ya están `Qwen3.5-4B` y `Qwen3.5-4B-Base`).
- El proyecto debe copiarse SIN: `validator/.env`, `validator/.venv`, `validator/.cache`, `validator/data_eval/`, `.git` (opcional).
  Sí: `validator/src`, `tests`, `data_split/receipts_input.jsonl`, `data_heldout/`, `output/EVAL.md`, `DECISIONS.md`, `AI_LOG.md`, `AWS_DESIGN.md`,
  `handoff.md`, `finetune/`, y las políticas y `category-taxonomy.md` del material original.
- Contexto completo del proyecto: `handoff.md` (secciones 4, 7, 10 y 10b). Registro del fine-tuning: `finetune/FINETUNE_LOG.md`.

## Primer paso sugerido
Leer este archivo y `FINETUNE_LOG.md`, confirmar RAM y entorno, y proponer al candidato (en pocas líneas) el plan del gate 1.
