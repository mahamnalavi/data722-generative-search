"""Build the evaluation query set (Phase 1 cases) with labelled answers.

WHO WROTE THE QUERIES: Claude (Anthropic), a different model family from the
app's answering model (gpt-oss on Groq) and the judge (Gemini), as the brief requires.
"Name" queries are generated programmatically from catalogue titles.

STYLES (Phase 1 asked for plain-language, function-based and vague queries, plus
out-of-catalogue checks):
  name        product-name searches, generated from titles: regular-store searches that must not get worse
  precise     a clear use ("something to separate egg whites from yolks")
  vague       a problem rather than a product ("my rotis go cold before everyone eats")
  constraint  a use plus budget and/or stock limits
  urdu        Roman Urdu or Urdu script
  no_match    out of the catalogue, or nothing fits the limits: the right answer is "no close match"
  trap        wording that points at the wrong product (e.g. "separator" for clothes)

LABELS: each query lists the relevant product TYPES; any product of that type which
also meets the stated limits counts as a correct answer. Queries with no correct
product are expected to return "no close match".

SPLIT: 30% dev (used for tuning thresholds and weights), 70% test (reported once),
stratified by style, fixed seed.

RUN:  python data/build_eval_set.py   ->   data/eval_queries.json
"""

import json
import random
from pathlib import Path

HERE = Path(__file__).parent
CAT = json.loads((HERE / "catalogue.json").read_text(encoding="utf-8"))
TYPES = {}
for p in CAT:
    TYPES.setdefault(p["product_type"], []).append(p)

# (query, relevant types, language, expected constraints, note)
PRECISE = [
    ("something to separate egg whites from yolks", ["egg_separator"]),
    ("slice potatoes really thin and even for chips", ["mandoline_slicer"]),
    ("crush garlic without chopping it", ["garlic_press", "mortar_pestle"]),
    ("scrape sticky dough off the counter", ["bench_scraper"]),
    ("dry lettuce after washing it", ["salad_spinner"]),
    ("take pakoras out of hot oil", ["spider_strainer"]),
    ("strain lumps out of a sauce", ["fine_mesh_strainer"]),
    ("flip rotis without burning my fingers", ["kitchen_tongs"]),
    ("grind whole spices at home", ["mortar_pestle"]),
    ("zest a lemon for baking", ["rasp_grater"]),
    ("open a jar lid that is stuck", ["jar_opener"]),
    ("check if chicken is cooked inside", ["food_thermometer"]),
    ("cut fresh coriander quickly", ["herb_scissors", "manual_chopper"]),
    ("make noodles out of vegetables", ["spiralizer"]),
    ("stop oil splashing everywhere while frying", ["splatter_screen"]),
    ("whip cream for a birthday cake", ["hand_mixer"]),
    ("find the wooden beam behind my wall before drilling", ["stud_finder"]),
    ("check that a picture frame is hanging straight", ["spirit_level"]),
    ("fix the tiny screws on my phone", ["precision_screwdriver"]),
    ("check whether a socket has current in it", ["voltage_tester", "multimeter"]),
    ("seal the gap around the bathtub", ["caulking_gun"]),
    ("protect my TV and fridge from voltage spikes", ["extension_board"]),
    ("hold two pieces of wood together while the glue dries", ["clamp"]),
    ("pick up a screw that fell behind the cupboard", ["pickup_tool"]),
    ("stop water leaking from a pipe thread", ["ptfe_tape"]),
    ("keep things tidy under the kitchen sink", ["under_sink_organizer"]),
    ("keep earrings and necklaces from getting tangled", ["jewelry_organizer"]),
    ("remember which tablets to take each day", ["medicine_box"]),
    ("a seat that also stores blankets inside", ["storage_ottoman"]),
    ("stand to hold the Quran while reading", ["rehal"]),
    ("raise my computer screen to eye level", ["monitor_riser", "standing_desk_converter"]),
    ("use my laptop comfortably in bed", ["lap_desk"]),
]

