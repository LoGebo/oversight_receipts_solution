# Revisión crítica del fine-tune del revisor de patrones y plan para ganar

Autor: Claude Opus 5.5 (revisión pedida por el dueño). Fecha: 2026-10-29.
Alcance: leí `FINETUNE_LOG.md`, las celdas de `entregable/notebooks/01_FINAL_full_story.ipynb`, los scripts de `data_synth/pipeline/` (`build_reviewer_sft.py`, `render_history.py`, `make_patterns_v3.py`, `score_full.py`, `score_e5.py`, `run_api_reviewer.py`, `combine_redteam*.py`, `check_redteam.py`, `build_review_inputs*.py`), `REVIEWER_TASK.md`, `RED_TEAM_SPEC2.md` y `RED_TEAM_SPEC3.md`, y analicé `reviewer_sft/train.jsonl`, `valid.jsonl`, `eval_inputs.json`, `eval5_inputs.json` y las predicciones de `results/` (las del modelo propio y las de la API). **No abrí ninguna clave de respuestas** (`*key*.json`) ni la carpeta original de Oversight. Todo lo que marco como "verificado" lo calculé yo sobre esos archivos. Lo que es inferencia lo digo como tal.

---

## Resumen ejecutivo (lo más importante primero)

1. **Encontré la causa más probable del colapso en E5, y es verificable: un atajo de etiqueta por fuente.** En el set de entrenamiento, **todos** los historiales escritos por un LLM (el equipo rojo) son fraude, y **todos** los meses limpios los generó el código (`combine_redteam*.py:19` descarta los historiales sin plantados; `build_reviewer_sft.py:28-29` saca los limpios solo de `patterns_v3_train` (clean) y `patterns_v3_control`). El código reparte las fechas al azar entre los días 1 y 28 de mayo (`make_patterns_v3.py`, `days = sorted(r.sample(range(1, 29), 16))`), así que casi todos los meses limpios tienen algún recibo en fin de semana. Los autores LLM, en cambio, escriben meses de días hábiles. Resultado medido en train+valid: **"ningún recibo en fin de semana" → 178 fraudes contra 2 limpios** (99% fraude); "trips: none" → 29 contra 2. En E5, **153 de 160** historiales no tienen recibos en fin de semana. Y la decisión del modelo tuneado en E5 sigue a ese rasgo: **escala 148/153 de los historiales sin fin de semana y 1/7 de los que sí lo tienen** (cruce de `results/reviewer_e5ft.json` con `eval5_inputs.json`; no usé la clave). En E1–E4 pasa lo mismo: 83/84 de los historiales sin fin de semana fueron escalados. Esto no es "estilo del autor" en abstracto: es un atajo concreto y casi determinista, y probablemente también **infló el 88% de E1** (los historiales de E1 son del equipo rojo y por eso, casi todos, sin fin de semana).
2. **La comparación con Opus 4.5 por API no es justa, y además el script tiene un bug.** En `run_api_reviewer.py:19`, `"-5-" not in model` es falso para `claude-opus-4-5-20251101` (contiene "4-5-2"), así que **nunca se mandó temperature=0**. El registro (§13d) dice "temperatura 0": es falso. Opus 4.5 contestó en promedio **68 tokens** (solo el JSON, sin razonar), mientras que Sonnet 5.5 por la misma ruta contestó **491 tokens** en promedio. El "46%" de Opus mide un formato que le prohíbe pensar, no a Opus 4.5.
3. **El cuello de botella son los datos y la evaluación, no la potencia de cómputo.** Un modelo más grande con los mismos datos aprendería el mismo atajo. El plan para ganar es, en este orden:
   - (a) datos con **autoría balanceada por etiqueta**: cada autor, de varias familias, escribe fraude y limpio; los esqueletos del calendario (fechas, viajes, número de recibos) los controla el código, con la misma distribución para ambas clases; negativos duros y pares mínimos;
   - (b) un E6 escrito por **familias que no aparecen en el entrenamiento** y que no sean Anthropic, congelado por hash antes de entrenar, con unos 360 fraudes de 90 esquemas o más y unos 360 limpios;
   - (c) una base de 8–14B con razonamiento (y una de 27–32B si el despliegue puede ser un servidor propio), SFT con razones verificadas y después GRPO con recompensa determinista y castigo a la falsa alarma;
   - (d) un umbral por puntaje calibrado para FA ≤ 5%.

---

## 1. ¿Lo entiendo? (reformulación en 10 líneas)

