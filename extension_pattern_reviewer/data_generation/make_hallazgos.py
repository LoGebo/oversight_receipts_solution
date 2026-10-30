import json, collections
D = "data_synth/"
rd = lambda p: [json.loads(x) for x in open(D + p)]
TR = rd("patterns_v2_train.jsonl") + rd("patterns_v2_test_seen.jsonl") + rd("patterns_v2_test_unseen.jsonl")
R1, R2 = rd("patterns_v2_redteam.jsonl"), rd("patterns_v2_redteam2.jsonl")
hold = set(json.load(open(D + "reviewer_sft/heldout_schemes.json")))
def rows(h, n=4):
    pl = set(h["planted_receipts"]); out = []
    for r in h["receipts"]:
        if r["receipt_id"] in pl:
            li = r["line_items"][0]; out.append(f"| {r['transaction_datetime'][:10]} | {r['merchant_name'][:28]} | {r['submitted_expense_type']} | ${r['total_amount_usd']} | {li['description_raw'][:60]} |")
    return "\n".join(out[:n])
HEAD = "| Fecha | Comercio | Tipo | USD | Línea |\n|---|---|---|---|---|"
MECH = {"gift_splitting": ("Varios regalos al mismo cliente en días distintos", "tope de $50 por regalo, **por recibo**", "GIFT-01"),
 "gift_under_naming": ("Muchos regalos sin destinatario, cada uno bajo $10", "desde $10 hay que nombrar al destinatario", "GIFT-01"),
 "tech_just_under": ("Compras de equipo a $195–$199.9, repetidas", "desde $200 por artículo se pide preaprobación", "TECH-02"),
 "itemize_just_under": ("Recibos de un solo total entre $72 y $75, repetidos", "sobre $75 se exige desglose", "DOC-01"),
 "meal_cap_hugging": ("Comidas individuales siempre al 97–99 % del tope diario", "tope por persona y día: $75 ($60 en APAC)", "MEAL-01/REG-02"),
 "meal_just_under_doc": ("Comidas de equipo de $145–$150 repetidas en el mismo lugar", "sobre $150 hay que documentar asistentes", "MEAL-02"),
 "duplicate_submission": ("El mismo gasto enviado dos veces con ids distintos", "cada copia, sola, es válida", "(ninguna regla)"),
 "pa_reuse": ("Una misma preaprobación cubre varias compras grandes", "con preaprobación la compra es válida", "TECH-02/EXC-02")}
md = ["""# Hallazgos: fraudes que el motor determinista deja pasar
*Registro vivo para la presentación. Fuente de verdad: `finetune/data_synth/` y `FINETUNE_LOG.md`. Actualizado tras la ronda 2 del equipo rojo y la línea base de Haiku.*

## 1. El argumento principal (con la fuente)
the reference company, *Part 1 — Build*:
> "**We wanted a way to review recent behavior without engineering a new feature for every pattern.** An LLM can compare the current transaction with the supplied history and apply fraud-review guidance expressed in natural language. Updating that guidance does not require retraining the model, although every change still needs validation against transaction outcomes."

**Nuestro hallazgo, con evidencia:** hay esquemas que el motor determinista deja pasar recibo por recibo y que ninguna regla anticipada atrapa. Pedimos a agentes de Claude que los inventaran sin que yo los pensara: **48 esquemas** en dos rondas (6 agentes por ronda, cada uno con una zona temática), y **el motor deja pasar el 100 %** de sus recibos (verificado con el motor real). Cada esquema nuevo exigiría que alguien lo imagine y lo programe; un revisor con guía en lenguaje natural no necesita una regla por patrón.
**El ciclo propuesto:** el LLM *descubre* y escala a revisión humana; lo que una persona confirma se vuelve regla determinista. El LLM nunca baja un `flag` ni decide un rechazo.

## 2. Resultados medidos (revisor Haiku solo con prompt; reglas congeladas antes de calificar)
| Examen | Reglas (5 familias, A1) | Reglas (8 familias, A2) | Haiku revisor |
|---|---|---|---|
| Familias ya vistas (E3) | 100 % | 100 % | **88 %** (35/40 historiales) |
| Familias no vistas (E2) | 0 % | 95 % | **78 %** (47/60) |
| **Esquemas del equipo rojo apartados (E1, 12 esquemas)** | 0 % | 0 % | **54 %** (45/84; 35 % de los recibos) |
| Controles limpios (falsas alarmas) | 0 % | 0 % | **11 %** (10/91) |
Lectura honesta: donde las reglas no ven nada, el LLM con prompt encuentra la mitad o más de los historiales, pero **no todo**; las reglas son mejores en lo que alguien ya programó. Las falsas alarmas bajaron de 44 % a 11 % solo al arreglar defectos de mi generador (comercios que no encajaban, viajes incoherentes): el revisor es muy sensible a lo raro, y en datos reales, que son sucios, la precisión será el reto.

## 3. Catálogo A: 8 familias propias, basadas en topes reales del motor
"""]
for f, (t, why, rule) in MECH.items():
    ex = next(h for h in TR if h["family"] == f and h["language"] == "en")
    md.append(f"### {f}\n- **Qué es:** {t}.\n- **Por qué el motor lo deja pasar:** {why} ({rule}); cada recibo cumple.\n- **Ejemplo real:**\n\n{HEAD}\n{rows(ex)}\n")
md.append("## 4. Catálogo B: 48 esquemas inventados por el equipo rojo (ronda 1: 24, ronda 2: 24)\n*Los marcados con ⛔ se apartaron del entrenamiento y son el examen E1.*\n")
for name, R in (("Ronda 1", R1), ("Ronda 2", R2)):
    md.append(f"### {name}\n")
    bys = collections.OrderedDict()
    for h in R: bys.setdefault(h["scheme"], []).append(h)
    for s, hs in bys.items():
        ex = next((h for h in hs if h["language"] == "en"), hs[0])
        md.append(f"#### {s} {'⛔' if s in hold else ''}\n- **Por qué es sospechoso:** {ex['reason']}\n- **Historiales:** {len(hs)}\n\n{HEAD}\n{rows(ex)}\n")
md.append("""## 5. Límites honestos
- Los patrones son sintéticos, de nosotros o de agentes de Claude; detectarlos no prueba que se cace fraude real.
- Duplicados y reuso de preaprobación no están escritos en la política: son sospechas razonables.
- Los esquemas inventados por agentes comparten rellenos parecidos entre historiales (lo notaron dos revisores).
- Hallazgo lateral (varios agentes): el motor marca TECH-04 en todo recibo de software, incluso con referencia de aprobación; no se investigó si es una limitación del motor.
- Las falsas alarmas dependen de qué tan limpios sean los controles sintéticos (dos defectos de generador ya encontrados y corregidos).

## 6. Cómo reproducirlo
`pipeline/make_patterns_v3.py` · `redteam/RED_TEAM_SPEC*.md` + `pipeline/check_redteam.py` + `pipeline/combine_redteam*.py` · `pipeline/baseline_rules.py` · `pipeline/build_review_inputs*.py` + `review_in/REVIEWER_TASK.md` + `pipeline/score_review.py` · notebook `04_revisor_de_patrones`.
""")
open("HALLAZGOS_fraudes_que_el_motor_pasa.md", "w").write("\n".join(md)); print(len("\n".join(md)), "chars")