VAGUE = [
    ("my rotis go cold before everyone sits down to eat", ["hot_pot"]),
    ("the back corners of my kitchen cabinet are wasted", ["lazy_susan", "pantry_riser"]),
    ("milk keeps spilling over on the stove", ["boil_over_disc"]),
    ("my drawers are a jumble of small things", ["drawer_divider", "sock_organizer", "cutlery_tray"]),
    ("too many cables tangled behind the TV", ["cable_box", "cable_tie"]),
    ("I keep losing my keys at home", ["key_holder"]),
    ("my back hurts after long hours at the computer", ["office_chair", "footrest", "standing_desk_converter", "monitor_riser"]),
    ("my mother finds it hard to sit on the floor for namaz", ["prayer_chair"]),
    ("something traditional to sit on in the courtyard", ["mooda", "charpai"]),
    ("the kitchen sink drains really slowly", ["drain_auger", "plunger"]),
    ("guests are staying over and we have no spare bed", ["sofa_cum_bed", "charpai"]),
    ("my small flat has no room for a proper dining table", ["drop_leaf_table"]),
    ("plastic shopping bags are piling up in the kitchen", ["bag_dispenser"]),
    ("I want to cook with less oil", ["oil_dispenser"]),
    ("food gets lost at the back of my fridge", ["fridge_bins", "lazy_susan"]),
    ("the kids' room is too small for two beds", ["bunk_bed"]),
]

# expected constraints: (max_price or None, in_stock)
CONSTRAINT = [
    ("light for load shedding under Rs 1500", ["emergency_light"], (1500, False)),
    ("pressure cooker under 5000", ["pressure_cooker"], (5000, False)),
    ("tawa that is in stock", ["tawa"], (None, True)),
    ("onion chopper under 1000", ["manual_chopper"], (1000, False)),
    ("knife sharpener under 1500", ["knife_sharpener"], (1500, False)),
    ("shoe rack under 3000, in stock", ["shoe_rack"], (3000, True)),
    ("something to dry clothes on the balcony, max 2500", ["drying_stand"], (2500, False)),
    ("kitchen scale 2000 tak", ["kitchen_scale"], (2000, False)),
    ("drill for brick walls under 15000", ["cordless_drill", "drill_bits"], (15000, False)),
    ("study desk under 10,000", ["study_desk"], (10000, False)),
    ("storage for winter blankets under 2000, in stock", ["vacuum_bags", "under_bed_storage"], (2000, True)),
    ("mortar and pestle under 3000 in stock", ["mortar_pestle"], (3000, True)),
    ("sasta spice box 3000 tak", ["masala_dabba", "spice_rack"], (3000, False)),
]

URDU = [
    ("pyaz barik katne wali cheez", ["manual_chopper", "mandoline_slicer"], "roman_urdu"),
    ("anday ki zardi alag karne wala", ["egg_separator"], "roman_urdu"),
    ("roti garam rakhne ka dabba", ["hot_pot"], "roman_urdu"),
    ("lassi banane wali madhani", ["madhani"], "roman_urdu"),
    ("bijli jane par roshni ke liye", ["emergency_light", "headlamp"], "roman_urdu"),
    ("kapre sukhane ka stand", ["drying_stand"], "roman_urdu"),
    ("namaz ke liye kursi", ["prayer_chair"], "roman_urdu"),
    ("masalay rakhne ka dabba", ["masala_dabba", "spice_rack"], "roman_urdu"),
    ("jootay rakhne ki rack", ["shoe_rack", "shoe_cabinet", "over_door_organizer"], "roman_urdu"),
    ("chhat ka pankha saaf karne ke liye seedhi", ["step_ladder", "step_stool"], "roman_urdu"),
    ("پیاز کاٹنے والی مشین", ["manual_chopper", "mandoline_slicer"], "urdu"),
    ("دودھ ابلنے سے روکنے والی چیز", ["boil_over_disc"], "urdu"),
    ("قرآن رکھنے کا اسٹینڈ", ["rehal"], "urdu"),
]

