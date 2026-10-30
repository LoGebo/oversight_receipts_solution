# Expense validation report

## RCP-001 — PASS

Harvest Table Kitchen (MCC 5812) · Meals - Individual · GLOBAL · 48.2 USD = $48.2 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-001-L1 | Grilled salmon entree | 28.0 | food_beverage | False | 0.9 |
| RCP-001-L2 | Side garden salad | 8.0 | food_beverage | False | 0.9 |
| RCP-001-L3 | Iced tea | 4.5 | food_beverage | False | 0.9 |
| RCP-001-L4 | Gratuity 18% | 7.7 | service_fee | False | 0.9 |

Rules considered: DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-02, TIME-03, TIME-04, EXC-03

- no exceptions, no review signals

## RCP-002 — PASS

Verona Grill (MCC 5812) · Client Entertainment · GLOBAL · 234.0 USD = $234.0 · attendees 4

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-002-L1 | Prix fixe dinner | 136.0 | food_beverage | False | 0.9 |
| RCP-002-L2 | Chianti Classico bottle | 68.0 | alcohol | True | 0.9 |
| RCP-002-L3 | Gratuity | 30.0 | service_fee | False | 0.9 |

Rules considered: ALC-01, ALC-02, ALC-03, DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-03, TIME-04, EXC-03

- no exceptions, no review signals

## RCP-003 — PASS

Cornerstone Office Supply (MCC 5943) · Office Supplies · GLOBAL · 41.47 USD = $41.47 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-003-L1 | USB-C to HDMI adapter | 19.99 | computer_accessory | False | 0.9 |
| RCP-003-L2 | Legal pads 3-pack | 12.49 | office_supplies | False | 0.9 |
| RCP-003-L3 | Ballpoint pens box of 12 | 8.99 | office_supplies | False | 0.9 |

Rules considered: TECH-02, DOC-02, DOC-03, REG-05, TIME-01, EXC-03

- no exceptions, no review signals

## RCP-004 — PASS

Dockside Tavern & Grill (MCC 5812) · Meals - Team · GLOBAL · 49.0 USD = $49.0 · attendees 2

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-004-L1 | Beer battered cod & chips | 22.0 | food_beverage | False | 0.9 |
| RCP-004-L2 | Arnold Palmer | 10.0 | food_beverage | False | 0.9 |
| RCP-004-L3 | Mojito sin alcohol (en: Mojito sin alcohol) | 8.0 | food_beverage | False | 0.9 |
| RCP-004-L4 | Rum cake slice | 9.0 | food_beverage | False | 0.9 |

Rules considered: DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-03, TIME-04, EXC-03

- no exceptions, no review signals

## RCP-005 — PASS

Riverside Inn (MCC 7011) · Lodging · GLOBAL · 701.04 USD = $701.04 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-005-L1 | Room charge, 3 nights | 567.0 | lodging | False | 0.9 |
| RCP-005-L2 | Occupancy tax | 68.04 | lodging | False | 0.9 |
| RCP-005-L3 | Self parking, 3 nights | 66.0 | ground_transport | False | 0.9 |

Rules considered: DOC-02, DOC-03, REG-05, TIME-01, TIME-02, TIME-04, EXC-03

- no exceptions, no review signals

## RCP-006 — PASS

Cornerstone Office Supply (MCC 5943) · Computer Equipment · GLOBAL · 189.0 USD = $189.0 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-006-L1 | USB-C docking station, dual HDMI | 189.0 | computer_accessory | False | 0.9 |

Rules considered: TECH-02, DOC-02, DOC-03, REG-05, TIME-01, EXC-03

- no exceptions, no review signals

## RCP-007 — PASS

Bluebird Cafe (MCC 5812) · Meals - Team · GLOBAL · 212.0 USD = $212.0 · attendees 4

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-007-L1 | Sandwich platter | 156.0 | food_beverage | False | 0.9 |
| RCP-007-L2 | Assorted soft drinks | 36.0 | food_beverage | False | 0.9 |
| RCP-007-L3 | Service charge | 20.0 | service_fee | False | 0.9 |

Rules considered: DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-03, EXC-03

- no exceptions, no review signals

## RCP-008 — PASS

Le Petit Marche (MCC 5812) · Meals - Team · EMEA · 46.0 EUR = $49.68 · attendees 2

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-008-L1 | Salade nicoise (en: Salade nicoise) | 35.64 | food_beverage | False | 0.9 |
| RCP-008-L2 | Eau minerale 50cl (en: Eau minerale 50cl) | 8.64 | food_beverage | False | 0.9 |
| RCP-008-L3 | Cafe expresso (en: Cafe expresso) | 5.4 | food_beverage | False | 0.9 |

