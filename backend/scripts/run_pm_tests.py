import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.services.pipeline import CascadedExtractionPipeline
from scripts.pm_cases import cases

p = CascadedExtractionPipeline(use_gliner=True)

for c in cases:
    res = p.process_card({"title": c["title"], "description": c["desc"]})
    print(f"=== Case {c['id']}: {c['title']} ===")
    print(f"Категория: {res['category']} | needs_review={res['needs_review']} | conf={res['overall_confidence']}")
    print(f"Missing: {res['missing']}")
    for pred in res['predictions']:
        print(f"  • {pred['attribute']:<16}: {pred['value']} [conf: {pred['confidence']}, src: {pred['source']}]")
    print("-" * 60)