1. Un motor determinista (41 reglas, 37 checks) decide pass/review/flag recibo por recibo; el LLM de la primera línea solo categoriza líneas.
2. El motor no ve patrones entre recibos. La segunda línea es un LLM que lee un mes de un empleado (recibos ya `pass` + un bloque SUMMARIES calculado por código) y solo puede **escalar pass→review**, con JSON `{"escalate":[{receipt_id, reason}]}`.
3. Los datos de fraude salen de tres fuentes: 8 familias por código (`make_patterns_v3.py`); 48 esquemas del equipo rojo escritos a mano por agentes Claude en 2 rondas (7 historiales cada uno); y E5, con 16 esquemas escritos por 16 agentes Opus independientes (6 fraudes + 4 limpios cada uno). Todo historial se verifica: cada recibo debe dar `pass` en el motor real.
4. El set SFT tiene 810 ejemplos de entrenamiento y 42 de validación: 429 positivos (252 del equipo rojo de 36 esquemas + 5 familias de código) y 381 limpios, todos de código. El prompt de sistema es corto y distinto de `REVIEWER_TASK.md`.
5. Entrenamiento: Qwen3-4B-Instruct-2507 en 4 bits, LoRA en MLX (r16, escala 20, 16 capas, lr 1e-4, batch 4, 400 iteraciones ≈ 2 épocas, pérdida solo en la respuesta).
6. Evaluación de desarrollo (E1–E4): E1 = 12 esquemas del equipo rojo apartados por nombre; E2 = 3 familias de código no vistas; E3 = familias vistas; E4 = 91 limpios de código (`control2`).
7. E5 (prueba): 96 fraudes y 64 limpios congelados por hash; criterios GANA/EMPATA/PIERDE fijados en §13 antes de medir.
8. Puntaje determinista: recall por historial (≥1 recibo plantado escalado), FA = un limpio con cualquier escalamiento, P/R/F1 por recibo, recall en dólares, IC de Wilson y bootstrap pareado.
9. Resultado: E1–E4 se veía como victoria (88/83/95%, 0% FA). En E5, 80% de recall con 97% de FA. Los frontier en E5 sacan 74–88% con 0% FA como agentes, y 36–49% con 0–5% FA por API de una sola llamada.
10. Veredicto pre-registrado: PIERDE. §19 (cambiar el comparador a "mejor Opus 4.5") está anotado, pero el registro dice que **no se ejecutó**.

### Ambigüedades y contradicciones que encontré

- **Título del log:** dice "Qwen3.5-4B". El modelo real es Qwen3-4B-Instruct-2507 (FT-007).
- **Temperatura de Opus 4.5:** §13d dice "temperatura 0", pero el código no la manda (bug de la sección 2.5); se usó la de omisión del API.
- **"Mismo prompt para todos":** la notebook 01 lo afirma (celda [40] y celda [49]: "same prompt"). Es falso. El tuneado usó el prompt corto de `build_reviewer_sft.py:13-18`; el frontier usó `REVIEWER_TASK.md`, con más reglas (OTC por viaje, cuidado personal/ropa $150, horario, etc.). Los agentes recibían además 13 historiales por archivo.
- **"Sonnet API 49% ≈ Opus 46% → el formato importa más que el modelo"** (celda [64]): las dos condiciones no son iguales. Sonnet generó unos 491 tokens de salida y Opus 68 (`results/api_*.json`, campo `usage`): Sonnet razonó en texto y Opus no.
- **"Red-team twins 8/48"** (§8): esos gemelos existen solo en `build_review_inputs.py` (v1, quitando los recibos plantados). **Nunca entraron al entrenamiento.** El log deja creer que sí hubo limpios escritos por LLM.
- **Comparador del veredicto:** §19 lo cambia a "mejor Opus 4.5", pero luego dice "NADA de §19 se ha ejecutado". La celda [55] de la notebook usa "mejor frontier excluyendo Haiku" (incluye a Sonnet agentes). Hay que dejar un solo comparador explícito.
- **Etiqueta `<think>\n\n</think>` en la salida del tuneado** (`reviewer_e5ft.json`, campo `raw`): Qwen3-4B-Instruct-2507 es un modelo sin modo de razonamiento y no debería emitirla. Es probable que la plantilla de chat de la conversión de mlx-community, o la del script de inferencia, sea la de Qwen3 híbrido. Hay que verificar que entrenamiento e inferencia usen la misma plantilla. No pude ver el script de inferencia: vive en el mini; `2.sh` local está vacío.
- **Validación:** la notebook (celda [44]) reconoce que la pérdida de validación no informa sobre generalización. La causa es que `build_reviewer_sft.py:35` parte por filas al azar, no por esquema ni por autor.

---

## 2. Revisión crítica de la metodología

### 2.1 Fugas y confusiones en los datos (de más a menos grave)

1. **La fuente predice la etiqueta (confusión perfecta).** Todo LLM es fraude y todo código es limpio. Con eso, el modelo puede aprender "¿lo escribió un LLM?" en vez de "¿hay un patrón?". Además, la regla de E1 se vuelve trivial para él: E1 viene del equipo rojo (fraude) y E4 del código (limpio), así que **E1–E4 no podía detectar este atajo por diseño**.
2. **Rasgos de calendario como atajo (verificado):** fin de semana (178:2), "sin viajes" (29:2). Los montos redondos aparecen sobre todo en positivos: ~152:45 con una regex aproximada. La causa es el muestreo uniforme de días del generador de código frente a la "normalidad laboral" que escriben los LLM.
3. **Sin negativos duros.** El spec de E5 (`RED_TEAM_SPEC3.md`) pidió limpios que "compartan rasgos superficiales del esquema de forma inocente". Los limpios de entrenamiento eran meses genéricos de código. E5 mide justo la robustez que nunca se entrenó.
4. **Razones memorizadas.** El objetivo de cada recibo plantado es la razón del esquema copiada (`build_reviewer_sft.py:20-21`): **41 razones distintas para 429 positivos** (verificado). El modelo aprende a recitar razones de esquemas y luego las "alucina" en meses limpios. Es el ejemplo X0001: "lodging folios add up to more nights…".
5. **E4 es del mismo generador que los 400 limpios de entrenamiento** (`control2` contra `control`/clean de v3): su 0% de FA está dentro de la distribución.
6. **Apartado solo por nombre de esquema.** Los esquemas apartados de E1 los escribieron los mismos agentes, en la misma ronda y con el mismo spec, que los de entrenamiento. Es apartado por concepto, no por autor ni por estilo.
7. **E5 lo escribió Opus 5.5 (Anthropic), y los comparadores son Anthropic.** Eso da ventaja de casa al frontier (§13c lo reconoce). Todo el entrenamiento también lo escribió Claude: el modelo propio heredó el estilo de Sonnet, y E5 tiene el de Opus.
8. **Filtro sin documentar:** `build_reviewer_sft.py:8` filtra `int(history_id[2:]) > 10130`. Hay que documentar por qué (¿excluye historiales usados en evaluaciones previas?).

