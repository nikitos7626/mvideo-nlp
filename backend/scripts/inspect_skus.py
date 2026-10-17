import pickle
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("Loading skus.pkl...")
with open(r'c:\Users\nikit\Downloads\cu_ws\skus.pkl', 'rb') as f:
    data = pickle.load(f)

offers = data['yml_catalog']['shop']['offers']['offer']
categories = data['yml_catalog']['shop']['categories']['category']
cat_map = {c['@id']: c['#text'] for c in categories}

print(f"Total offers: {len(offers)}")

# Ищем смартфоны, пылесосы, ноутбуки, телевизоры
queries = [
    ("Смартфон", lambda name: "смартфон apple iphone" in name or "смартфон samsung galaxy" in name),
    ("Ноутбук", lambda name: "ноутбук" in name and ("asus" in name or "apple" in name or "lenovo" in name)),
    ("Пылесос", lambda name: "пылесос" in name and ("робот" in name or "dreame" in name or "xiaomi" in name)),
]

for label, predicate in queries:
    print(f"\n==================== {label} ====================")
    matched = None
    for o in offers:
        name = (o.get('name') or '').lower()
        if predicate(name):
            matched = o
            break
    
    if matched:
        cid = matched.get('categories', {}).get('categoryId')
        cname = cat_map.get(cid, "Неизвестно")
        print(f"Категория: {cname} (ID: {cid})")
        print(f"Товар: {matched.get('name')}")
        print(f"Vendor: {matched.get('vendor')}")
        print(f"Model: {matched.get('model')}")
        print("Атрибуты M.Video:")
        params = matched.get('param', [])
        if isinstance(params, dict):
            params = [params]
        for p in params:
            name = p.get('@name')
            val = p.get('#text')
            unit = f" ({p.get('@unit')})" if '@unit' in p else ""
            if any(key in name.lower() for key in ['памят', 'экран', 'диагональ', 'процессор', 'цвет', 'аккумулятор', 'батаре', 'модель', 'серия', 'уборк', 'мощност']):
                print(f"  • {name}{unit}: {val}")
