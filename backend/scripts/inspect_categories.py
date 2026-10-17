import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_parquet(r'C:\Users\nikit\Downloads\cu_ws\sku_desc.parquet')

categories = {
    'Смартфоны': ('смартфон', 'чехол|стекло|пленка|ремешок|уцен|восстановлен'),
    'Телевизоры': ('телевизор', 'пульт|кронштейн|кабель|подставка|уцен'),
    'Роботы-пылесосы': ('робот-пылесос', 'щетка|фильтр|салфетка|тряпка|уцен|восстановлен'),
    'Стиральные машины': ('стиральная машина', 'шланг|подставка|уцен|восстановлен'),
    'Холодильники': ('холодильник', 'полка|ручка|уцен|восстановлен'),
    'Ноутбуки': ('ноутбук', 'чехол|сумка|подставка|уцен|восстановлен'),
    'Смарт-часы': ('смарт-часы|умные часы|apple watch', 'ремешок|пленка|защитное|уцен'),
    'Игровые приставки': ('playstation|xbox series|nintendo switch', 'геймпад|джойстик|подписка|игра|чехол'),
    'Микроволновые печи': ('микроволновая печь', 'тарелка|кронштейн|уцен|восстановлен'),
    'Кофемашины': ('кофемашина', 'очиститель|таблетки|фильтр|капсулы|уцен|восстановлен'),
    'Беспроводные наушники': ('беспроводные наушники|наушники tws', 'чехол|амбушюр|кабель|уцен|восстановлен')
}

for cat, (pos_pat, neg_pat) in categories.items():
    m = df[df['title'].str.lower().str.contains(pos_pat, na=False)]
    if neg_pat:
        m = m[~m['title'].str.lower().str.contains(neg_pat, na=False)]
    if not m.empty:
        good_m = m[m['description'].str.len() > 200]
        sample = good_m.iloc[0] if not good_m.empty else m.iloc[0]
        
        print(f"### 📦 {cat}")
        print(f"- **SKU**: `{sample['sku_id']}`")
        print(f"- **Товар**: **{sample['title']}**")
        desc = str(sample['description']).replace('\r', '').replace('<br>', ' ').replace('<br/>', ' ').strip()
        # Clean multiple spaces
        desc = ' '.join(desc.split())
        print(f"- **Фрагмент описания**: \n  \"{desc[:350]}...\"\n")