### 2.2 Comparaciones injustas

- **El tuneado con prompt corto contra el frontier con el digest completo.** No invalida el resultado (cada uno en su formato nativo), pero la notebook no puede decir "mismo prompt".
- **Agentes contra API.** Los agentes procesan 13 historiales por archivo: ven contexto cruzado (contraste entre historiales del mismo lote), razonan en varios pasos y pueden calcular. Eso es otra tarea (revisión por lotes). La API de una sola llamada, sin razonamiento, es la peor versión posible del frontier. **El comparador justo es Opus 4.5 por API con razonamiento extendido**, o "razona y luego JSON", con el mismo número de iteraciones de prompt que tuvimos nosotros.
- **Few-shot con ejemplos del generador de entrenamiento:** a Opus le bajó el recall (46→36%). Los ejemplos de un solo autor sesgan también al frontier.
- **El modelo base se evaluó con el prompt corto, en 100 historiales y solo sin razonamiento** (siempre devuelve `[]`). La comparación "base vs tuneado" queda sin información; falta el base con el prompt completo y en modo de razonamiento.

### 2.3 Problemas de métricas

- **El recall por historial premia escalar todo.** Con 97% de FA, el 80% no significa nada. La métrica primaria debería ser **recall a FA fija** (≤5%, y reportar también 2%), o una curva recall–FA a partir de un puntaje continuo.
- **Prevalencia.** En producción, el fraude por mes de empleado será del orden de 1–5%. Con 2% de prevalencia, 85% de recall y 5% de FA, la precisión del escalamiento es ≈ 26%. Hay que reportar alertas por cada 1,000 meses (carga del revisor humano).
- **IC demasiado estrechos.** `score_e5.py:33-41` hace bootstrap remuestreando historiales i.i.d., pero hay 6 historiales por esquema y autor, correlacionados. Hace falta un **bootstrap por grupos (esquema/autor)**. Con 16 esquemas, el n efectivo se parece más a 16–40 que a 96.
- **FA sin incertidumbre.** La FA no entra al bootstrap, y la regla EMPATA (`score_e5.py:53`) compara FA puntuales y no mira dólares.
- **Recall en dólares con 96 historiales:** está dominado por pocos esquemas caros (en E1–E2, `pa_reuse` llevaba $22k). Es frágil; hay que reportarlo con IC por grupos.
- **Precisión por recibo y convención de etiquetado.** Cada autor decide qué recibos son "plantados" (¿el primer regalo legítimo de la serie cuenta?). Escalar un recibo relacionado no plantado cuenta como FP. Conviene definir una regla canónica ("conjunto mínimo de evidencia": recibos sin los cuales el patrón desaparece), más un conjunto "relacionado" que no penalice.
- **Los FP en limpios entran a la precisión agregada junto con E1–E3** (`score_full.py`): la precisión depende de la mezcla. Hay que reportarla por separado.

### 2.4 Qué más, además del estilo, pudo causar el colapso

| Factor | Evidencia | Peso |
|---|---|---|
| Fuente → etiqueta (LLM = fraude) | `combine_redteam*.py:19`; 0 limpios LLM en train | Muy alto |
| Fin de semana / viajes en el bloque SUMMARIES | 178:2 y 29:2 en train; 148/153 contra 1/7 en E5 | Muy alto (verificado como correlación) |
| Sin negativos duros | spec E5 contra `make_patterns_v3.py` clean | Alto |
| Razones memorizadas por esquema | 41 razones únicas; copias en E5 | Medio (síntoma y mecanismo) |
| Sobreajuste (2 épocas, val 0.047, val no apartada) | `curve_reviewer.json`, `build_reviewer_sft.py:35` | Medio |
| Distribución de precios/tipos (E5: monto medio $82 contra $54–62; 5.75 tipos de gasto contra ~4) | mis estadísticas de superficie | Medio-bajo |
| Ruido de etiqueta en limpios de E5 | frontier 0% FA → poco probable | Bajo |
| Prompt corto (sin "la mayoría de los meses son normales" con fuerza) | `build_reviewer_sft.py:13` | Bajo |
| Plantilla de chat (`<think>`) | salida `raw` | Bajo, pero hay que verificarlo |

### 2.5 Bugs en los scripts

