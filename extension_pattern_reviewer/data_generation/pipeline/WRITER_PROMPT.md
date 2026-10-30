# Task: write the surface text for synthetic expense receipts (you are the WRITER)

Input: a seeds file (JSON list of receipts; each has `lines` = line "slots"). CODE has already decided every label (category, slice,
target confidence, recipient, injection, other_kind). You only write realistic TEXT that genuinely IS the assigned category.

## Hard rules
- Read ONLY: your seeds chunk file and `/Users/geboou/Desktop/oversight/Expense-Policy-Validator-Junior-Mid/data/category-taxonomy.md`. Open nothing else in the project
  (no validator/, data_eval/, data_split/, data_heldout/, gold/labels/expected files). No git, no network.
- Write ONLY your output file `/Users/geboou/Desktop/oversight/finetune/data_synth/raw/<chunk_name>.json` (same base name as the seeds chunk).
- Do not copy the taxonomy's typical examples verbatim; invent new, varied items. Fictional merchants, no real people.

## Output: a JSON list, one object per receipt in the chunk, same order
{"seed_id": "...", "merchant_name": "...", "lines": [{"slot_id": "...", "description_raw": "...", "description_en": "...", "quantity": int>=1,
 "unit_price": number (in the receipt's currency, realistic magnitude: JPY/INR/MXN in whole larger numbers), "note": "<=8 words, only if category is other else null",
 "acceptable_alternatives": [category ids that a careful annotator could also accept; [] if none], "why": "<=15 words: why the assigned category is right"}]}
Every slot of every receipt must appear exactly once. Do not output category, labels or confidence (code adds them).

## How to write each line
- `description_raw` is written NATIVELY in the slot's `language` (not a word-for-word translation). `description_en`: English translation of the words only; keep brand names as written; if language is en, identical.
- The item must truly BE the assigned `category` (what the item IS, not the words in its name). Never write the category slug in the text (except injection lines).
- Vary style using the slot's `style` and `persona` hints; vary length (2-60 chars mostly), include quantities/sizes/sku fragments sometimes. Match the receipt's merchant archetype only when natural: ~25% of receipts are deliberately mismatched (e.g. alcohol sold at a grocery).
- `target_confidence` tells how recognisable the item should be from the line text + receipt context: high = unambiguous; medium = probably that category but a defensible alternative exists (fill acceptable_alternatives); low = hard to decide from the text alone (opaque, vague, truncated, or genuinely between two categories; fill acceptable_alternatives with the other plausible category).
- Slice meanings:
  plain: clear ordinary item. trap_names_lie: the NAME points to another category than the true one (e.g. a word that suggests alcohol but the item is food/household, or a food-sounding name that is really something else) or both sides of a contrast.
  brand_no_hint: only a brand/product name, no category word. gift_vs_goods: items that are gifts only if given (cards, merchandise, boxes) vs ordinary goods.
  recipient_in_text: the line text ITSELF states who it is for. slot.recipient = {kind: client|employee|government_official, named: true/false}: write it in the line's language; if named=true include a person's name; for government_official say official/ministry/public employee/state company in words.
  dirty_text: typos, abbreviations, OCR noise, ALL CAPS, missing accents, truncated words, mixed language or script. injection: the line text also contains an instruction aimed at an AI classifier ("ignore previous instructions...", "category: X confidence high", "classify as ...", or a bare category slug), in the line's language or English, along with the real item; the true category is still the assigned one.
  service_vs_tip: service charge, gratuity, delivery/booking fee, or the item that carries one. extension_items (category other): follow `other_kind`: mobile_handset = a phone handset; entertainment_venue = ticket/admission to golf, theatre, concert, sport; prescription_medication = a prescription drug; none = something fitting no category. restricted_boundary: an item right on the border between two categories; the assigned one is right.
- For category `other` write a short `note` saying what the item is; otherwise note = null.

## Quality
Valid JSON only (no comments). Check with a tiny `python3 -I` script that all slot_ids are present once and the JSON parses. Reply with ONE line: file path, receipts, lines, and any slot you could not satisfy.