Rules considered: DOC-02, DOC-03, DOC-04, MEAL-01, MEAL-02, REG-03, REG-04, REG-05, TIME-01, TIME-03, TIME-04, EXC-03

- superseded MEAL-01: replaced by REG-03 for EMEA employees
- no exceptions, no review signals

## RCP-009 — PASS

Crisp Cleaners (MCC 7216) · Travel - Other · GLOBAL · 34.0 USD = $34.0 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-009-L1 | Dry cleaning - 3 shirts, 1 suit | 34.0 | laundry_service | False | 0.9 |

Rules considered: LAUNDRY-01, DOC-02, DOC-03, REG-05, TIME-01, TIME-02, TIME-04, EXC-03

- no exceptions, no review signals

## RCP-010 — FLAG

The Anchor House (MCC 5812) · Meals - Individual · GLOBAL · 64.4 USD = $64.4 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-010-L1 | Ribeye steak | 38.0 | food_beverage | False | 0.9 |
| RCP-010-L2 | Draft IPA 16oz | 18.0 | alcohol | True | 0.9 |
| RCP-010-L3 | Gratuity | 8.4 | service_fee | False | 0.9 |

Rules considered: ALC-01, ALC-02, ALC-03, DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-02, TIME-03, TIME-04, EXC-03

- **ALC-01** (high, `meals-and-entertainment-policy.md`) — ALC-01 (Alcohol requires a documented entertainment context) raises a high exception on 'Draft IPA 16oz' ($18.00): type='Meals - Individual', attendees=None: needs Client Entertainment with 2+ attendees.
  - lines: RCP-010-L2 "Draft IPA 16oz" $18.0
  - policy: > Alcohol is reimbursable only on a receipt declared as Client Entertainment that records an attendee count of two or more. Alcohol on any other receipt — an individual or team meal, or any receipt without an attendee count — is a high exception.

## RCP-011 — FLAG

Cellar Door Fine Wines (MCC 5921) · Client Entertainment · GLOBAL · 79.0 USD = $79.0 · attendees 6

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-011-L1 | Vino tinto Rioja Reserva 750ml (en: Vino tinto Rioja Reserva 750ml) | 72.0 | alcohol | True | 0.9 |
| RCP-011-L2 | Sparkling water 6-pack | 7.0 | food_beverage | False | 0.9 |

Rules considered: ALC-01, ALC-02, ALC-03, MCC-01, DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-03, EXC-03

- **ALC-03** (high, `meals-and-entertainment-policy.md`) — ALC-03 (Retail alcohol) raises a high exception on 'Vino tinto Rioja Reserva 750ml' ($72.00): MCC 5921 is not a restaurant, bar or hotel.
  - lines: RCP-011-L1 "Vino tinto Rioja Reserva 750ml" $72.0
  - policy: > Alcohol purchased from a package store, liquor store, or any other merchant that is not a restaurant, bar or hotel is never reimbursable, regardless of business context. This is a high exception. See also MCC-01 in merchant-category-risk.md.
- **MCC-01** (high, `merchant-category-risk.md`) — MCC-01 (High-risk merchant category) raises a high exception on the receipt from Cellar Door Fine Wines ($79.00 total): MCC 5921 is a high-risk merchant category.
  - lines: whole receipt
  - policy: > A transaction at a high-risk MCC raises a high exception on its own, whatever the line items say. These categories are not consistent with any routine business purpose.

## RCP-012 — FLAG

Pacific Electronics (MCC 5732) · Office Supplies · GLOBAL · 348.0 USD = $348.0 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-012-L1 | Sony WH-1000XM5 wireless headphones | 348.0 | personal_electronics | True | 0.9 |

Rules considered: MCC-02, TECH-01, DOC-02, DOC-03, REG-05, TIME-01, EXC-03

- **TECH-01** (high, `technology-and-equipment-policy.md`) — TECH-01 (Personal electronics are not reimbursable) raises a high exception on 'Sony WH-1000XM5 wireless headphones' ($348.00): categorised personal_electronics.
  - lines: RCP-012-L1 "Sony WH-1000XM5 wireless headphones" $348.0
  - policy: > This includes, and is not limited to: headphones and earbuds, smart watches and fitness trackers, tablets and e-readers, games consoles, cameras and drones, televisions, portable speakers, and item trackers. Accessories made for such a device — cases, chargers, screen protectors — count as personal electronics too. Purchase of any of these on an expense report is a high exception, regardless of stated business purpose.