1. **`run_api_reviewer.py:19`:** `elif "-5-" not in model` excluye `claude-opus-4-5-20251101`, así que no se manda temperature=0. Fix: lista explícita de modelos que rechazan `temperature`. Repetir las corridas de Opus 4.5 y declararlas.
2. **`run_api_reviewer.py`:** si fallan todos los reintentos, devuelve `escalate: []` con `json_ok False`, y el puntaje lo cuenta como "no escaló". En las corridas finales no hubo fallas (0/160, verificado), pero en la primera corrida de `sonnet55api` fallaron 160/160 (`api_run.log`). Fix: que el puntaje rechace corridas con fallas en vez de tratarlas como abstenciones.
3. **`score_e5.py:33-41`:** bootstrap i.i.d. (ver 2.3). Además, el bootstrap pareado excluye los limpios y la regla EMPATA ignora los dólares.
4. **`build_reviewer_sft.py:20-21`:** razón del esquema copiada a todos los recibos.
5. **`build_reviewer_sft.py:35`:** validación aleatoria por fila; el split debería hacerse por esquema y por autor.
6. **`build_reviewer_sft.py:13-18`:** se lee `REVIEWER_TASK.md` y se sobrescribe enseguida (código muerto). Además, ese prompt corto omite reglas que sí tiene el prompt del frontier.
7. **`score_full.py` / `score_e5.py`:** la regex de montos (`^- (\S+-R\d+) \|[^|]*\|[^|]*\|[^|]*\| \$…`) falla en silencio (monto = 0) si un comercio contiene `|`. Hay que contar las coincidencias y comprobar que sean iguales al número de recibos.
8. **Generador de código:** fechas uniformes sin modelo de semana laboral; `tday()` satura en 28; los precios de los esquemas son siempre bandas fijas (195–199.9, 72.5–74.95…), un atajo numérico para las familias de código.

---

## 3. ¿Por qué falló en E5? Hipótesis ordenadas y experimentos baratos para distinguirlas

| # | Hipótesis | Prob. a priori | Experimento discriminante (Mac mini, adaptador v1, E5 solo como diagnóstico, ya "quemado") | Costo |
|---|---|---|---|---|
| H1 | Atajo de calendario y fuente: "sin fin de semana / sin viajes / tiene pinta de LLM" ⇒ escalar | 0.6 | **Contrafactual:** (i) en los 64 limpios y 96 fraudes de E5, cambiar solo la línea SUMMARIES a "receipts dated Saturday or Sunday: R0X"; (ii) insertar un recibo inocuo en sábado (café de $4.50, sin viaje); (iii) al revés: en 50 limpios de E4, mover a días hábiles los recibos de fin de semana. Si la FA en limpios E5 baja de 97% a <40% con (ii), y la de E4 sube de 0% a >50% con (iii), H1 queda confirmada de forma causal. | ~1 h |
| H2 | Sin negativos duros (el modelo no aprendió a abstenerse ante rasgos inocentes del dominio) | 0.2 | Ver si las FA restantes tras el contrafactual se concentran en limpios que comparten dominio con su esquema (lectura de razones), y el análisis por autor. | 1 h |
| H3 | Hay señal pero mal calibrada (umbral) | 0.1 (pero se puede combinar con H1) | **Puntaje por log-probabilidad:** s = log P(`]` \| `{"escalate":[`) frente a log P(`{`). Una pasada hacia adelante. AUROC fraude-vs-limpio en E5: si ≥0.80, la información existe y basta un umbral; si es ~0.5–0.6, no hay señal. | 30 min |
| H4 | La capacidad base no alcanza (un 4B en 4 bits sin razonamiento no puede hacer la tarea) | 0.1 | **Base con el prompt completo:** Qwen3-4B-2507 y Qwen3-8B (modo razonamiento) zero-shot con `REVIEWER_TASK.md` en E5. Si Qwen3-8B con razonamiento saca >50% de recall a FA ≤10% sin entrenar, la capacidad no es el límite. | 2–4 h |
| H5 | El bloque SUMMARIES es la vía principal del atajo | (parte de H1) | **Ablación:** quitar SUMMARIES en E4 y E5 y medir FA y recall. | 1 h |
| H6 | Autoría Opus contra Sonnet (estilo léxico) | baja tras H1 | Reentrenar el 4B (5 h) con la corrección mínima: (a) gemelos limpios del equipo rojo, reemplazando los recibos plantados por inocuos y verificando con el motor; (b) fechas de los limpios de código remuestreadas con la misma distribución de fin de semana que los fraudes. Si la FA en E5 baja mucho con el recall estable, el problema era la confusión de etiqueta, no el estilo. | 5–6 h de mini |

Primero haría H1 y H3, en una tarde. Si H1 se confirma, la historia que se cuenta cambia, y para bien: "aprendió un atajo identificable que el diseño de datos puede eliminar", en vez de "aprendió el estilo".

**Advertencia:** todo esto usa E5 como diagnóstico. Desde ya, **E5 queda quemado como prueba**: se reporta como "desarrollo" en adelante. La prueba nueva es E6.

---

## 4. Plan de optimización para GANAR (priorizado)

### P0. Arreglar la evaluación antes que nada (ganancia: credibilidad; costo ~$0; riesgo bajo)
- Corregir los bugs 1–3 y 7 de la sección 2.5.
- Bootstrap por grupos (esquema y autor) para todas las diferencias, incluida la FA.
- Métrica primaria: **recall por historial a FA ≤ 5%** en el punto de operación congelado. Secundarias: recall en dólares, F1 por recibo con el conjunto "relacionado", alertas por cada 1,000 meses con prevalencia supuesta de 2%.
- **Base de comparación no LLM obligatoria:** un modelo de árboles (GBM) sobre ~40 rasgos calculados entre recibos (sumas por destinatario, cercanía a umbrales, ventanas de viaje, duplicados aproximados, días repetidos, montos redondos…), entrenado en los mismos datos. Si el LLM no le gana, la tesis "el LLM aporta" no se sostiene.