NO_MATCH = [
    ("refrigerator", "out of catalogue"),
    ("split air conditioner 1.5 ton", "out of catalogue"),
    ("baby stroller", "out of catalogue"),
    ("prayer mat", "out of catalogue; near miss: prayer chair"),
    ("mosquito net for a bed", "out of catalogue"),
    ("gas heater for winter", "out of catalogue"),
    ("water filter for drinking water", "out of catalogue"),
    ("laptop bag", "out of catalogue; near miss: laptop table"),
    ("scanner for documents", "out of catalogue; near miss: wall scanner"),
    ("hair curling tongs", "out of catalogue; near miss: kitchen tongs"),
    ("office chair under Rs 10000", "nothing fits the budget (cheapest office chair is Rs 13,900)"),
    ("bean bag with filling under 5000", "only the cover is under 5000; it has no filling"),
    ("headlamp in stock", "the only headlamp is out of stock"),
]
NO_MATCH_CONSTRAINTS = {"office chair under Rs 10000": (10000, False), "bean bag with filling under 5000": (5000, False),
                        "headlamp in stock": (None, True)}

TRAP = [
    ("separator for my clothes in the drawer", ["drawer_divider", "sock_organizer"], "'separator' should not pull in the egg separator"),
    ("a stand for my plants", ["plant_stand"], "many products are 'stands'"),
    ("cover for a bean bag", ["bean_bag"], "must accept the cover-only listing"),
]

NAME_TYPES = ["pressure_cooker", "tawa", "karahi", "garlic_press", "salad_spinner", "kitchen_scale",
              "hand_mixer", "knife_sharpener", "cordless_drill", "spirit_level", "measuring_tape", "multimeter",
              "step_ladder", "hammer", "glue_gun", "shoe_rack", "dish_rack", "hangers", "laundry_basket",
              "shower_caddy", "office_chair", "bookcase", "tv_console", "bedside_table"]


def ids_for(types, cons):
    max_price, in_stock = cons
    out = []
    for t in types:
        assert t in TYPES, f"unknown product type {t}"
        for p in TYPES[t]:
            if max_price is not None and p["price_pkr"] > max_price:
                continue
            if in_stock and not p["in_stock"]:
                continue
            out.append(p["product_id"])
    return out


def build():
    rows = []

    def add(query, style, types, language="english", cons=(None, False), note=""):
        rel = ids_for(types, cons) if types else []
        rows.append({"query": query, "style": style, "language": language, "relevant_types": types,
                     "relevant_ids": rel, "expected_max_price": cons[0], "expected_in_stock": cons[1],
                     "expects_no_match": len(rel) == 0, "note": note})

    for t in NAME_TYPES:
        title = TYPES[t][0]["title"].split(",")[0].lower()
        add(title, "name", [t], note="generated from catalogue title")
    for q, types in PRECISE:
        add(q, "precise", types)
    for q, types in VAGUE:
        add(q, "vague", types)
    for q, types, cons in CONSTRAINT:
        add(q, "constraint", types, cons=cons)
    for q, types, lang in URDU:
        add(q, "urdu", types, language=lang)
    for q, note in NO_MATCH:
        add(q, "no_match", [], cons=NO_MATCH_CONSTRAINTS.get(q, (None, False)), note=note)
    for q, types, note in TRAP:
        add(q, "trap", types, note=note)

    # stratified 30/70 split
    rng = random.Random(722)
    for style in sorted({r["style"] for r in rows}):
        group = [r for r in rows if r["style"] == style]
        rng.shuffle(group)
        n_dev = max(1, round(0.3 * len(group)))
        for i, r in enumerate(group):
            r["split"] = "dev" if i < n_dev else "test"
    for i, r in enumerate(rows, start=1):
        r["qid"] = f"Q{i:03d}"
    return rows


if __name__ == "__main__":
    rows = build()
    (HERE / "eval_queries.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    from collections import Counter
    print(len(rows), "queries;", dict(Counter(r["style"] for r in rows)))
    print("split:", dict(Counter(r["split"] for r in rows)))
    print("expects no match:", sum(r["expects_no_match"] for r in rows))
