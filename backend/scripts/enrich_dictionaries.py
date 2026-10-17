"""
Скрипт генерации эталонной таксономии и обогащения словарей из skus.pkl.
"""
import json
import os
import pickle
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

print("Загрузка skus.pkl...")
with open(r'c:\Users\nikit\Downloads\cu_ws\skus.pkl', 'rb') as f:
    data = pickle.load(f)

offers = data['yml_catalog']['shop']['offers']['offer']
categories = data['yml_catalog']['shop']['categories']['category']
cat_map = {c['@id']: c['#text'] for c in categories}

print(f"Анализ {len(offers)} офферов...")

# 1. Извлечение брендов
brand_counts = Counter()
# 2. Извлечение цветов (raw -> canon)
color_pairs = Counter()
# 3. Таксономия по категориям
category_attributes = {}

target_categories = {
    "smartphones": ["Смартфоны"],
    "laptops": ["Ноутбуки"],
    "tvs": ["Телевизоры", "Встраиваемый телевизор"],
    "vacuum_cleaners": ["Пылесосы вертикальные", "Пылесосы напольные", "Роботы-пылесосы"],
    "refrigerators": ["Встраиваемые холодильники", "Холодильники"],
    "headphones": ["Наушники", "Наушники игровые True Wireless", "Наушники для компьютеров"],
}

for cat_key in target_categories:
    category_attributes[cat_key] = Counter()

for o in offers:
    v = o.get('vendor')
    if v and isinstance(v, str):
        brand_counts[v.strip()] += 1

    cid = o.get('categories', {}).get('categoryId') if isinstance(o.get('categories'), dict) else None
    cname = cat_map.get(cid, "")

    # Определяем категорию
    matched_cat = None
    for k, names in target_categories.items():
        if any(n.lower() in cname.lower() for n in names):
            matched_cat = k
            break

    params = o.get('param', [])
    if isinstance(params, dict):
        params = [params]
    elif not isinstance(params, list):
        continue

    c_raw = None
    c_canon = None
    for p in params:
        if not isinstance(p, dict):
            continue
        pname = p.get('@name')
        ptext = p.get('#text')
        if not ptext or not isinstance(ptext, str):
            continue

        if pname == 'Цвет_search':
            c_raw = ptext.strip().lower()
        elif pname == 'Цвет':
            c_canon = ptext.strip().lower()

        if matched_cat and pname and not pname.endswith('_search') and pname not in ['Потратить бонусы', 'Продавец', 'Подборки', 'Топ коллекция']:
            category_attributes[matched_cat][pname] += 1

    if c_raw and c_canon and len(c_raw) < 40 and len(c_canon) < 30:
        color_pairs[(c_raw, c_canon)] += 1

# 1. Сохранение эталонного графа таксономии
gold_taxonomy = {}
for cat_key, counter in category_attributes.items():
    top_attrs = [attr for attr, cnt in counter.most_common(20)]
    gold_taxonomy[cat_key] = {
        "mvideo_categories": target_categories[cat_key],
        "top_official_attributes": top_attrs,
        "sample_counts": dict(counter.most_common(10))
    }

os.makedirs("data/taxonomies", exist_ok=True)
with open("data/taxonomies/mvideo_gold_taxonomy.json", "w", encoding="utf-8") as f:
    json.dump(gold_taxonomy, f, ensure_ascii=False, indent=2)
print("Сохранен граф таксономии в data/taxonomies/mvideo_gold_taxonomy.json")

# 2. Обогащение brands.csv
existing_brands = set()
brands_path = "backend/data/dictionaries/brands.csv"
if os.path.exists(brands_path):
    with open(brands_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 2:
                existing_brands.add(parts[0].lower().strip())

new_brands_added = 0
with open(brands_path, "a", encoding="utf-8") as f:
    # Берем бренды с встречаемостью от 3 раз (отсекаем мусор и опечатки)
    for b, cnt in brand_counts.most_common():
        if cnt < 3:
            break
        b_clean = b.strip()
        b_alias = b_clean.lower()
        if b_alias not in existing_brands and "," not in b_clean and len(b_clean) >= 2:
            f.write(f"{b_alias},{b_clean}\n")
            existing_brands.add(b_alias)
            new_brands_added += 1

print(f"Добавлено новых официальных брендов в brands.csv: {new_brands_added}")

# 3. Обогащение colors.csv
existing_colors = set()
colors_path = "backend/data/dictionaries/colors.csv"
if os.path.exists(colors_path):
    with open(colors_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 2:
                existing_colors.add(parts[0].lower().strip())

new_colors_added = 0
with open(colors_path, "a", encoding="utf-8") as f:
    # Берем пары цветов с частотой >= 5
    for (raw, canon), cnt in color_pairs.most_common():
        if cnt < 5:
            break
        if raw not in existing_colors and "," not in raw and "," not in canon and "/" not in canon:
            prio = min(95, 75 + cnt // 10)
            f.write(f"{raw},{canon},{prio}\n")
            existing_colors.add(raw)
            new_colors_added += 1

print(f"Добавлено новых официальных маппингов цветов в colors.csv: {new_colors_added}")