### P1. Datos multifamilia con autoría balanceada (palanca #1; ganancia esperada: FA de 97% a ≤10% sin umbral, recall E6 de 60 a 80%; costo $20–80 de API; riesgo medio)

**Que la generación sea multifamilia es correcto, pero no basta.** Si DeepSeek escribe solo fraudes y el código solo limpios, se reproduce el mismo error. La regla de oro es **autor ⟂ etiqueta**.

Protocolo:
1. **El esqueleto lo controla el código y es igual para ambas clases.** Un muestreador decide, por historial: número de recibos (8–14), entidad, rol del empleado (vendedor viajero, ingeniero de oficina, asistente ejecutivo, gerente con equipo), número de viajes (0–3) con ventanas coherentes, fracción de recibos en fin de semana (de una distribución realista, p. ej. Beta), idioma y rangos de precio por tipo. **Fraude y limpio salen del mismo muestreador.** El LLM rellena el texto (comercios, descripciones, montos dentro de los rangos) y, si es fraude, inserta el mecanismo.
2. **Asignación en cuadrado latino:** dominio (regalos, equipo, comidas, alojamiento, transporte, software/otros, entretenimiento, aprobaciones) × tipo de mecanismo (partición, temporización, repetición, re-etiquetado, cantidad-vs-ítems, identidad del destinatario, imposibilidad espacio-temporal, reuso de referencia, casi-duplicado) × familia de autor. Cada familia cubre todos los dominios y nunca hay un dominio "propio" de un autor.
3. **Cada autor escribe, por esquema:** 4–6 fraudes, 4–6 **negativos duros** (mismo dominio, rasgos superficiales del esquema, inocentes), y el código fabrica **pares mínimos**: el mismo mes con los recibos plantados sustituidos por equivalentes inocuos (no borrados, para no cambiar el conteo), verificados con el motor. Además, meses "ordinarios" con la persona asignada.
4. **Proporción en entrenamiento:** fraude:limpio ≈ 1:1.5. Al menos el 50% de los limpios deben ser negativos duros o pares mínimos. La calibración final se hace con umbral, no con la proporción.
5. **Familias de autores sugeridas.**
   - Entrenamiento: DeepSeek (V3.x/R1), GLM (4.x), Anthropic (Sonnet/Opus; ya existen datos), Mistral (Large/Medium) y Kimi K2 si se puede.
   - E6 (nunca en entrenamiento, ni siquiera la familia): p. ej. Gemini, GPT o gpt-oss-120b, Llama 4, y **≥30 meses escritos a mano por personas** (el dueño o un colega). Eso vale más que cualquier familia extra.
   - **No usar Qwen como autor** (es la familia del alumno) **ni Anthropic en E6** (son los comparadores).
6. **Auditoría de etiquetas con otra familia, sin seleccionar por "detectabilidad".** Para cada historial, un auditor de otra familia (nunca un comparador cuando se audita E6) responde: (i) sin etiquetas, "¿hay algo que un auditor cuestionaría?"; (ii) con etiquetas, "¿el limpio es inocente? ¿el fraude es realmente sospechoso y los plantados son el conjunto mínimo?". Desacuerdo de 2 auditores → adjudicación humana o descarte. **No descartar fraudes porque el auditor no los encontró**: eso filtraría hacia lo que los LLM ya detectan y sesgaría a favor del frontier.
7. **Compuerta anti-atajos (pre-registrada).** Antes de entrenar: un clasificador logístico sobre ~30 rasgos de superficie sin contenido (conteos, fin de semana, viajes, tipos, idiomas, redondez, longitud del texto, autor) debe dar AUROC ≤ 0.60 para predecir la etiqueta; y la AUROC de "autor → etiqueta" debe ser ≈ 0.5. Si no pasa, se remuestrea.
8. **Deduplicación:** exacta y difusa entre splits. A nivel de esquema: embeddings de la descripción más un juez de otra familia, para que los esquemas de E6 no sean paráfrasis de los de entrenamiento.
9. **Tamaños:** entrenamiento con **≥150 esquemas** (incluye los 64 actuales re-etiquetados con gemelos) → ~1,000 fraudes + ~1,500 limpios. Validación de desarrollo: 1 familia de autor apartada + 20 esquemas apartados (~300 historiales) para elegir checkpoints y umbral.
10. **Razones de entrenamiento específicas del historial** (citan ids, montos y fechas), no la frase del esquema.

**Términos de uso:** verificar los de DeepSeek y GLM (y los de Anthropic, que el log ya marcó como ambiguos) antes de publicar. La diversificación también reduce la dependencia legal de una sola fuente.

### P2. Modelo base (ganancia: +5–15 pts de recall a FA fija frente a 4B; riesgo: despliegue)