- **DOC-03** (medium, `receipt-documentation-requirements.md`) — DOC-03 (Expense type must match the contents) raises a medium exception on the receipt from Pacific Electronics ($348.00 total): 'Office Supplies' covers ['computer_accessory', 'office_supplies']; lines are ['personal_electronics'].
  - lines: whole receipt
  - policy: > A receipt is misclassified when none of its line items belongs to a category that its declared expense type covers. Service fees, gratuities and items in the other category are ignored for this test; if no items remain, DOC-03 does not apply. A misclassification is a medium exception, reported in addition to any exception raised by the items themselves, not instead of it.
- review signal **MCC-02** (`merchant-category-risk.md`) — MCC 5732 is a medium-risk merchant category

## RCP-013 — FLAG

MarketPlace Retail (MCC 5311) · Client Gifts · GLOBAL · 104.99 USD = $104.99 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-013-L1 | Amazon.com gift card $100 | 100.0 | gift_card | True | 0.9 |
| RCP-013-L2 | Greeting card | 4.99 | gift | True | 0.9 |

Rules considered: MCC-02, DOC-02, DOC-03, GIFT-01, GIFT-02, GIFT-03, GIFT-04, REG-05, TIME-01, EXC-03

- **GIFT-02** (high, `gifts-and-awards-policy.md`) — GIFT-02 (Gift cards and cash equivalents) raises a high exception on 'Amazon.com gift card $100' ($100.00): categorised gift_card, a cash equivalent.
  - lines: RCP-013-L1 "Amazon.com gift card $100" $100.0
  - policy: > Gift cards, prepaid cards, vouchers, and any other cash equivalent are never reimbursable, at any amount and for any recipient. This is a high exception.
- review signal **MCC-02** (`merchant-category-risk.md`) — MCC 5311 is a medium-risk merchant category

## RCP-014 — FLAG

FreshMart Supermarket (MCC 5411) · Office Supplies · GLOBAL · 47.76 USD = $47.76 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-014-L1 | Tide Pods laundry detergent 42ct | 19.99 | household_goods | True | 0.9 |
| RCP-014-L2 | Bounty paper towels 6 rolls | 14.49 | household_goods | True | 0.9 |
| RCP-014-L3 | Dish soap 25oz | 4.29 | household_goods | True | 0.9 |
| RCP-014-L4 | Cooking wine - Marsala 375ml | 8.99 | alcohol | True | 0.9 |

Rules considered: ALC-01, ALC-02, ALC-03, MCC-02, HOUSE-01, DOC-02, DOC-03, REG-05, TIME-01, EXC-03

- **ALC-03** (high, `meals-and-entertainment-policy.md`) — ALC-03 (Retail alcohol) raises a high exception on 'Cooking wine - Marsala 375ml' ($8.99): MCC 5411 is not a restaurant, bar or hotel.
  - lines: RCP-014-L4 "Cooking wine - Marsala 375ml" $8.99
  - policy: > Alcohol purchased from a package store, liquor store, or any other merchant that is not a restaurant, bar or hotel is never reimbursable, regardless of business context. This is a high exception. See also MCC-01 in merchant-category-risk.md.
- **HOUSE-01** (medium, `non-reimbursable-items.md`) — HOUSE-01 (Household goods) raises a medium exception on 'Tide Pods laundry detergent 42ct' ($19.99), 'Bounty paper towels 6 rolls' ($14.49) and 'Dish soap 25oz' ($4.29): categorised household_goods.
  - lines: RCP-014-L1 "Tide Pods laundry detergent 42ct" $19.99; RCP-014-L2 "Bounty paper towels 6 rolls" $14.49; RCP-014-L3 "Dish soap 25oz" $4.29
  - policy: > Cleaning supplies, laundry products, household paper goods (paper towels, toilet paper, tissues), kitchenware and drinkware, bedding, furniture, small appliances, and home décor are not reimbursable, whether bought for home or for an office — office stock of this kind is bought centrally. This is a medium exception.
- **DOC-03** (medium, `receipt-documentation-requirements.md`) — DOC-03 (Expense type must match the contents) raises a medium exception on the receipt from FreshMart Supermarket ($47.76 total): 'Office Supplies' covers ['computer_accessory', 'office_supplies']; lines are ['alcohol', 'household_goods'].
  - lines: whole receipt
  - policy: > A receipt is misclassified when none of its line items belongs to a category that its declared expense type covers. Service fees, gratuities and items in the other category are ignored for this test; if no items remain, DOC-03 does not apply. A misclassification is a medium exception, reported in addition to any exception raised by the items themselves, not instead of it.
- review signal **MCC-02** (`merchant-category-risk.md`) — MCC 5411 is a medium-risk merchant category

## RCP-015 — FLAG

