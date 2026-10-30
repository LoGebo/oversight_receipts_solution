# Plan v2 consolidado: el enfoque "meta" (2026-10-29)
Fuentes: revisión de Opus 5.5 (`REVISION_OPUS55.md`), segunda opinión de DeepSeek V4 Pro (otra familia), búsqueda de literatura reciente, y el experimento contrafactual propio. Aprobado por el usuario: examen E6 de ~250 fraudes + ~250 limpios, Opus 4.5 solo en la prueba final, tope de gasto $150 (gasto esperado $60–90).

## Lo que ya está probado (no es opinión)
1. **Atajo confirmado por contrafactual** (reviewer_e5cf.json): mover UN recibo inocuo a sábado baja las alarmas en meses limpios de 100% a 6% y en meses con fraude de 95% a 24%; quitar fines de semana las sube a 100%. La detección real del v1 en E5 ≈ 24% con 6% de falsas alarmas. E1–E4 probablemente estaban inflados.
2. Bug en la corrida de Opus 4.5 (sin temperature=0; respuestas de ~68 tokens): corregido en `run_api_reviewer.py`. Bootstrap por esquema (clúster) ya en `evaluation.py`.

## El enfoque (en orden)
**Fase 0 · Compuertas antes de gastar** (gratis)
- Compuerta anti-atajo: un clasificador de rasgos superficiales (fin de semana, nº de recibos, viajes, tipos, idiomas, redondez, longitud, autor) debe dar AUROC ≤ 0.60 para predecir la etiqueta. Si no pasa, se remuestrea.
- Ablación del bloque SUMMARIES (también es un canal de fuga, lo señaló DeepSeek): se decide si se quita o se reemplaza por rasgos con la misma distribución en fraude y limpio.
- Líneas base SIN LLM: (a) reglas tipo SQL (suma de regalos por destinatario, comidas por día, reuso de preaprobación…), (b) árbol de decisión (GBM) sobre ~40 rasgos entre recibos. Si no les ganamos, la tesis "el LLM aporta" cae.

**Fase 1 · Datos** (suscripción, $0 de API)
- El CÓDIGO fija el esqueleto del mes (nº de recibos, fechas, viajes, precios) con la MISMA distribución para fraude y limpio; los modelos solo escriben texto e insertan el mecanismo.
- Autores de varias familias (DeepSeek V4.1/V4 Pro, Kimi K2.6, Claude); asignación en cuadrado latino dominio × mecanismo × familia.
- Por esquema: fraudes + negativos duros + pares mínimos (mismo mes con lo plantado sustituido por equivalentes inocuos, verificados con el motor). Proporción fraude:limpio ≈ 1:1.5.
- Auditoría de etiquetas con una familia distinta; sin descartar fraudes "porque el auditor no los vio".
- Razones específicas de cada historial (ids, montos, fechas), no la frase del esquema.

**Fase 2 · Examen E6** (congelado con hash antes de entrenar)
- ~250 fraudes (≥60 esquemas) + ~250 limpios, escritos por familias que NO estén en el entrenamiento (ni Anthropic ni Qwen) + **≥30 meses escritos a mano por personas** (lo más valioso: es lo único que prueba si aprendió fraude y no el proceso de generación del proyecto).
- Ya no se reutilizan E1–E5 para decidir nada.

**Fase 3 · Entrenamiento** (dos pistas)
- Pista Mac mini: Qwen3-8B / Qwen3.5-9B.
- Pista GPU rentada: Qwen3.5-27B (QLoRA).
- Para cada pista, dos variantes: (A) **cabeza de clasificación / puntuación por logits** (barata, entrena en minutos, da un puntaje continuo) y (B) **SFT generativo con razones verificadas** (auditable) y luego GRPO con recompensa que penaliza fuerte la falsa alarma y amortigua el recall (p. ej. recall/(1+0.65·FP), patrón visto en la literatura).
- Umbral de abstención calibrado en un set de validación INDEPENDIENTE (conformal): meta FA ≤ 5% con intervalo exacto. El set de validación se parte por esquema y por autor, nunca por fila.

**Fase 4 · Evaluación y decisión**
- Métrica primaria: recall por historial a FA ≤ 5% en el punto de operación congelado; secundarias: recall en dólares, F1 por recibo, alertas por 1,000 meses (con prevalencia supuesta de 2%).
- Comparadores: Opus 4.5 (temperature=0; zero-shot y razonamiento extendido) en la prueba final; Opus 5.5 y Sonnet como agentes (suscripción, $0); líneas base sin LLM.
- Intervalos con bootstrap por esquema. Veredicto GANA/EMPATA/PIERDE con los mismos criterios pre-registrados.

## Presupuesto y calendario (estimados)
- GPU rentada ~$30–60; Opus 4.5 en E6 ~$30–40 (zero-shot ~$4 + razonamiento ~$35 si E6≈500); total ~$60–90.
- ~4 días de trabajo: D1 compuertas + generador; D2 generación, verificación, auditoría, E6 + meses a mano; D3 entrenamiento (Mac de noche, GPU); D4 evaluación + notebook.

## Riesgos
- Duplicación CONCEPTUAL de esquemas (todos los esquemas nacieron en este proyecto): se mitiga con los meses escritos a mano y con deduplicación semántica.
- Destilar etiquetas de Opus 4.5 podría violar términos de uso: no se hace sin revisar.
- Probabilidades (Opus 5.5, FA ≤ 5%): superar a Opus 4.5 sin razonamiento 70–85%; a su mejor configuración con razonamiento 25–50%; empatar con un revisor tipo agente 10–30%.

## No afirmar en la presentación
- "Le ganamos al frontier" mientras el comparador sea débil o la prueba no sea independiente.
- Los números de E1–E4 del modelo v1 como evidencia de capacidad (están inflados por el atajo).