El despliegue decide el tamaño. Dos pistas:
- **Pista A (cabe en el Mac mini, 16 GB, solo inferencia): Qwen3-8B** (denso, modo de razonamiento conmutable; ~5 GB en 4 bits) o **Qwen3.5-9B** (paridad con el caso de referencia; en el mini la inferencia en 4 bits debería caber, pero hay que medirla: el entrenamiento ya falló ahí por memoria). Se entrenan en GPU rentada en bf16 y se cuantizan a 4 bits para MLX (y se evalúa *ya cuantizado*).
- **Pista B (servidor propio con una GPU de 48–80 GB): Qwen3.5-27B, Qwen3-32B o Qwen3-30B-A3B** (MoE, rápido). Alternativas: Gemma 3 27B, Mistral Small 3.x 24B. AWQ/FP8 para servir con vLLM. Es la de mayor probabilidad de empatar con un frontier.
- **Contexto:** los historiales ocupan ~1.4k tokens. Con razonamiento, la secuencia queda en ≤4–6k. Entrenar con un máximo de 6k.
- **No usar** modelos <4B ni 4B sin razonamiento: la tarea requiere aritmética de ventanas y sumas.
- Verificar la disponibilidad y licencia exactas (Qwen3.5/"3.6", etc.) antes de fijar; no lo verifiqué.

### P3. Entrenamiento

**SFT (calentamiento, sobre un objetivo con razonamiento verificado):**
- **Objetivo:** "análisis breve (≤250 tokens, cita recibos y hechos calculados) + JSON", o el bloque de razonamiento del modelo. Las razones salen de **muestreo con rechazo multifamilia**: DeepSeek-R1, GLM y Opus generan K=4 análisis por historial de entrenamiento; solo se guardan los que coinciden con la clave (correcto a nivel de historial y F1 por recibo ≥ 0.8; en limpios, lista vacía). Así no se destila la "opinión" de una sola familia y se filtra por exactitud.
- **Hiperparámetros (8–14B, LoRA bf16 en H100):** rank 32–64, α = 2×rank, todas las proyecciones lineales, lr 1e-4 coseno, warmup 3%, batch efectivo 32, **1–2 épocas** (no 2 ciegas: early stopping por **FA y recall en la validación de autor apartado**, no por pérdida), pérdida solo en la respuesta, max_seq 6k, 3 semillas.
- **QLoRA** solo para 27–32B en una GPU de 80 GB. FT completo no hace falta.
- **Pesos:** peso por clase 1:1 en la pérdida. Peso por dólares moderado (√monto planteado) solo en ejemplos de fraude; no exagerar, porque premia los esquemas caros de un autor.
- **Currículo:** familias de código y fraudes obvios primero; negativos duros y pares mínimos en la segunda mitad.

**RLVR (GRPO) sobre el checkpoint SFT (ganancia esperada: +5–10 pts de recall a FA fija y mejor calibración; riesgo: hackeo de recompensa):**
- **Framework:** TRL `GRPOTrainer` con vLLM colocado (lo más simple en 1 GPU) o Unsloth (eficiente en memoria, LoRA). verl o SkyRL solo para 27–32B en varias GPU.
- **Configuración:** G = 8 muestras por prompt, temperatura 1.0, max completion 1,024–1,536, β_KL 0–0.02, lr 5e-6 a 1e-5 (LoRA), clip 0.2 (clip-higher 0.28 al estilo DAPO), filtrado dinámico de grupos con varianza 0, ~2,000 prompts balanceados 50/50, 1–2 épocas (~300–500 pasos de 64 prompts).
- **Recompensa determinista (pre-registrar):**
  - JSON inválido o `receipt_id` inexistente → −1.
  - **Limpio:** 0 escalamientos → +1; si no, −1 − 0.2·(n−1), con tope en −2.
  - **Fraude:** P = TP/(TP+FP), donde FP excluye el conjunto "relacionado". R$ = Σ$ atrapados / Σ$ plantados. Recompensa = F1(P, R$) + 0.5·[≥1 plantado escalado], en el rango [0, 1.5].
  - Penalización por >6 escalamientos y por longitud >1,500 tokens.
  - La asimetría (limpio: ±1; fraude: hasta 1.5) se ajusta en la validación para el punto de operación FA ≤5%.
- **Costo de rollout (estimado, no medido):** 8B ≈ 8–12 h de H100 (~$20–40); 14B ≈ 15–25 h (~$40–75); 32B con QLoRA ≈ 2–4 H100 × 15–20 h (~$100–250). El caso de referencia reporta <$100 para 9B en una RTX PRO 6000: consistente.

### P4. Trucos en inferencia

- **Abstención por puntaje (obligatoria).**
  - Sin razonamiento: s = 1 − P(`]` | `{"escalate":[`), una sola pasada. Con razonamiento: la fracción de K=5 muestras que escalan ≥1 recibo.
  - Umbral calibrado en la validación de autor apartado para FA ≤ 4% (margen para llegar a ≤5% en E6), congelado antes de E6.
  - Es lo que más rápido baja la FA, pero **solo funciona si la AUROC es alta**: por eso el experimento H3 va primero.
- **Autoconsistencia:** K = 5–8 a T = 0.7. Se escala un recibo con ≥⌈K/2⌉ votos; el umbral de votos es el control de FA. Multiplica el costo por K: aceptable fuera de línea (lote nocturno).
- **Cascada o ensamble con semántica de solo-escalar:**
  - Unión de dos modelos locales: FA ≤ FA_a + FA_b. Con 3% + 3% queda en ≤6%; si los errores se correlacionan, cerca de 4%.
  - El recall sube a 1−(1−r_a)(1−r_b) si los aciertos fueran independientes; en E1–E2, la unión tuneado∪Sonnet dio 98%.
  - La intersección baja la FA y el recall.
  - **La unión con un frontier no es "gobernada"** (los datos salen): no se cuenta como solución local.