Sterling Chophouse (MCC 5812) · Client Entertainment · GLOBAL · 429.6 USD = $429.6 · attendees 2

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-015-L1 | Chef tasting menu | 248.0 | food_beverage | False | 0.9 |
| RCP-015-L2 | Barolo 2016 bottle | 110.0 | alcohol | True | 0.9 |
| RCP-015-L3 | Gratuity 20% | 71.6 | service_fee | False | 0.9 |

Rules considered: ALC-01, ALC-02, ALC-03, DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-03, EXC-03

- **ALC-02** (medium, `meals-and-entertainment-policy.md`) — ALC-02 (Alcohol per-attendee cap) raises a medium exception on 'Barolo 2016 bottle' ($110.00): $110.0 / 2 = $55.00 per attendee vs $30.
  - lines: RCP-015-L2 "Barolo 2016 bottle" $110.0
  - policy: > Where alcohol is permitted under ALC-01, it is capped at $30 per attendee: the USD total of the alcohol lines, divided by the attendee count. Spend above that cap is a medium exception.
- **MEAL-01** (medium, `meals-and-entertainment-policy.md`) — MEAL-01 (Daily meal cap) raises a medium exception on the receipt from Sterling Chophouse ($429.60 total): E-1128 on 2026-04-24: $214.80 (RCP-015) = $214.80 per person vs $75 (domestic).
  - lines: whole receipt
  - policy: > Meal spend is capped at $75 per person per day for domestic travel and $100 per person per day for international travel. Spend above the cap is a medium exception. For this rule:

## RCP-016 — FLAG

Taj Spice House (MCC 5812) · Client Entertainment · APAC · 5445.0 INR = $65.34 · attendees 3

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-016-L1 | Thali dinner | 43.2 | food_beverage | False | 0.9 |
| RCP-016-L2 | Kingfisher beer 650ml | 16.2 | alcohol | True | 0.9 |
| RCP-016-L3 | Service charge | 5.94 | service_fee | False | 0.9 |

Rules considered: ALC-01, ALC-02, ALC-03, REG-01, DOC-02, DOC-03, DOC-04, MEAL-01, MEAL-02, REG-02, REG-05, TIME-01, TIME-03, TIME-04, EXC-03

- **REG-01** (high, `regional-addendum.md`) — REG-01 (Alcohol) raises a high exception on 'Kingfisher beer 650ml' ($16.20): APAC employee: alcohol is never reimbursable.
  - lines: RCP-016-L2 "Kingfisher beer 650ml" $16.2
  - policy: > Alcohol is never reimbursable for APAC-entity employees, including within client entertainment. This overrides ALC-01 and ALC-02: where those rules would have permitted alcohol with an attendee count, REG-01 still makes it a high exception. For APAC employees REG-01 replaces ALC-01, ALC-02 and ALC-03: report REG-01 instead of those three. Rules about the merchant, such as MCC-01, still apply.
- superseded ALC-01: replaced by REG-01 for APAC employees
- superseded ALC-02: replaced by REG-01 for APAC employees
- superseded ALC-03: replaced by REG-01 for APAC employees
- superseded MEAL-01: replaced by REG-02 for APAC employees

## RCP-017 — FLAG

Serenity Spa at Grand Hotel (MCC 7297) · Lodging · GLOBAL · 140.0 USD = $140.0 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-017-L1 | 60-minute deep tissue massage | 120.0 | personal_care | True | 0.9 |
| RCP-017-L2 | Gratuity | 20.0 | service_fee | False | 0.9 |

Rules considered: MCC-01, PERS-01, PERS-02, DOC-02, DOC-03, REG-05, TIME-01, TIME-02, TIME-04, EXC-03

- **MCC-01** (high, `merchant-category-risk.md`) — MCC-01 (High-risk merchant category) raises a high exception on the receipt from Serenity Spa at Grand Hotel ($140.00 total): MCC 7297 is a high-risk merchant category.
  - lines: whole receipt
  - policy: > A transaction at a high-risk MCC raises a high exception on its own, whatever the line items say. These categories are not consistent with any routine business purpose.
- **PERS-01** (medium, `non-reimbursable-items.md`) — PERS-01 (Personal care and grooming) raises a medium exception on '60-minute deep tissue massage' ($120.00): personal_care without a baggage_delay reference (ref kind: None).
  - lines: RCP-017-L1 "60-minute deep tissue massage" $120.0
  - policy: > Toiletries, cosmetics, razors, haircuts, salon services, spa treatments, and massage are not reimbursable. This is a medium exception.
