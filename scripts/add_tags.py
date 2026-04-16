"""给现有 flashcards.json 补充 tag 字段"""
import json
from pathlib import Path

TAG_MAP = {
    "Shameless-S02E01": "影视剧",
    "基础口语": "日常生活",
}

def main():
    fp = Path("e:/Outsidework/EnglishStudy/server/data/flashcards.json")
    cards = json.loads(fp.read_text(encoding="utf-8"))
    
    updated = 0
    for card in cards:
        cat = card.get("category", "基础口语")
        old_tag = card.get("tag")
        new_tag = TAG_MAP.get(cat, "日常生活")
        if old_tag != new_tag:
            card["tag"] = new_tag
            updated += 1
    
    fp.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done. Updated {updated}/{len(cards)} cards with tags.")

if __name__ == "__main__":
    main()