- **Formato de prompt para el modelo chico:** el prompt de entrenamiento debe ser el mismo que en inferencia y contener el digest completo. Agregar "la mayoría de los meses son normales; escala solo si puedes nombrar el mecanismo y los recibos". Mover más cálculo al código: sumas por destinatario, distancia a umbrales, ventanas de viaje contra fechas, gasto por día. **Probar la ablación del bloque SUMMARIES** (puede ser también la vía de atajos).

### P5. Evaluación final: E6 y comparadores

- **E6 se escribe primero y se congela por hash antes de generar el set de entrenamiento final.** Autores: 3 familias o más no presentes en entrenamiento, no Anthropic, no Qwen, más ≥30 meses humanos. Mismo esqueleto controlado por código, mismos negativos duros, auditoría por familias no comparadoras.
- **Tamaño (análisis de potencia):**
  - Para detectar 10 pts de diferencia en recall pareado (p. ej. 85% contra 75%, pares discordantes ≈ 24%), con α = 0.05 y potencia 0.8: n ≈ (1.96·√0.24 + 0.84·√0.23)² / 0.01 ≈ **186 fraudes independientes**.
  - Con correlación intra-esquema (ICC ≈ 0.2–0.3, 4 por esquema) el efecto de diseño es ≈ 1.6–1.9, así que hacen falta **~300–360 fraudes de ≥90 esquemas (≤4 por esquema)**.
  - Para la FA: con 360 limpios y FA observada de 2% (7/360), el límite superior de Wilson queda en ~4%, lo que permite afirmar "≤5%". Con 64 limpios, como en E5, eso es imposible: 0/64 ya tiene límite superior de 5.7%.
  - **E6 ≈ 360 fraudes + 360 limpios (≥50% negativos duros).**
- **Comparadores (pre-registrar las configuraciones y el presupuesto de ajuste de prompt, igual que el nuestro):**
  - Opus 4.5: (a) zero-shot solo JSON (existente, corregido el bug de temperatura); (b) +4 ejemplos multiautor; (c) **razonamiento extendido** (budget 8–16k); (d) "razona y luego JSON" sin el parámetro de razonamiento.
  - Sonnet 5.5 API con razonamiento, y Sonnet 5.5 en agentes como referencia de techo (no es el comparador del veredicto, porque procesa por lotes).
  - Más el GBM de rasgos y las reglas A2.
- **Veredictos (comparador = mejor configuración de Opus 4.5 en E6):**
  - **GANA:** el límite inferior del IC95% bootstrap por grupos de (nuestro recall − Opus) es > 0 en el punto de operación congelado, **y** nuestra FA en E6 es ≤ 5% (límite superior de Wilson ≤ 8%) y ≤ FA_Opus + 2 pts, **y** el recall en dólares no es inferior por más de 5 pts.
  - **EMPATA (no inferioridad):** el límite inferior de la diferencia es > −7 pts, con las mismas condiciones de FA.
  - **PIERDE:** cualquier otro caso.
  - Además: ganar al GBM con IC > 0 como condición para afirmar que "el LLM aporta".
- **Costo de evaluación frontier en E6:** Opus 4.5 con razonamiento cuesta ~1.5k tokens de entrada y 3–6k de salida por historial ≈ $0.08–0.16; × 720 ≈ $60–115 por configuración. Las 4 configuraciones de Opus más Sonnet salen en ≈ $200–350.

---

## 5. Probabilidades realistas (FA ≤ 5% en un E6 multiautor nuevo)

| Escenario | 8–9B (cabe en el Mac) | 27–32B (servidor propio) |
|---|---|---|
| (a1) Superar a Opus 4.5 API **sin razonamiento** (el 46% actual) | 70–80% | 80–85% |
| (a2) Superar a la **mejor** configuración de Opus 4.5 API (incluye razonamiento extendido), con IC > 0 | 25–35% | 40–50% |
| (b) Empatar (no inferior a −7 pts) con un revisor frontier tipo agente (~85–88% @ 0–2% FA) | 10–15% | 20–30% |

**Razonamiento:**
- El 46% de Opus vino de un formato que le prohíbe pensar. Con razonamiento, el frontier probablemente sube mucho (Sonnet pasó de 49% por API a 74–88% como agente); es una inferencia, falta medirla.
- A favor nuestro: el modelo propio entrena sobre la tarea exacta, con recompensa verificable y umbral calibrado, y E6 sin autores Anthropic quita la ventaja de casa.
- En contra: la tarea exige razonar sobre fechas, sumas y relaciones, donde el tamaño importa. Y con ≤360 fraudes, diferencias <8 pts no se separan.
- **La palanca individual más grande son los datos con autoría balanceada por etiqueta** (esqueleto común por código, pares mínimos y negativos duros), porque elimina el atajo que hoy explica casi toda la FA. Le siguen el umbral calibrado y el RLVR. El cómputo extra viene después.

---

## 6. Plan de ejecución paso a paso

