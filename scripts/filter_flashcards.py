"""
filter_flashcards.py
从提取的对话文本中筛选适合闪卡的句子

筛选规则（排除以下情形）：
1. 英文少于 5 个词 → 太短
2. 纯感叹词 / 单词句 (Shit/Fuck/Yes/No/What 等)
3. 强上下文依赖：以 He/She/They/It/That/This/We/You 开头且这些代词指代不明的
4. 只包含人名呼叫的句子
5. 数字或密码类句子

保留：
- 有实际表达意义的完整句子 (≥ 5 词)
- 能独立理解的实用短句
- 包含常用口语表达、惯用搭配的句子
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "scripts/output/Shameless-S02E01_dialogues.txt"
OUT = ROOT / "scripts/output/Shameless-S02E01_flashcards.txt"

# 感叹词/独立词（单独出现时跳过）
PURE_EXCLAMATIONS = {
    "shit", "fuck", "damn", "hell", "crap", "christ", "jesus",
    "yes", "no", "okay", "ok", "alright", "right", "sure", "really",
    "wow", "hey", "hi", "bye", "what", "why", "how", "where", "when",
    "go", "stop", "wait", "now", "again", "move", "done", "fine",
    "great", "good", "bad", "cool", "nice", "please", "thanks", "thank",
    "sorry", "excuse", "exactly", "absolutely", "definitely",
}

# 强上下文依赖的开头词（这些词用于逻辑衔接，脱离上下文没意义）
CONTEXT_STARTERS = {
    "but", "and", "so", "then", "because", "because", "although",
    "however", "anyway", "besides", "meanwhile", "therefore",
    "otherwise", "furthermore", "moreover", "yet", "still",
    "well,", "yeah,", "no,", "yes,",  # 接续语气词
}

# 仅由人名/称呼构成（简单角色名判断）
NAMES_ONLY_PATTERN = re.compile(
    r"^[A-Z][a-z]+[\.,!?]?\s*(-\s*[A-Z][a-z]+[\.,!?]?)*[!?]?$"
)

def count_words(text: str) -> int:
    return len(text.split())

def is_too_short(en: str) -> bool:
    """少于 5 个词"""
    return count_words(en) < 5

def is_pure_exclamation(en: str) -> bool:
    """纯感叹词句"""
    cleaned = re.sub(r"[^a-zA-Z\s]", "", en).strip().lower()
    words = cleaned.split()
    if not words:
        return True
    if len(words) == 1 and words[0] in PURE_EXCLAMATIONS:
        return True
    # 两词以内且都是感叹词
    if len(words) <= 2 and all(w in PURE_EXCLAMATIONS for w in words):
        return True
    return False

def is_lyrics_or_quote(en: str) -> bool:
    """歌词（星号包裹）"""
    return en.strip().startswith("*") and en.strip().endswith("*")

def is_incomplete(en: str) -> bool:
    """以省略号结尾——句子不完整"""
    return en.rstrip().endswith("...")

def is_pronoun_reference_unclear(en: str) -> bool:
    """
    以 him/her/them/him/it 等开头 + 短句，或者
    类似 "Never gonna get him out" 这种代词指代不明的句子
    （句子主语明显是对话里前文提到的人）
    """
    first_words = en.strip().lower().split()[:3]
    # "Never gonna get him/her..."
    if first_words and first_words[0] in ("never", "gonna", "gotta"):
        if any(w in first_words for w in ("him", "her", "them", "it")):
            return True
    # 句子中 he/she 出现在开头且无引号或从句补充
    if first_words and first_words[0] in ("he", "she"):
        # 如果只是短句且没有充分补充
        if count_words(en) < 8:
            return True
    return False

def is_strong_context_dependent(en: str) -> bool:
    """强上下文依赖：以衔接词开头，脱离上下文不知所云"""
    first_word = en.strip().lower().split()[0].rstrip(",.!?") if en.strip() else ""
    # 衔接词开头
    if first_word in CONTEXT_STARTERS:
        return True
    # "That's/That was/That's what..." 等强指代
    if re.match(r"^(that|those|this|these|it|they)\s", en.strip(), re.I):
        # 允许 "That's a" "This is a" 之类的一般陈述短句
        if not re.match(r"^(that|this|it|they)\s+(is|are|was|were|'s|would|could|can|will|has|have)\b", en.strip(), re.I):
            return True
    # 代词指代不明
    if is_pronoun_reference_unclear(en):
        return True
    return False

def is_names_only(en: str) -> bool:
    """基本上只有人名呼叫"""
    # 去标点后若只有大写开头的单个词
    stripped = en.strip().rstrip("!?.,")
    # 单个首字母大写的词（可能是人名）
    if re.match(r"^[A-Z][a-z!]+$", stripped):
        return True
    # 连呼两个人名  "Frank! Karen!"
    if re.match(r"^[A-Z][a-z]+!?\s+[A-Z][a-z]+!?$", stripped):
        return True
    return False

def has_practical_value(en: str) -> bool:
    """是否包含有实用学习价值的词汇或表达"""
    # 包含动词性结构（简单判断：含有 be/have/do/make/get/go/come/want/need/like/think/know/say/tell 等）
    useful_verbs = r"\b(is|are|was|were|have|has|had|do|does|did|make|get|go|come|want|need|like|think|know|say|tell|take|give|put|see|look|feel|seem|become|happen|try|let|keep|start|stop|show|play|run|turn|ask|work|move|live|buy|sell|pay|spend|lose|win|find|bring|help|leave|hold|call|wait|sit|stand|hear|learn|grow|cut|read|write|eat|drink|sleep|wake)\b"
    if re.search(useful_verbs, en, re.I):
        return True
    # 含有常用惯用语结构
    if re.search(r"\b(going to|have to|want to|need to|able to|used to|supposed to)\b", en, re.I):
        return True
    return False

def is_good_flashcard(en: str, zh: str) -> tuple[bool, str]:
    """
    判断是否适合做闪卡
    返回 (是否保留, 排除原因)
    """
    en = en.strip()
    zh = zh.strip()

    if not en or not zh:
        return False, "空行"

    if is_too_short(en):
        return False, f"太短({count_words(en)}词)"

    if is_pure_exclamation(en):
        return False, "纯感叹词"

    if is_lyrics_or_quote(en):
        return False, "歌词/引用"

    if is_incomplete(en):
        return False, "句子不完整"

    if is_names_only(en):
        return False, "只有人名"

    if is_strong_context_dependent(en):
        return False, "强上下文依赖"

    if not has_practical_value(en):
        return False, "实用价值低"

    return True, ""


def main():
    lines = SRC.read_text(encoding="utf-8").strip().splitlines()

    kept = []
    rejected_reasons = {}

    for line in lines:
        if "\t" not in line:
            continue
        parts = line.split("\t", 1)
        en, zh = parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""

        ok, reason = is_good_flashcard(en, zh)
        if ok:
            kept.append(f"{en}\t{zh}")
        else:
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    # 输出统计
    print(f"原始对话数: {len(lines)}")
    print(f"保留闪卡数: {len(kept)}")
    print(f"排除明细:")
    for reason, count in sorted(rejected_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count} 条")

    # 写入文件
    OUT.write_text("\n".join(kept), encoding="utf-8")
    print(f"\n✅ 已写入: {OUT}")


if __name__ == "__main__":
    main()
