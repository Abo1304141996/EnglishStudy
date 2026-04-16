import json
import re
from pathlib import Path

def parse_scene_txt(filepath: str, category_name: str):
    cards = []
    lines = Path(filepath).read_text(encoding='utf-8').strip().split('\n')
    current_scene = "默认场景"
    
    question = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("【场景"):
            current_scene = line
        elif line.startswith("中文："):
            question = line[3:].strip()
        elif line.startswith("英文：") and question:
            answer = line[3:].strip()
            cards.append({
                "category": category_name,
                "scene": current_scene,
                "question": question,
                "answer": answer
            })
            question = None
            
    return cards

def main():
    out_dir = Path("e:/Outsidework/EnglishStudy/server/data")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "flashcards.json"
    
    old_cards = []
    if json_path.exists():
        try:
            old_cards = json.loads(json_path.read_text(encoding='utf-8'))
        except Exception:
            pass
            
    # Process old cards to ensure they have category and scene
    processed_cards = []
    seen = set()
    for card in old_cards:
        if card.get('question') not in seen:
            if 'category' not in card:
                card['category'] = "基础口语"
            if 'scene' not in card:
                card['scene'] = "默认场景"
            processed_cards.append(card)
            seen.add(card.get('question'))
            
    # Parse new scene files
    new_cards = []
    scene1_path = "e:/Outsidework/EnglishStudy/scripts/output/scene_flashcards_part1.txt"
    scene2_path = "e:/Outsidework/EnglishStudy/scripts/output/scene_flashcards_part2.txt"
    
    if Path(scene1_path).exists():
        new_cards.extend(parse_scene_txt(scene1_path, "Shameless-S02E01"))
    if Path(scene2_path).exists():
        new_cards.extend(parse_scene_txt(scene2_path, "Shameless-S02E01"))
        
    start_id = len(processed_cards)
    added = 0
    
    for card in new_cards:
        if card['question'] not in seen:
            card['id'] = f"card_{start_id + added}"
            # Add timestamp if needed (Flashcard model does this ordinarily, but we can fake it)
            card['created_at'] = "2026-04-03T00:00:00.000000"
            processed_cards.append(card)
            seen.add(card['question'])
            added += 1

    json_path.write_text(json.dumps(processed_cards, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Migration completed. Total cards: {len(processed_cards)} (Added new: {added})")

if __name__ == "__main__":
    main()