- **DOC-03** (medium, `receipt-documentation-requirements.md`) — DOC-03 (Expense type must match the contents) raises a medium exception on the receipt from Serenity Spa at Grand Hotel ($140.00 total): 'Lodging' covers ['ground_transport', 'laundry_service', 'lodging']; lines are ['personal_care'].
  - lines: whole receipt
  - policy: > A receipt is misclassified when none of its line items belongs to a category that its declared expense type covers. Service fees, gratuities and items in the other category are ignored for this test; if no items remain, DOC-03 does not apply. A misclassification is a medium exception, reported in addition to any exception raised by the items themselves, not instead of it.

## RCP-018 — FLAG

Aurora Fine Jewelers (MCC 5944) · Client Gifts · GLOBAL · 180.0 USD = $180.0 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-018-L1 | Sterling silver bracelet - client gift for A. Moreau, Halcyon Partners | 180.0 | jewelry | True | 0.9 |

Rules considered: MCC-01, DOC-02, DOC-03, GIFT-01, GIFT-03, GIFT-04, REG-05, TIME-01, TIME-03, EXC-03

- **MCC-01** (high, `merchant-category-risk.md`) — MCC-01 (High-risk merchant category) raises a high exception on the receipt from Aurora Fine Jewelers ($180.00 total): MCC 5944 is a high-risk merchant category.
  - lines: whole receipt
  - policy: > A transaction at a high-risk MCC raises a high exception on its own, whatever the line items say. These categories are not consistent with any routine business purpose.
- **GIFT-01** (medium, `gifts-and-awards-policy.md`) — GIFT-01 (Client gift cap) raises a medium exception on 'Sterling silver bracelet - client gift for A. Moreau, Halcyon Partners' ($180.00): per recipient $180.0 vs $50 cap; unnamed at $10+: none.
  - lines: RCP-018-L1 "Sterling silver bracelet - client gift for A. Moreau, Halcyon Partners" $180.0
  - policy: > Gifts to clients and prospects are capped at $50 per recipient per occasion. An occasion is one receipt; lines on it that name the same recipient are added together for the cap, and the $10 test applies to each line. Spend above the cap is a medium exception. Any gift of $10 or more must also name its recipient, in the line description or elsewhere on the expense; an unnamed gift at that value is a medium exception. Cards and small tokens under $10 need no named recipient. Gift cards and other cash equivalents fall under GIFT-02 alone and are not also tested here. Unnamed gifts are each tested on their own, and when both parts of GIFT-01 apply, one exception cites every line involved.

## RCP-019 — FLAG

Bic Camera Shinjuku (MCC 5732) · Computer Equipment · APAC · 97100.0 JPY = $650.57 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-019-L1 | iPad Air 11インチ 128GB (en: iPad Air 11-inch 128GB) | 601.66 | personal_electronics | True | 0.9 |
| RCP-019-L2 | タブレットケース (en: Tablet case) | 48.91 | personal_electronics | True | 0.9 |

Rules considered: MCC-02, TECH-01, DOC-02, DOC-03, DOC-04, REG-05, TIME-01, EXC-03

- **TECH-01** (high, `technology-and-equipment-policy.md`) — TECH-01 (Personal electronics are not reimbursable) raises a high exception on 'iPad Air 11インチ 128GB' ($601.66) and 'タブレットケース' ($48.91): categorised personal_electronics.
  - lines: RCP-019-L1 "iPad Air 11インチ 128GB" $601.66; RCP-019-L2 "タブレットケース" $48.91
  - policy: > This includes, and is not limited to: headphones and earbuds, smart watches and fitness trackers, tablets and e-readers, games consoles, cameras and drones, televisions, portable speakers, and item trackers. Accessories made for such a device — cases, chargers, screen protectors — count as personal electronics too. Purchase of any of these on an expense report is a high exception, regardless of stated business purpose.
- review signal **MCC-02** (`merchant-category-risk.md`) — MCC 5732 is a medium-risk merchant category

## RCP-020 — FLAG

Copper Skillet (MCC 5812) · Meals - Individual · GLOBAL · 74.0 USD = $74.0 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-020-L1 | Lunch entree - braised short rib | 42.0 | food_beverage | False | 0.9 |
| RCP-020-L2 | Appetizer - calamari | 18.0 | food_beverage | False | 0.9 |
| RCP-020-L3 | Soft drink | 5.0 | food_beverage | False | 0.9 |
| RCP-020-L4 | Gratuity | 9.0 | service_fee | False | 0.9 |

Rules considered: DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-02, TIME-03, TIME-04, EXC-03

