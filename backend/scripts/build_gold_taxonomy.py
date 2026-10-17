"""
Скрипт извлечения эталонной таксономии и словарей М.Видео из skus.pkl.
Извлекает:
1. Официальные бренды (vendors)
2. Официальные маппинги цветов (Цвет_search -> Цвет)
3. Частотные атрибуты по ключевым категориям
"""
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

print(f"Обработка {len(offers)} офферов...")

brands = Counter()
colors_map = Counter()
cat_counter = Counter()

for o in offers:
    v = o.get('vendor')
    if v and isinstance(v, str):
        brands[v.strip()] += 1
    
    cid = o.get('categories', {}).get('categoryId') if isinstance(o.get('categories'), dict) else None
    if cid and cid in cat_map:
        cat_counter[cat_map[cid]] += 1

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

    if c_raw and c_canon:
        colors_map[(c_raw, c_canon)] += 1

print(f"\n1. Найдено уникальных брендов М.Видео: {len(brands)}")
print("Топ-25 брендов:")
for b, cnt in brands.most_common(25):
    print(f"  {b:<25}: {cnt}")

print(f"\n2. Найдено уникальных пар нормализации цветов (alias -> canon): {len(colors_map)}")
print("Топ-25 маппингов цветов:")
for (raw, canon), cnt in colors_map.most_common(25):
    print(f"  {raw:<30} -> {canon:<15} ({cnt} раз)")

print(f"\n3. Топ-15 категорий каталога по количеству товаров:")
for cname, cnt in cat_counter.most_common(15):
    print(f"  {cname:<35}: {cnt}")
