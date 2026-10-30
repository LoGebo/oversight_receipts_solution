# Hallazgos: fraudes que el motor determinista deja pasar
*Registro vivo para la presentación. Fuente de verdad: `finetune/data_synth/` y `FINETUNE_LOG.md`. Actualizado tras la ronda 2 del equipo rojo y la línea base de Haiku.*

## 1. El argumento principal (con la fuente)
la empresa de referencia, *Part 1 — Build*:
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

### gift_splitting
- **Qué es:** Varios regalos al mismo cliente en días distintos.
- **Por qué el motor lo deja pasar:** tope de $50 por regalo, **por recibo** (GIFT-01); cada recibo cumple.
- **Ejemplo real:**

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-09 | The Giving Tree Shop | Client Gifts | $34.28 | Thank-you present for Horizon Biotech Inc. contact Matthew S |
| 2026-05-10 | Petal & Stem Florist | Client Gifts | $33.18 | Appreciation gift for Matthew Sullivan from Horizon Biotech  |
| 2026-05-12 | The Gift Gallery | Client Gifts | $44.3 | Corporate gift: hardcover coffee table book, for Matthew Sul |
| 2026-05-14 | Copperfield Gifts | Client Gifts | $43.74 | Corporate gift: silk tie, for Matthew Sullivan (Horizon Biot |

### gift_under_naming
- **Qué es:** Muchos regalos sin destinatario, cada uno bajo $10.
- **Por qué el motor lo deja pasar:** desde $10 hay que nombrar al destinatario (GIFT-01); cada recibo cumple.
- **Ejemplo real:**

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-16 | The Gift Gallery | Client Gifts | $7.06 | pocket mirror |
| 2026-05-17 | Honeybee Gift Baskets | Client Gifts | $8.53 | pack of pencils |
| 2026-05-18 | Petal & Stem Florist | Client Gifts | $9.27 | thank-you cards (pack of 10) |
| 2026-05-19 | The Giving Tree Shop | Client Gifts | $6.56 | seed packet |

### tech_just_under
- **Qué es:** Compras de equipo a $195–$199.9, repetidas.
- **Por qué el motor lo deja pasar:** desde $200 por artículo se pide preaprobación (TECH-02); cada recibo cumple.
- **Ejemplo real:**

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-09 | Circuit & Co. | Computer Equipment | $195.56 | Cable management kit, 40 pieces |
| 2026-05-11 | The Cable Shed | Computer Equipment | $197.88 | HDMI cable 2m, 4K60 |
| 2026-05-12 | Orbit Peripherals | Computer Equipment | $199.83 | Monitor arm, single, gas spring, fits 17-32 inch |

### itemize_just_under
- **Qué es:** Recibos de un solo total entre $72 y $75, repetidos.
- **Por qué el motor lo deja pasar:** sobre $75 se exige desglose (DOC-01); cada recibo cumple.
- **Ejemplo real:**

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-15 | Corner Page Books | Office Supplies | $73.4 | Amount due |
| 2026-05-16 | Summit Locksmiths | Office Supplies | $72.86 | Charges |
| 2026-05-17 | Swift Lane Couriers | Office Supplies | $74.7 | Amount due |

### meal_cap_hugging
- **Qué es:** Comidas individuales siempre al 97–99 % del tope diario.
- **Por qué el motor lo deja pasar:** tope por persona y día: $75 ($60 en APAC) (MEAL-01/REG-02); cada recibo cumple.
- **Ejemplo real:**

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-11 | Marlow's Burger Joint | Meals - Individual | $73.05 | Spaghetti bolognese with sparkling water |
| 2026-05-13 | Pier 9 Seafood Shack | Meals - Individual | $74.63 | Tomato soup and grilled cheese |
| 2026-05-15 | Foxglove Tavern Kitchen | Meals - Individual | $74.46 | Spaghetti bolognese with sparkling water |
| 2026-05-16 | Marlow's Burger Joint | Meals - Individual | $73.19 | Quinoa bowl with roasted vegetables |

### meal_just_under_doc
- **Qué es:** Comidas de equipo de $145–$150 repetidas en el mismo lugar.
- **Por qué el motor lo deja pasar:** sobre $150 hay que documentar asistentes (MEAL-02); cada recibo cumple.
- **Ejemplo real:**

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-12 | Oak Barrel Smokehouse | Meals - Team | $147.85 | Quinoa bowl with roasted vegetables |
| 2026-05-13 | Oak Barrel Smokehouse | Meals - Team | $145.56 | Set lunch: soup of the day, grilled chicken, rice, soft drin |
| 2026-05-14 | Oak Barrel Smokehouse | Meals - Team | $149.25 | Breakfast-for-dinner: pancakes and fruit, juice |
| 2026-05-15 | Oak Barrel Smokehouse | Meals - Team | $148.95 | Vegetable curry with rice and naan |

### duplicate_submission
- **Qué es:** El mismo gasto enviado dos veces con ids distintos.
- **Por qué el motor lo deja pasar:** cada copia, sola, es válida ((ninguna regla)); cada recibo cumple.
- **Ejemplo real:**

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-08 | Ember Grill House | Meals - Individual | $5.73 | 2 x filter coffee, regular |

### pa_reuse
- **Qué es:** Una misma preaprobación cubre varias compras grandes.
- **Por qué el motor lo deja pasar:** con preaprobación la compra es válida (TECH-02/EXC-02); cada recibo cumple.
- **Ejemplo real:**

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-08 | Orbit Peripherals | Computer Equipment | $301.64 | Noise-cancelling headset with boom mic |
| 2026-05-09 | Oakline Electronics | Computer Equipment | $397.74 | USB-C docking station 11-in-1, dual HDMI |
| 2026-05-11 | The Cable Shed | Computer Equipment | $398.08 | Wireless presenter remote with laser pointer |
| 2026-05-14 | Circuit & Co. | Computer Equipment | $395.44 | HDMI cable 2m, 4K60 |

## 4. Catálogo B: 48 esquemas inventados por el equipo rojo (ronda 1: 24, ronda 2: 24)
*Los marcados con ⛔ se apartaron del entrenamiento y son el examen E1.*

### Ronda 1

#### weekend_client_entertainment_no_trip 
- **Por qué es sospechoso:** Client Entertainment is claimed repeatedly on Saturdays/Sundays with no trip or client visit, suggesting personal leisure outings relabelled as client entertainment.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-02 | Northside Diner | Client Entertainment | $113.39 | Business dinner |
| 2026-05-03 | Juniper Kitchen | Client Entertainment | $128.2 | Business dinner |
| 2026-05-09 | Northside Diner | Client Entertainment | $110.33 | Business dinner |
| 2026-05-16 | Northside Diner | Client Entertainment | $128.48 | Business dinner |

#### overlapping_lodging_same_night 
- **Por qué es sospechoso:** Two different hotels are claimed for the same night(s) within one trip, a sign of double-claiming lodging or a personal stay billed in parallel.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-19 | Hotel Atlas Suites | Lodging | $135.61 | Hotel night |
| 2026-05-19 | Residencia Norte Plaza | Lodging | $121.23 | Hotel night |
| 2026-05-20 | Hotel Atlas Inn | Lodging | $133.91 | Hotel night |

#### recurring_item_merchant_rotation 
- **Por qué es sospechoso:** The same identical office item is bought every week from a different stationery merchant, so the same-merchant checks never fire and the recurring volume looks like stockpiling or resale.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-04 | Bürobedarf Meier | Office Supplies | $27.4 | Sticky notes 12-pack |
| 2026-05-11 | Papelería Nacional | Office Supplies | $27.4 | Sticky notes 12-pack |
| 2026-05-18 | Inkwell Supply | Office Supplies | $27.4 | Sticky notes 12-pack |
| 2026-05-25 | Staples Corner | Office Supplies | $27.4 | Sticky notes 12-pack |

#### trip_id_stretched_over_month ⛔
- **Por qué es sospechoso:** One trip_id with a 1-2 night duration carries meals and transport dated across nearly the whole month, so ordinary local spend is being attached to a trip.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-06 | Union Street Eatery | Meals - Individual | $38.64 | Lunch |
| 2026-05-13 | Bluebird Cafe Cab | Travel - Other | $20.16 | Taxi ride |
| 2026-05-19 | Harbor Grill | Meals - Individual | $47.56 | Lunch |

#### team_label_for_solo_meals 
- **Por qué es sospechoso:** Solo lunches repeatedly filed as two-person team meals at one restaurant to double the per-person cap headroom while attendees are never named.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-05 | Mesa Dorada | Meals - Team | $107.2 | Lunch for two |
| 2026-05-08 | Mesa Dorada | Meals - Team | $123.81 | Lunch for two |
| 2026-05-16 | Mesa Dorada | Meals - Team | $134.93 | Lunch for two |
| 2026-05-23 | Mesa Dorada | Meals - Team | $111.3 | Lunch for two |

#### personal_goods_as_office_supplies 
- **Por qué es sospechoso:** Household and personal items described in the line text are filed as Office Supplies with the office_supplies category label.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-09 | Papeterie Maison Claire | Office Supplies | $51.37 | Throw pillow covers |
| 2026-05-16 | Bureau Déco | Office Supplies | $58.81 | Kitchen hand towels set |
| 2026-05-25 | Papeterie Maison Claire | Office Supplies | $61.57 | Scented candles 3-pack |
| 2026-05-26 | Bureau Déco | Office Supplies | $32.9 | Phone case and screen guard |

#### gift_baskets_as_team_meals 
- **Por qué es sospechoso:** Gourmet hampers bought at gift shops are filed as team meals with nominal attendee counts, bypassing gift recipient naming and per-recipient limits.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-04 | Feinkost Geschenkhaus | Meals - Team | $103.59 | Gourmet hamper, assorted |
| 2026-05-10 | Präsentkorb Atelier | Meals - Team | $126.98 | Gourmet hamper, assorted |
| 2026-05-15 | Feinkost Geschenkhaus | Meals - Team | $128.15 | Gourmet hamper, assorted |
| 2026-05-24 | Präsentkorb Atelier | Meals - Team | $127.19 | Gourmet hamper, assorted |

#### weekend_rides_under_trip_id 
- **Por qué es sospechoso:** Evening and weekend ride-shares of a personal nature are filed as Travel - Other under a business trip id that does not match the dates.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-17 | Fahrdienst Blitz | Travel - Other | $67.47 | Ride share, weekend |
| 2026-05-24 | Taxi Nordstern | Travel - Other | $29.33 | Ride share, weekend |
| 2026-05-30 | Fahrdienst Blitz | Travel - Other | $46.08 | Ride share, weekend |

#### sequential_invoice_amounts 
- **Por qué es sospechoso:** Same vendor billed in an exact arithmetic progression of amounts, as if one fabricated invoice series were being drawn down.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-10 | Brightline Office Co | Office Supplies | $37.5 | Office supplies order |
| 2026-05-17 | Brightline Office Co | Office Supplies | $47.5 | Office supplies order |
| 2026-05-19 | Brightline Office Co | Office Supplies | $57.5 | Office supplies order |
| 2026-05-22 | Brightline Office Co | Office Supplies | $67.5 | Office supplies order |

#### cloned_fare_rotating_cab_companies 
- **Por qué es sospechoso:** The identical fare to the cent at the same hour is claimed from a different cab company each time, suggesting a template receipt with the merchant swapped.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-02 | BlueLine Cars | Travel - Other | $44.49 | Taxi ride to client site |
| 2026-05-05 | Capital Cabs | Travel - Other | $44.49 | Taxi ride to client site |
| 2026-05-14 | Metro Taxi | Travel - Other | $44.49 | Taxi ride to client site |
| 2026-05-20 | Yellow Ride | Travel - Other | $44.49 | Taxi ride to client site |

#### round_dollar_rotating_restaurants 
- **Por qué es sospechoso:** Dinners are always whole-dollar amounts at a different restaurant each time, suggesting invented or rounded-up figures rather than real receipts.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-04 | Oak Kitchen | Meals - Individual | $30.0 | Dinner |
| 2026-05-13 | Harbor Grill | Meals - Individual | $60.0 | Dinner |
| 2026-05-17 | Maple Diner | Meals - Individual | $35.0 | Dinner |
| 2026-05-27 | Pier Cafe | Meals - Individual | $55.0 | Dinner |

#### team_meal_split_across_food_hall_stalls 
- **Por qué es sospechoso:** One large team meal is split into several receipts from different stalls of the same food hall the same day, each under the team cap, with the same headcount.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-21 | Taco Yard | Meals - Team | $137.09 | Team lunch |
| 2026-05-21 | Noodle Corner | Meals - Team | $130.98 | Team lunch |
| 2026-05-21 | Grill 9 | Meals - Team | $137.79 | Team lunch |

#### gifts_to_clients_family_members 
- **Por qué es sospechoso:** Every gift is for a different relative of a client (wife, child, mother) rather than a client contact, on personal occasions, so the spend looks like personal giving rather than business relationship building.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-07 | Maple & Rye Gifts | Client Gifts | $29.68 | Toy set for client's son |
| 2026-05-11 | Bloom Corner Florist | Client Gifts | $34.89 | Flower bouquet for client's wife |
| 2026-05-13 | Little Acorn Toys | Client Gifts | $41.75 | Picture book for client's daughter |
| 2026-05-15 | Harbor Books | Client Gifts | $45.78 | Birthday candle set for client's mother |

#### identical_gift_rotating_recipients 
- **Por qué es sospechoso:** The same item is bought at about the cap for many different 'clients' from different shops, which looks like bulk personal gift shopping spread over recipients to dodge the per-recipient cap.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-05 | Linden & Co | Client Gifts | $44.84 | Cashmere-blend scarf |
| 2026-05-06 | Wren Boutique | Client Gifts | $44.84 | Cashmere-blend scarf |
| 2026-05-11 | Alder Home Store | Client Gifts | $44.84 | Cashmere-blend scarf |
| 2026-05-18 | Kestrel Goods | Client Gifts | $45.34 | Cashmere-blend scarf |

#### entertainment_headcount_vs_items_mismatch 
- **Por qué es sospechoso:** Client Entertainment receipts record a large attendee count (kept so per-head cost is low) but the items billed are only for two or three people, so the headcount looks inflated.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-12 | Riverside Bistro | Client Entertainment | $166.0 | Table dinner entrée |
| 2026-05-15 | Riverside Bistro | Client Entertainment | $165.0 | Table dinner entrée |
| 2026-05-28 | Riverside Bistro | Client Entertainment | $165.0 | Table dinner entrée |

#### weekend_family_outing_as_client_entertainment 
- **Por qué es sospechoso:** Client Entertainment claims fall on Saturdays and Sundays at kid-friendly venues with children's menus and four attendees, suggesting family outings relabelled as client entertainment.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-16 | Sunny Side Diner | Client Entertainment | $64.0 | Kids menu pancakes |
| 2026-05-17 | Pancake Barn | Client Entertainment | $78.0 | Kids menu pancakes |
| 2026-05-24 | Sunny Side Diner | Client Entertainment | $68.0 | Kids menu pancakes |
| 2026-05-31 | Sunny Side Diner | Client Entertainment | $76.0 | Kids menu pancakes |

#### trip_id_hopping 
- **Por qué es sospechoso:** One physical hotel stay is billed to two different trip ids with overlapping dates, so each trip looks plausible but the same nights are claimed twice.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-08 | Summit Suites | Lodging | $537.6 | Room night |
| 2026-05-08 | Summit Suites | Lodging | $348.4 | Room night |
| 2026-05-07 | CityRide Taxi | Travel - Other | $22.04 | Taxi fare |

#### lodging_nights_exceed_trip 
- **Por qué es sospechoso:** Lodging folios from several hotels add up to more nights than the declared trip length, hinting at padded or personal stays.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-15 | Summit Suites | Lodging | $291.36 | Room night |
| 2026-05-15 | Cedar Park Hotel | Lodging | $299.6 | Room night |
| 2026-05-14 | Harborview Inn | Lodging | $155.37 | Room night |

#### day_trip_with_lodging ⛔
- **Por qué es sospechoso:** A trip declared with zero nights carries an overnight hotel and evening spend, suggesting a day trip stretched into a paid personal overnight.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-06 | Lakeshore Lodge | Lodging | $172.75 | Room night |
| 2026-05-06 | Corner Bistro 41 | Meals - Individual | $33.37 | Dinner |
| 2026-05-07 | CityRide Taxi | Travel - Other | $38.23 | Taxi fare |

#### two_places_one_day ⛔
- **Por qué es sospechoso:** Meals and taxis on the same date are filed under two different trips in different cities, which is physically implausible.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-26 | Juniper Kitchen | Meals - Individual | $24.38 | Lunch |
| 2026-05-26 | CityRide Taxi | Travel - Other | $20.39 | Taxi fare |
| 2026-05-26 | Birch Table Grill | Meals - Individual | $31.48 | Dinner |
| 2026-05-26 | CityRide Taxi | Travel - Other | $22.12 | Taxi fare |

#### attendee_padding_vs_line_quantities 
- **Por qué es sospechoso:** Recurring team meals at one venue declare 7-9 attendees while the itemized quantities show only 2-3 portions, so the attendee count looks inflated to dodge per-person scrutiny.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-06 | Taverna Nova | Meals - Team | $43.04 | Entree |
| 2026-05-15 | Taverna Nova | Meals - Team | $45.14 | Entree |
| 2026-05-21 | Taverna Nova | Meals - Team | $64.32 | Entree |

#### teleporting_employee ⛔
- **Por qué es sospechoso:** Same day the employee claims an individual trip meal in one city and a team lunch with no trip in a different city, an impossible co-location pattern.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-05 | Dinner House Porto | Meals - Individual | $32.83 | Dinner |
| 2026-05-05 | Corner Roast Cafe Lisbon | Meals - Team | $99.38 | Team lunch |
| 2026-05-13 | Dinner House Porto | Meals - Individual | $32.71 | Dinner |
| 2026-05-13 | Corner Roast Cafe Lisbon | Meals - Team | $100.01 | Team lunch |

#### trip_id_recycled_for_commuting ⛔
- **Por qué es sospechoso:** One short trip id is reused on routine rides spread across many unrelated weekdays of the month, looking like a disguised daily commute.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-06 | City Cab Co 2 | Travel - Other | $30.37 | Taxi fare |
| 2026-05-07 | City Cab Co 2 | Travel - Other | $20.4 | Taxi fare |
| 2026-05-20 | City Cab Co 2 | Travel - Other | $31.95 | Taxi fare |
| 2026-05-28 | City Cab Co 2 | Travel - Other | $29.91 | Taxi fare |

#### weekend_stay_beyond_trip ⛔
- **Por qué es sospechoso:** Lodging, meals and rides are charged on the weekend after a Mon-Thu trip ended (more nights billed than the trip's recorded nights), suggesting a personal leisure extension.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-08 | Grand Plaza Hotel | Lodging | $159.31 | 1 night room |
| 2026-05-09 | Grand Plaza Hotel | Lodging | $161.99 | 1 night room |
| 2026-05-09 | Corner Roast Cafe Resort | Meals - Individual | $53.21 | Dinner |

### Ronda 2

#### annual_plus_monthly_double_billing 
- **Por qué es sospechoso:** The same software tool is claimed as an annual license and also as monthly plan charges in the same month, double-billing one subscription at two cadences.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-06 | Taskly Cloud | Software | $102.52 | Taskly Pro annual license (12 months) |
| 2026-05-22 | Taskly Cloud | Software | $11.96 | Taskly Pro monthly plan |
| 2026-05-27 | Taskly Cloud | Software | $11.96 | Taskly Pro monthly renewal |

#### standing_weekly_client_lunch 
- **Por qué es sospechoso:** The same near-identical client lunch recurs every Friday at one restaurant, a standing weekly lunch that looks like a routine personal habit billed as client entertainment.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-08 | Bayside Brasserie | Client Entertainment | $137.2 | Weekly client lunch set menu |
| 2026-05-15 | Bayside Brasserie | Client Entertainment | $141.2 | Weekly client lunch set menu |
| 2026-05-22 | Bayside Brasserie | Client Entertainment | $139.2 | Weekly client lunch set menu |
| 2026-05-29 | Bayside Brasserie | Client Entertainment | $139.2 | Weekly client lunch set menu |

#### weekly_subscription_box_as_office_supplies 
- **Por qué es sospechoso:** A weekly coffee and tea subscription box with an identical price is claimed as office supplies every week, recurring consumables for personal consumption.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-08 | BrewCrate Subscriptions | Office Supplies | $41.86 | Coffee capsule and tea box, weekly delivery (week 1) |
| 2026-05-15 | BrewCrate Subscriptions | Office Supplies | $41.86 | Coffee capsule and tea box, weekly delivery (week 2) |
| 2026-05-22 | BrewCrate Subscriptions | Office Supplies | $41.86 | Coffee capsule and tea box, weekly delivery (week 3) |
| 2026-05-29 | BrewCrate Subscriptions | Office Supplies | $41.86 | Coffee capsule and tea box, weekly delivery (week 4) |

#### personal_wellness_app_weekly_pass 
- **Por qué es sospechoso:** Weekly passes of a personal meditation and sleep app are claimed as software, a consumer subscription billed in weekly slices to evade a monthly review.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-04 | ZenPulse Apps | Software | $13.94 | ZenPulse Premium weekly pass, meditation and sleep sounds (w |
| 2026-05-11 | ZenPulse Apps | Software | $13.94 | ZenPulse Premium weekly pass, meditation and sleep sounds (w |
| 2026-05-18 | ZenPulse Apps | Software | $13.94 | ZenPulse Premium weekly pass, meditation and sleep sounds (w |
| 2026-05-25 | ZenPulse Apps | Software | $13.94 | ZenPulse Premium weekly pass, meditation and sleep sounds (w |

#### decorative_approval_refs_on_routine_receipts 
- **Por qué es sospechoso:** Approval references are attached to routine meals, taxi rides and supplies that never need one, lending false authority to ordinary spend.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-26 | Metro Yellow Cab | Travel - Other | $24.66 | Taxi: airport to hotel |
| 2026-05-28 | Daily Table Bistro | Meals - Individual | $22.15 | Lunch: grilled chicken sandwich and soda |
| 2026-05-29 | Metro Yellow Cab | Travel - Other | $23.39 | Taxi: hotel to client office |

#### approval_numbers_out_of_date_order 
- **Por qué es sospechoso:** Approved purchases are dated in ascending order yet carry approval numbers in descending order, so earlier purchases hold newer approvals, suggesting approvals obtained after the fact or borrowed.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-11 | Northgate Tech Depot | Computer Equipment | $325 | 27-inch monitor |
| 2026-05-28 | Brightline Office Tech | Computer Equipment | $267.99 | Thunderbolt docking station |
| 2026-05-29 | Circuit Hub | Computer Equipment | $208.99 | Ergonomic split keyboard |

#### overlapping_software_separate_approvals 
- **Por qué es sospechoso:** Several software subscriptions with the same function, each under its own separate approval reference, pile up overlapping tools no one person needs.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-04 | Folio PDF Studio | Software | $12.99 | PDF editor, monthly plan |
| 2026-05-15 | Notely | Software | $12.99 | Note-taking app, monthly plan |
| 2026-05-19 | VaultKey | Software | $9.99 | Password manager, monthly plan |
| 2026-05-22 | ClipCast | Software | $14.99 | Screen recorder, monthly plan |

#### approved_peripheral_bought_in_multiples 
- **Por qué es sospechoso:** Each purchase has its own approval reference, but quantities of 2 to 3 units of a single-user peripheral far exceed one person's need while staying inside the per-unit approval.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-07 | Circuit Hub | Computer Equipment | $410 | Ergonomic split keyboard |
| 2026-05-13 | Northgate Tech Depot | Computer Equipment | $552 | 27-inch monitor |
| 2026-05-18 | Brightline Office Tech | Computer Equipment | $723 | Thunderbolt docking station |

#### tip_and_service_charge_double_dip ⛔
- **Por qué es sospechoso:** Each dinner shows both an included service charge line and a separate tip line of similar percentage, so gratuity is claimed twice on every meal.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-11 | Kora Bistro | Meals - Individual | $47.03 | Dinner: main course and dessert |
| 2026-05-12 | Cobre Bistro | Meals - Individual | $58.61 | Dinner: main course and dessert |
| 2026-05-13 | Horizonte Bistro | Meals - Individual | $54.71 | Dinner: main course and dessert |

#### identical_booking_fee_across_rides ⛔
- **Por qué es sospechoso:** Four rides from different taxi companies each carry the exact same booking-fee add-on, which is implausible for independent vendors.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-11 | Tundra Cab Co | Travel - Other | $36.82 | Taxi: ride to client meeting |
| 2026-05-12 | Jade Cab Co | Travel - Other | $27.93 | Taxi: hotel to office |
| 2026-05-13 | Umbra Cab Co | Travel - Other | $26.42 | Taxi: ride to train station |
| 2026-05-14 | Cobre Cab Co | Travel - Other | $29.1 | Taxi: ride to conference center |

#### price_creep_same_item_weekly ⛔
- **Por qué es sospechoso:** The same box of paper is bought weekly at the same shop with the unit price climbing about 6% each time, suggesting inflated or fabricated invoices.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-01 | Vela Stationers | Office Supplies | $40.48 | A4 copy paper, box of 5 reams |
| 2026-05-08 | Vela Stationers | Office Supplies | $42.91 | A4 copy paper, box of 5 reams |
| 2026-05-15 | Vela Stationers | Office Supplies | $45.49 | A4 copy paper, box of 5 reams |
| 2026-05-22 | Vela Stationers | Office Supplies | $48.22 | A4 copy paper, box of 5 reams |

#### office_purchases_exact_multiples ⛔
- **Por qué es sospechoso:** Four different stationers bill exact consecutive multiples (1x, 2x, 3x, 4x) of one base amount, suggesting amounts were fabricated from a single number.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-06 | Quimera Stationers | Office Supplies | $14.0 | Desk organizer |
| 2026-05-12 | Lumen Stationers | Office Supplies | $28.0 | Document shelf |
| 2026-05-20 | Estrella Stationers | Office Supplies | $42.0 | Whiteboard set |
| 2026-05-26 | Kora Stationers | Office Supplies | $56.0 | Ergonomic footrest |

#### repeated_single_contact_hosting 
- **Por qué es sospechoso:** The same named client contact is hosted at four different venues within a few weeks, an unusually frequent hosting cadence for one person.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-05 | Olive & Thyme Bistro | Client Entertainment | $60.95 | Business lunch with Dana Whitfield (Northwind Logistics) |
| 2026-05-08 | Sunrise Brunch House | Client Entertainment | $55.45 | Brunch with Dana Whitfield (Northwind Logistics) |
| 2026-05-11 | The Copper Pot | Client Entertainment | $132.22 | Business dinner with Dana Whitfield (Northwind Logistics) |
| 2026-05-14 | Bean Theory Coffee | Client Entertainment | $15.15 | Coffee meeting with Dana Whitfield (Northwind Logistics) |

#### weekly_friday_client_lunch_same_cafe 
- **Por qué es sospechoso:** Every Friday the employee files a nameless two-person 'client' lunch at the same small cafe at a trivial per-head cost, the profile of recurring lunches with a colleague rather than clients.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-01 | Fig Street Cafe | Client Entertainment | $24.73 | Client lunch |
| 2026-05-08 | Fig Street Cafe | Client Entertainment | $27.4 | Client lunch |
| 2026-05-15 | Fig Street Cafe | Client Entertainment | $23.4 | Client lunch |
| 2026-05-22 | Fig Street Cafe | Client Entertainment | $26.78 | Client lunch |

#### internal_celebration_as_client_event 
- **Por qué es sospechoso:** Cake, decorations and party platters for 9-14 people are all filed as client entertainment on one day, matching an internal birthday or farewell party with no client named.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-14 | Sugar Loaf Bakery | Client Entertainment | $46.0 | Sheet cake with 'Happy Birthday Priya' icing |
| 2026-05-14 | Confetti Corner | Client Entertainment | $31.55 | Balloons and banner set |
| 2026-05-14 | Slice Brothers Pizza | Client Entertainment | $70.0 | Large pizzas, assorted toppings |

#### own_meal_double_claimed_in_entertainment 
- **Por qué es sospechoso:** On trip evenings the employee files a client dinner for three and then an individual dinner at the same restaurant minutes later, claiming their own meal twice.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-12 | Harbor Grill | Client Entertainment | $89.34 | Client dinner for 3 - set menu |
| 2026-05-12 | Harbor Grill | Meals - Individual | $18.24 | Dinner: grilled salmon and side salad |
| 2026-05-13 | Ember Steakhouse | Client Entertainment | $79.26 | Client dinner for 3 - tasting plates |
| 2026-05-13 | Ember Steakhouse | Meals - Individual | $21.66 | Dinner: pasta primavera and sparkling water |

#### bulk_stationery_resale_quantities 
- **Por qué es sospechoso:** One employee buys stationery in wholesale, resale-sized quantities (hundreds of pens or sleeves) that no single office worker could use.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-21 | Harbor Stationery Co. | Office Supplies | $112.15 | Spiral notebooks A5 |
| 2026-05-27 | Harbor Stationery Co. | Office Supplies | $143.46 | Highlighters, single |
| 2026-05-29 | Harbor Stationery Co. | Office Supplies | $203.53 | Sticky note pads |

#### streaming_rig_from_accessories ⛔
- **Por qué es sospechoso:** Over the month the equipment receipts, each a small accessory, add up to a complete home streaming studio (ring light, microphone, capture card, webcam).
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-15 | GameGear Peripherals | Computer Equipment | $76.05 | Ring light with tripod |
| 2026-05-20 | GameGear Peripherals | Computer Equipment | $91.36 | Webcam 1080p streaming |
| 2026-05-22 | GameGear Peripherals | Computer Equipment | $43.76 | Green screen backdrop, collapsible |
| 2026-05-27 | GameGear Peripherals | Computer Equipment | $39.86 | Microphone boom arm |

#### leisure_resort_merchants_on_business_trip 
- **Por qué es sospechoso:** The business trip's lodging, shuttles and meals are all at ski or beach resort venues, which makes a work purpose implausible.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-18 | Coral Bay Beach Resort & Spa | Lodging | $295.48 | Oceanfront room, per night |
| 2026-05-18 | Sunset Terrace Grill | Meals - Individual | $56.46 | Seafood dinner on the terrace |
| 2026-05-19 | Sunset Terrace Grill | Meals - Individual | $22.54 | Poolside breakfast platter |
| 2026-05-19 | Coral Bay Boat Transfers | Travel - Other | $30.63 | Island beach boat transfer |

#### grocery_stockpile_as_individual_meals 
- **Por qué es sospechoso:** Individual meal claims are supermarket baskets in family-sized quantities (kilos of chicken, dozens of eggs) that are not one person's meals.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-19 | FreshMart Supermarket | Meals - Individual | $38.6 | Family pack chicken legs, 3 kg |
| 2026-05-20 | Greenfield Grocery | Meals - Individual | $36.5 | Eggs, tray of 30 |
| 2026-05-21 | FreshMart Supermarket | Meals - Individual | $36.5 | Whole milk 1 L |

#### month_end_office_supply_flush 
- **Por qué es sospechoso:** No office-supply purchases all month, then four sizeable purchases at four different stationers in the final three working days, looking like a use-it-or-lose-it budget flush.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-27 | Metro Office Mart | Office Supplies | $134.0 | Filing cabinet 2-drawer |
| 2026-05-28 | BrightDesk Supply | Office Supplies | $54.0 | Ergonomic footrest |
| 2026-05-29 | Cornerstone Paper Co. | Office Supplies | $46.5 | Desk organizer set |
| 2026-05-29 | Harbor Stationers | Office Supplies | $118.0 | Laser toner cartridge, black |

#### dinners_stamped_just_past_curfew 
- **Por qué es sospechoso:** Client dinners are time-stamped just after the 05:00 cutoff of the overnight check (05:01 to 05:11) on several days, so the evening dinners look back-dated or edited to dodge the 00:00-05:00 rule.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-20 | Lantern House | Client Entertainment | $152 | Client dinner, set menu |
| 2026-05-21 | Olive Branch Bistro | Client Entertainment | $96 | Client dinner, grill platters |
| 2026-05-27 | Riverside Grill | Client Entertainment | $96 | Client dinner, tasting plates |

#### competing_saas_tool_sampling ⛔
- **Por qué es sospechoso:** Three or four competing tools with the same function (all sampled once in the same stretch of the month) are each expensed as 'Pro' monthly plans, a tool-sampling spree rather than a business need.
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-14 | Kanbanly Inc. | Software | $9.99 | Kanbanly Pro, monthly plan |
| 2026-05-21 | DoneList Inc. | Software | $12.99 | DoneList Pro, monthly plan |
| 2026-05-27 | TaskHive Inc. | Software | $12.99 | TaskHive Pro, monthly plan |
| 2026-05-28 | SprintPad Inc. | Software | $18.5 | SprintPad Pro, monthly plan |

#### two_dinners_same_evening 
- **Por qué es sospechoso:** On two evenings of the trip the employee claims both a solo dinner and a client dinner at different restaurants within 30 minutes of each other, so one of the two dinners cannot be real (double-claimed evening).
- **Historiales:** 7

| Fecha | Comercio | Tipo | USD | Línea |
|---|---|---|---|---|
| 2026-05-12 | Riverside Grill | Meals - Individual | $21.0 | Dinner: mushroom risotto and salad |
| 2026-05-12 | Olive Branch Bistro | Client Entertainment | $81 | Client dinner, tasting plates |
| 2026-05-13 | Olive Branch Bistro | Meals - Individual | $21.0 | Dinner: beef stew and bread |
| 2026-05-13 | Riverside Grill | Client Entertainment | $78 | Client dinner, grill platters |

## 5. Límites honestos
- Los patrones son sintéticos, de nosotros o de agentes de Claude; detectarlos no prueba que se cace fraude real.
- Duplicados y reuso de preaprobación no están escritos en la política: son sospechas razonables.
- Los esquemas inventados por agentes comparten rellenos parecidos entre historiales (lo notaron dos revisores).
- Hallazgo lateral (varios agentes): el motor marca TECH-04 en todo recibo de software, incluso con referencia de aprobación; no se investigó si es una limitación del motor.
- Las falsas alarmas dependen de qué tan limpios sean los controles sintéticos (dos defectos de generador ya encontrados y corregidos).

## 6. Cómo reproducirlo
`pipeline/make_patterns_v3.py` · `redteam/RED_TEAM_SPEC*.md` + `pipeline/check_redteam.py` + `pipeline/combine_redteam*.py` · `pipeline/baseline_rules.py` · `pipeline/build_review_inputs*.py` + `review_in/REVIEWER_TASK.md` + `pipeline/score_review.py` · notebook `04_revisor_de_patrones`.