| Día | Dónde | Qué | $ |
|---|---|---|---|
| 1 | Mac mini | Experimentos H1 (contrafactual de fin de semana), H3 (AUROC por logprob), H5 (ablación SUMMARIES), H4 (Qwen3-4B y Qwen3-8B base con el prompt completo; el 8B en 4 bits cabe para inferencia). Corregir los bugs de la sección 2.5. Registrar en el log. | 0 |
| 1–2 | Mac | Escribir y congelar el **pre-registro v2**: E6, métricas, compuerta anti-atajos, comparadores y configuraciones, veredictos, presupuesto. Construir el muestreador de esqueletos y la fabricación de pares mínimos (con el motor real). | 0 |
| 2–4 | API (OpenCode: DeepSeek, GLM; más otras familias) | **E6 primero:** autores de familias apartadas + ≥30 meses humanos; verificación con el motor; auditoría por no comparadores; **hash**. Nadie mira E6 después. | $10–40 |
| 3–5 | API | Set de entrenamiento: ≥150 esquemas, ~2,500 historiales; gemelos y negativos duros; auditoría cruzada; compuerta AUROC ≤ 0.60. Razones verificadas por muestreo con rechazo. | $30–100 |
| 5 | Mac | Piloto barato: reentrenar Qwen3-4B (MLX) con los datos nuevos y evaluar en la validación de autor apartado. Valida el pipeline antes de rentar. | 0 |
| 6–7 | **GPU rentada: 1× H100 80 GB** (RunPod o Lambda; Vast es más barato pero menos estable; ~$2–3.5/h, verificar precio) | SFT de 8B (3 semillas) → GRPO 8B; si hay presupuesto, QLoRA SFT + GRPO de 27–32B (2× H100 o 1× H200). Subir solo datos sintéticos; ninguna llave guardada en el pod. | $60–300 |
| 8 | Mac + servidor | Cuantizar (MLX 4 bits para la pista A; AWQ/FP8 para la B), **evaluar ya cuantizado** en la validación, calibrar y congelar el umbral. Medir latencia. | 0–20 |
| 9 | Todos | **Una sola corrida** en E6 de todos los brazos (nuestro, base, GBM, reglas, configuraciones de Opus 4.5, Sonnet). Puntaje con el script congelado; veredicto tal cual salga. | $200–350 API |
| 10 | — | Notebook y log actualizados, con los veredictos y la sección "qué no afirmamos". | 0 |

**Total:** ≈ $300–800 entre GPU y API, y unos 10 días de calendario.

### Decisiones que debe tomar el dueño

1. **Destino de despliegue:** Mac mini de 16 GB (tope ~8–9B en 4 bits) o servidor con GPU propio (permite 27–32B). Define el modelo.
2. **Comparador único del veredicto:** "mejor Opus 4.5 con razonamiento" (recomendado). Decidir si Sonnet agentes se reporta solo como techo.
3. **Punto de operación:** FA ≤ 5% (actual) o ≤ 2% (más realista para la carga humana).
4. **Familias de autores** para entrenamiento y para E6 (y si se pagan Gemini/GPT/Mistral además de DeepSeek/GLM). Y si el dueño u otra persona escribe ≥30 meses a mano.
5. **Revisión legal de términos** (Anthropic, DeepSeek, GLM) para usar sus salidas como datos de entrenamiento.
6. **Si se permite razonamiento** en producción (latencia: ~30–60 s por historial en el mini con 8B; aceptable en lote nocturno).
7. **Presupuesto máximo y regla de parada:** p. ej. una sola corrida en E6; si PIERDE, se reporta y se cierra.
8. **Qué hacer con E1–E5:** todos pasan a ser de desarrollo. Recomiendo no volver a citarlos como prueba.

---

## 7. Lo que NO se debe afirmar en la presentación

- "Nuestro modelo supera a un frontier" o "88% contra 54% de Haiku": E1 está dentro de la distribución y, muy probablemente, inflado por el atajo de fin de semana.
- "0% de falsas alarmas" como propiedad del modelo: solo vale para limpios del mismo generador. En datos independientes fue 97%.
- "Opus 4.5 saca 46%" u "Opus 4.5 es peor que Sonnet 5.5": se midió sin razonamiento, con ~68 tokens de salida y **sin temperatura 0, contra lo que dice el log**.
- "Todos los candidatos con el mismo prompt": falso.
- "El formato de llamada importa más que el modelo", como conclusión limpia: las dos API no estaban en la misma condición.
- "Generaliza a esquemas no vistos": lo apartado es el nombre, no el autor ni el estilo.
- "Aprendió el estilo del generador", como explicación única: la evidencia apunta a un atajo concreto (calendario y fuente → etiqueta). Hay que decirlo así y mostrar el contrafactual.
- "RLVR/GRPO" o "como el caso de referencia": se hizo SFT con un 4B de otra generación (Qwen3, no Qwen3.5).
- "Frontier con 0% FA en E5 ⇒ apto para producción": con n = 64, el límite superior de Wilson es 5.7%, y E5 lo escribió Opus (ventaja de casa).
- "La unión tuneado∪frontier es segura": es segura para el veredicto (solo escala), no para la carga humana ni para la gobernanza (los datos salen).
- Claims de costo total o latencia más allá de lo medido (~8 s por historial en el mini y el costo API medido).
- "Validado con fraude real": no hay datos reales.
- Cualquier diferencia entre modelos sin IC por grupos (esquema/autor).