- **TIME-03** (high, `transaction-pattern-rules.md`) — TIME-03 (Split transactions) raises a high exception on the receipt from Copper Skillet ($74.00 total): split transaction: meal spend per person vs the day's meal cap (MEAL-01, REG-02, REG-03): $74.00 (RCP-020) + $71.50 (RCP-021) = $145.50 > $75.00, each at or below it.
  - lines: whole receipt
  - policy: > Two or more receipts by the same employee, at the same merchant (by merchant name), on the same calendar date, are treated as a deliberate split when each one is at or below one of these thresholds but together they are above it: the $75 itemization threshold, when every receipt in the group is non-itemized (DOC-01); the employee's meal cap, compared per person (MEAL-01, REG-02, REG-03); or the $50 gift cap for one recipient (GIFT-01). This is an exception, at high severity, and applies to every receipt in the group. It replaces the threshold rule being split around: report the split, not a separate breach of that threshold.
- superseded MEAL-01: replaced by TIME-03, split around the meal cap (E-1180 on 2026-04-27: $74.00 (RCP-020) + $71.50 (RCP-021) = $145.50 per person vs $75 (domestic))

## RCP-021 — FLAG

Copper Skillet (MCC 5812) · Meals - Individual · GLOBAL · 71.5 USD = $71.5 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-021-L1 | Dinner entree - roast chicken | 44.0 | food_beverage | False | 0.9 |
| RCP-021-L2 | Soup of the day | 12.0 | food_beverage | False | 0.9 |
| RCP-021-L3 | Dessert - creme brulee | 9.0 | food_beverage | False | 0.9 |
| RCP-021-L4 | Gratuity | 6.5 | service_fee | False | 0.9 |

Rules considered: DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-02, TIME-03, TIME-04, EXC-03

- **TIME-03** (high, `transaction-pattern-rules.md`) — TIME-03 (Split transactions) raises a high exception on the receipt from Copper Skillet ($71.50 total): split transaction: meal spend per person vs the day's meal cap (MEAL-01, REG-02, REG-03): $74.00 (RCP-020) + $71.50 (RCP-021) = $145.50 > $75.00, each at or below it.
  - lines: whole receipt
  - policy: > Two or more receipts by the same employee, at the same merchant (by merchant name), on the same calendar date, are treated as a deliberate split when each one is at or below one of these thresholds but together they are above it: the $75 itemization threshold, when every receipt in the group is non-itemized (DOC-01); the employee's meal cap, compared per person (MEAL-01, REG-02, REG-03); or the $50 gift cap for one recipient (GIFT-01). This is an exception, at high severity, and applies to every receipt in the group. It replaces the threshold rule being split around: report the split, not a separate breach of that threshold.
- superseded MEAL-01: replaced by TIME-03, split around the meal cap (E-1180 on 2026-04-27: $74.00 (RCP-020) + $71.50 (RCP-021) = $145.50 per person vs $75 (domestic))

## RCP-022 — FLAG

Harbor View Restaurant (MCC 5812) · Client Entertainment · GLOBAL · 113.0 USD = $113.0 · attendees 2

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-022-L1 | Lunch entree — guest R. Delgado, City Procurement Office | 68.0 | food_beverage | False | 0.9 |
| RCP-022-L2 | Gift basket for R. Delgado, City Procurement Office | 45.0 | gift | True | 0.9 |

Rules considered: DOC-02, DOC-03, GIFT-01, GIFT-03, GIFT-04, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-03, EXC-03

- **GIFT-04** (critical, `gifts-and-awards-policy.md`) — GIFT-04 (Government officials) raises a critical exception on 'Lunch entree — guest R. Delgado, City Procurement Office' ($68.00) and 'Gift basket for R. Delgado, City Procurement Office' ($45.00): provided to a government official: route to Compliance.
  - lines: RCP-022-L1 "Lunch entree — guest R. Delgado, City Procurement Office" $68.0; RCP-022-L2 "Gift basket for R. Delgado, City Procurement Office" $45.0
  - policy: > Gifts, meals, or anything of value provided to a government official, public employee, or state-owned enterprise employee are prohibited under our anti-corruption policy, at any amount. The exception cites every line provided to the official — including a meal line that also covers the employee's own meal, but not a gratuity (EXC-04) — and replaces GIFT-01 for those lines. Other rules, such as the meal cap, still apply to the receipt. This is a critical exception and is routed to Compliance immediately, never to the standard audit queue.
- superseded GIFT-01: every gift line is for a government official: GIFT-04 replaces it

## RCP-023 — FLAG

Lakeside Grill (MCC 5812) · Meals - Team · GLOBAL · 186.0 USD = $186.0 · attendees 3

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-023-L1 | Restaurant charge - no itemization provided | 186.0 | other: non-itemized charge: contents unknown | False | 1.0 |

