"""Frozen KEYWORD BASELINE classifier: the kind of system this project replaces (brief, Part 3).

A plain, ordered keyword table -> taxonomy category, matched on the lower-cased `description_raw` only.
First matching category wins; restricted categories are tried first (a "restricted words" matcher), then
the unrestricted ones; no match -> `other`. A non-itemized charge is `other` (the taxonomy says so).
No MCC, merchant, amount or context is used: that is the point of a keyword baseline.

Provenance: written ONLY from data/category-taxonomy.md (category names and "typical examples") plus
obvious common-sense words, in English and the most obvious words in es/fr/de/pt/ja. Written WITHOUT
looking at the answer line labels, receipt descriptions or their answers, and FROZEN before it was scored.
tests/test_evaluate.py pins a sha256 of KEYWORDS so any later edit is visible. Do not tune it to its score.
It is a pipeline-style module: it never imports the answer key.
"""
import re

# (category, keywords). Order matters: first match wins. Latin words match on word boundaries;
# Japanese (no spaces) matches as a substring.
KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # restricted
    ("alcohol", ("beer", "wine", "spirits", "cocktail", "corkage", "whisky", "whiskey", "vodka", "gin", "rum",
                 "tequila", "champagne", "prosecco", "sake", "lager", "ale", "bourbon", "liquor", "cerveza", "vino",
                 "licor", "bière", "vin", "alcool", "bier", "wein", "sekt", "schnaps", "cerveja", "vinho",
                 "ビール", "ワイン", "日本酒", "焼酎", "ウイスキー", "酒")),
    ("tobacco", ("cigarette", "cigarettes", "cigar", "cigars", "tobacco", "vape", "vaping", "e-cigarette",
                 "cigarrillo", "cigarrillos", "tabaco", "puro", "tabac", "zigarette", "zigaretten", "zigarre",
                 "tabak", "cigarro", "たばこ", "タバコ", "煙草")),
    ("gambling", ("casino", "casino chips", "betting", "bet", "lottery", "poker", "slot machine", "apuesta",
                  "lotería", "pari", "loterie", "wette", "lotto", "aposta", "loteria", "カジノ", "宝くじ")),
    ("gift_card", ("gift card", "giftcard", "prepaid card", "voucher", "tarjeta regalo", "tarjeta de regalo",
                   "carte cadeau", "carte-cadeau", "bon d'achat", "gutschein", "geschenkkarte", "cartão presente",
                   "vale-presente", "ギフトカード", "商品券", "プリペイドカード")),
    ("personal_electronics", ("headphones", "earbuds", "headset", "tablet", "ipad", "smartwatch", "smart watch",
                              "camera", "fitness tracker", "tracker", "airpods", "kindle", "e-reader", "charger",
                              "auriculares", "tableta", "cámara", "reloj inteligente", "cargador", "écouteurs",
                              "casque", "tablette", "appareil photo", "montre connectée", "chargeur", "kopfhörer",
                              "kamera", "ladegerät", "fones de ouvido", "câmera", "relógio inteligente",
                              "carregador", "ヘッドホン", "イヤホン", "タブレット", "カメラ", "スマートウォッチ", "充電器")),
    ("jewelry", ("jewelry", "jewellery", "bracelet", "necklace", "earrings", "watch", "joyería", "pulsera",
                 "collar", "reloj", "bijou", "bijoux", "collier", "montre", "schmuck", "armband", "halskette", "uhr",
                 "joia", "pulseira", "colar", "relógio", "ジュエリー", "ブレスレット", "ネックレス", "腕時計")),
    ("clothing", ("shirt", "t-shirt", "pants", "trousers", "jacket", "coat", "dress", "shoes", "socks",
                  "underwear", "belt", "tie", "apparel", "footwear", "sweater", "camisa", "pantalón", "chaqueta",
                  "zapatos", "calcetines", "ropa", "chemise", "pantalon", "veste", "chaussures", "chaussettes",
                  "vêtements", "cravate", "ceinture", "hemd", "hose", "jacke", "schuhe", "socken", "kleidung",
                  "krawatte", "gürtel", "calça", "jaqueta", "sapatos", "meias", "roupa", "gravata", "cinto",
                  "シャツ", "ズボン", "ジャケット", "靴", "靴下", "ネクタイ")),
    ("personal_care", ("toiletries", "shampoo", "toothpaste", "toothbrush", "deodorant", "cosmetics", "makeup",
                       "lotion", "razor", "haircut", "spa", "massage", "manicure", "champú", "pasta de dientes",
                       "desodorante", "corte de pelo", "masaje", "shampooing", "dentifrice", "déodorant",
                       "coupe de cheveux", "zahnpasta", "deo", "haarschnitt", "xampu", "creme dental",
                       "corte de cabelo", "massagem", "シャンプー", "歯磨き", "マッサージ", "スパ", "化粧品")),
    ("household_goods", ("detergent", "cleaning supplies", "cleaner", "paper towels", "kitchenware", "mug", "drinkware", "bedding",
                         "pillow", "towel", "décor", "dish soap", "sponge", "detergente", "toallas de papel",
                         "almohada", "taza", "détergent", "essuie-tout", "oreiller", "tasse", "waschmittel",
                         "küchenrolle", "kissen", "toalha de papel", "travesseiro", "caneca",
                         "洗剤", "キッチンペーパー", "枕", "マグ")),
    ("gift", ("gift", "gifts", "flowers", "bouquet", "gift basket", "greeting card", "branded merchandise",
              "flores", "ramo", "regalo", "cesta", "fleurs", "cadeau", "blumen", "geschenk", "presente",
              "花束", "フラワー", "ギフト", "贈答")),
    # unrestricted
    ("service_fee", ("service charge", "service fee", "gratuity", "tip", "delivery fee", "booking fee",
                     "convenience fee", "propina", "cargo por servicio", "pourboire", "frais de service",
                     "frais de livraison", "trinkgeld", "servicegebühr", "bedienung", "liefergebühr", "gorjeta",
                     "taxa de serviço", "taxa de entrega", "サービス料", "配送料", "チップ", "手数料")),
    ("laundry_service", ("laundry", "dry cleaning", "pressing", "ironing", "lavandería", "tintorería",
                         "planchado", "blanchisserie", "nettoyage à sec", "repassage", "wäscherei", "reinigung",
                         "bügeln", "lavanderia", "lavagem a seco", "ランドリー", "クリーニング")),
    ("health_otc", ("ibuprofen", "paracetamol", "acetaminophen", "aspirin", "tylenol", "advil", "medicine",
                    "medication", "lozenges", "cough drops", "throat", "antacid", "bandage", "band-aid",
                    "first aid", "allergy", "ibuprofeno", "aspirina", "medicamento", "tiritas", "botiquín",
                    "ibuprofène", "paracétamol", "aspirine", "médicament", "pastilles", "pansement",
                    "schmerztabletten", "medikament", "halstabletten", "pflaster", "hustenbonbons", "remédio",
                    "pastilha", "curativo", "薬", "のど飴", "絆創膏")),
    ("software_subscription", ("software", "license", "licence", "subscription", "saas", "licencia",
                               "suscripción", "abonnement", "logiciel", "lizenz", "abo", "licença", "assinatura",
                               "ソフトウェア", "ライセンス", "サブスクリプション")),
    ("computer_accessory", ("cable", "adapter", "dock", "docking", "mouse", "keyboard", "monitor", "usb", "hdmi",
                            "hub", "adaptador", "ratón", "teclado", "câble", "adaptateur", "souris", "clavier",
                            "écran", "kabel", "maus", "tastatur", "bildschirm", "cabo",
                            "ケーブル", "アダプタ", "マウス", "キーボード", "モニター")),
    ("office_supplies", ("stationery", "notebook", "pen", "pens", "paper", "printing", "print", "toner", "ink",
                         "stapler", "folder", "envelope", "shipping", "postage", "courier", "papelería",
                         "cuaderno", "bolígrafo", "papel", "impresión", "envío", "papeterie", "cahier", "stylo",
                         "papier", "impression", "envoi", "schreibwaren", "notizbuch", "stift", "druck", "versand",
                         "papelaria", "caderno", "caneta", "impressão", "envio", "文房具", "ノート", "ペン", "印刷")),
    ("lodging", ("room", "hotel", "lodging", "resort fee", "accommodation", "nightly rate", "lodging tax",
                 "occupancy tax", "habitación", "alojamiento", "chambre", "hôtel", "hébergement", "nuitée",
                 "taxe de séjour", "zimmer", "übernachtung", "kurtaxe", "quarto", "hospedagem", "diária",
                 "宿泊", "客室", "ホテル")),
    ("ground_transport", ("taxi", "uber", "lyft", "rideshare", "ride", "train", "metro", "subway", "bus",
                          "transit", "parking", "toll", "fuel", "gas", "gasoline", "petrol", "car rental",
                          "estacionamiento", "aparcamiento", "peaje", "gasolina", "combustible", "tren",
                          "stationnement", "péage", "essence", "carburant", "parken", "parkgebühr", "maut", "benzin",
                          "tankstelle", "zug", "bahn", "táxi", "estacionamento", "pedágio", "combustível", "trem",
                          "タクシー", "駐車", "電車", "ガソリン", "乗車")),
    ("airfare", ("flight", "airfare", "airline", "plane", "seat", "baggage", "bag fee", "checked bag", "boarding",
                 "ticket", "vuelo", "billete de avión", "asiento", "equipaje", "vol", "billet d'avion", "siège",
                 "bagage", "flug", "flugticket", "sitzplatz", "gepäck", "voo", "passagem aérea", "assento",
                 "bagagem", "航空券", "座席", "手荷物", "フライト")),
    ("food_beverage", ("meal", "lunch", "dinner", "breakfast", "coffee", "tea", "juice", "water", "soda",
                       "sandwich", "salad", "burger", "pizza", "snack", "snacks", "catering", "food", "chicken",
                       "fish", "steak", "soup", "dessert", "cake", "cookie", "menu", "appetizer", "entree",
                       "lemonade", "comida", "almuerzo", "cena", "desayuno", "café", "té", "agua", "refresco",
                       "jugo", "zumo", "ensalada", "pollo", "pescado", "postre", "menú", "repas", "déjeuner",
                       "dîner", "petit-déjeuner", "thé", "eau", "jus", "salade", "poulet", "poisson", "plat",
                       "essen", "mittagessen", "abendessen", "frühstück", "kaffee", "tee", "wasser", "saft", "salat",
                       "hähnchen", "fisch", "nachtisch", "menü", "refeição", "almoço", "jantar", "chá", "água",
                       "suco", "salada", "frango", "peixe", "sobremesa", "弁当", "ランチ", "定食", "コーヒー", "茶",
                       "水", "ジュース", "食事", "寿司", "ラーメン", "朝食", "昼食", "夕食")),
)


def _pattern(word: str) -> str:
    if word.isascii() or any(ch.isalpha() and ch.isascii() for ch in word):
        return r"(?<!\w)" + re.escape(word) + r"(?!\w)"
    return re.escape(word)  # Japanese: no word boundaries


_COMPILED = [(cat, re.compile("|".join(_pattern(w) for w in words))) for cat, words in KEYWORDS]


def classify_line(description: str) -> str:
    text = description.lower()
    return next((cat for cat, rx in _COMPILED if rx.search(text)), "other")


def classify(receipts: list[dict]) -> dict[str, str]:
    """line_id -> category, for run_engine(receipts, categories)."""
    return {li["line_id"]: "other" if not r["itemized"] else classify_line(li["description_raw"])
            for r in receipts for li in r["line_items"]}