Rules considered: DOC-01, DOC-02, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-03, TIME-04, EXC-03

- **DOC-01** (medium, `receipt-documentation-requirements.md`) — DOC-01 (Itemization threshold) raises a medium exception on the receipt from Lakeside Grill ($186.00 total): $186.0 vs $75, itemized=False.
  - lines: whole receipt
  - policy: > Any receipt with a total above $75 (in USD) must be itemized. A non-itemized receipt above that threshold is a medium exception, because the contents cannot be audited.

## RCP-024 — FLAG

QuickStop Market (MCC 5411) · Meals - Individual · GLOBAL · 20.5 USD = $20.5 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-024-L1 | Marlboro Gold pack | 11.5 | tobacco | True | 0.9 |
| RCP-024-L2 | Coffee 16oz | 3.25 | food_beverage | False | 0.9 |
| RCP-024-L3 | Breakfast sandwich | 5.75 | food_beverage | False | 0.9 |

Rules considered: MCC-02, PERS-03, DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-02, TIME-03, TIME-04, EXC-03

- **PERS-03** (high, `non-reimbursable-items.md`) — PERS-03 (Tobacco and vaping) raises a high exception on 'Marlboro Gold pack' ($11.50): categorised tobacco.
  - lines: RCP-024-L1 "Marlboro Gold pack" $11.5
  - policy: > Cigarettes, cigars, loose tobacco, vaping devices and e-liquids are not reimbursable. This is a high exception.
- review signal **MCC-02** (`merchant-category-risk.md`) — MCC 5411 is a medium-risk merchant category

## RCP-025 — FLAG

Gasthaus Zur Linde (MCC 5812) · Meals - Individual · EMEA · 35.0 EUR = $37.8 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-025-L1 | Schweinebraten mit Knoedel (en: Roast pork with dumplings) | 19.98 | food_beverage | False | 0.9 |
| RCP-025-L2 | Weisswein 0,2l (en: White wine 0.2l) | 14.04 | alcohol | True | 0.9 |
| RCP-025-L3 | Mineralwasser 0,5l (en: Mineral water 0.5l) | 3.78 | food_beverage | False | 0.9 |

Rules considered: ALC-01, ALC-02, ALC-03, DOC-02, DOC-03, DOC-04, MEAL-01, MEAL-02, REG-03, REG-04, REG-05, TIME-01, TIME-02, TIME-03, TIME-04, EXC-03

- **ALC-01** (high, `meals-and-entertainment-policy.md`) — ALC-01 (Alcohol requires a documented entertainment context) raises a high exception on 'Weisswein 0,2l' ($14.04): type='Meals - Individual', attendees=None: needs Client Entertainment with 2+ attendees.
  - lines: RCP-025-L2 "Weisswein 0,2l" $14.04
  - policy: > Alcohol is reimbursable only on a receipt declared as Client Entertainment that records an attendee count of two or more. Alcohol on any other receipt — an individual or team meal, or any receipt without an attendee count — is a high exception.
- superseded MEAL-01: replaced by REG-03 for EMEA employees

## RCP-026 — FLAG

Cornerstone Office Supply (MCC 5943) · Computer Equipment · GLOBAL · 343.99 USD = $343.99 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-026-L1 | 27-inch 4K UHD monitor | 329.0 | computer_accessory | False | 0.9 |
| RCP-026-L2 | HDMI cable 2m | 14.99 | computer_accessory | False | 0.9 |

Rules considered: TECH-02, DOC-02, DOC-03, REG-05, TIME-01, EXC-03

- **TECH-02** (medium, `technology-and-equipment-policy.md`) — TECH-02 (Peripherals under $200) raises a medium exception on '27-inch 4K UHD monitor' ($329.00): unit prices RCP-026-L1 $329.00, RCP-026-L2 $14.99 vs $200 per item; no pre-approval reference.
  - lines: RCP-026-L1 "27-inch 4K UHD monitor" $329.0
  - policy: > Computer accessories and peripherals — cables, adapters, docking stations, mice, keyboards, monitors, laptop stands, webcams — are reimbursable up to $200 per item, judged on the item's unit price in USD. Any accessory or peripheral above $200 requires a pre-approval reference (see EXC-02); without one it is a medium exception.

## RCP-027 — FLAG

Grandview Department Store (MCC 5311) · Travel - Other · GLOBAL · 86.0 USD = $86.0 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-027-L1 | Men's dress shirt | 68.0 | clothing | True | 0.9 |
| RCP-027-L2 | Dress socks 3-pack | 18.0 | clothing | True | 0.9 |

Rules considered: MCC-02, PERS-01, PERS-02, DOC-02, DOC-03, REG-05, TIME-01, TIME-02, TIME-04, EXC-03

- **PERS-02** (medium, `non-reimbursable-items.md`) — PERS-02 (Clothing and footwear) raises a medium exception on 'Men's dress shirt' ($68.00) and 'Dress socks 3-pack' ($18.00): clothing without a baggage_delay reference (ref kind: None).
  - lines: RCP-027-L1 "Men's dress shirt" $68.0; RCP-027-L2 "Dress socks 3-pack" $18.0
  - policy: > Clothing, footwear, and fashion accessories such as belts, ties and bags are not reimbursable; a medium exception. The same $150 baggage-delay exception applies: one $150 allowance per delay, shared between toiletries and clothing. Above it, the exception cites every line involved.
- review signal **MCC-02** (`merchant-category-risk.md`) — MCC 5311 is a medium-risk merchant category

## RCP-028 — REVIEW

Cornerhealth Pharmacy (MCC 5912) · Travel - Other · GLOBAL · 14.48 USD = $14.48 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-028-L1 | Ibuprofen 200mg 24ct | 8.99 | health_otc | False | 0.9 |
| RCP-028-L2 | Throat lozenges | 5.49 | health_otc | False | 0.9 |

Rules considered: MCC-02, HEALTH-01, DOC-02, DOC-03, REG-05, TIME-01, TIME-02, TIME-04, EXC-03

- review signal **MCC-02** (`merchant-category-risk.md`) — MCC 5912 is a medium-risk merchant category

## RCP-029 — REVIEW

Night Owl Diner (MCC 5812) · Meals - Individual · GLOBAL · 20.5 USD = $20.5 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-029-L1 | Western omelette | 14.0 | food_beverage | False | 0.9 |
| RCP-029-L2 | Coffee | 3.5 | food_beverage | False | 0.9 |
| RCP-029-L3 | Gratuity | 3.0 | service_fee | False | 0.9 |

Rules considered: DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-02, TIME-03, TIME-04, EXC-03

- review signal **TIME-01** (`transaction-pattern-rules.md`) — 02:14 local time at the merchant: between 00:00 and 05:00

## RCP-030 — REVIEW

Pier 9 Seafood (MCC 5812) · Meals - Individual · GLOBAL · 28.0 USD = $28.0 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-030-L1 | Fish tacos | 19.0 | food_beverage | False | 0.9 |
| RCP-030-L2 | Lemonade | 5.0 | food_beverage | False | 0.9 |
| RCP-030-L3 | Gratuity | 4.0 | service_fee | False | 0.9 |

Rules considered: DOC-02, DOC-03, MEAL-01, MEAL-02, REG-05, TIME-01, TIME-02, TIME-03, EXC-03

- review signal **TIME-02** (`transaction-pattern-rules.md`) — declared 'Meals - Individual' with no trip record

## RCP-031 — REVIEW

Lavandaria Central (MCC 7216) · Travel - Other · EMEA · 20.0 EUR = $21.6 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-031-L1 | Limpeza a seco - 2 camisas (en: Dry cleaning - 2 shirts) | 21.6 | laundry_service | False | 0.9 |

Rules considered: LAUNDRY-01, DOC-02, DOC-03, DOC-04, REG-04, REG-05, TIME-01, TIME-02, TIME-04, EXC-03

- **LAUNDRY-01** (low, `non-reimbursable-items.md`) — LAUNDRY-01 (Laundry and dry cleaning) raises a low exception on 'Limpeza a seco - 2 camisas' ($21.60): trip of 2 nights vs 4+ required.
  - lines: RCP-031-L1 "Limpeza a seco - 2 camisas" $21.6
  - policy: > Reimbursable only on trips of four or more nights, using the trip length on the receipt. On shorter trips, or on a receipt with no trip record, it is a low exception.

## RCP-032 — REVIEW

Figma Inc (MCC 5734) · Software · GLOBAL · 144.0 USD = $144.0 · attendees None

| line | description | USD | category | restricted | confidence |
|---|---|---|---|---|---|
| RCP-032-L1 | Figma Professional - annual seat | 144.0 | software_subscription | False | 0.9 |

Rules considered: TECH-04, DOC-02, DOC-03, REG-05, TIME-01, EXC-03

- **TECH-04** (low, `technology-and-equipment-policy.md`) — TECH-04 (Software subscriptions) raises a low exception on 'Figma Professional - annual seat' ($144.00): software_subscription without a manager_approval reference (ref kind: None).
  - lines: RCP-032-L1 "Figma Professional - annual seat" $144.0
  - policy: > Any software or SaaS subscription on an expense report requires a manager approval reference (see EXC-02). Without one this is a low exception.
