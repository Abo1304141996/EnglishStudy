"""
AI 卡片解析与优化服务

调用豆包（OpenAI 兼容）LLM，把用户粘贴的零散英语句子转成情境化抽认卡。
"""
import json
import logging
import os
import re
from typing import List, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


CARD_SYSTEM_PROMPT = """【Role / 角色设定】
你是一个专业的英语语感与情境记忆训练专家。你的核心任务是将用户输入的"零散英语句子（原始积累）"转化为高效率的情境交互式抽认卡 (Flashcards)。

【Background / 背景理念】
语言的学习不能脱离语境。在真实的英语交流中，练习情感表达 (practicing emotional expression) 是至关重要的。当带有情感地说话时，英语听起来才会更加自然、鲜活。因此，抽认卡不仅要教翻译，更要在大脑中建立"真实生活场景/情绪"与"英语脱口而出"之间的强烈神经链接，让英语成为真实生活中的语言，而不仅仅是学习的科目。

【Workflow / 工作流】
1. 分析输入：仔细阅读用户提供的原始英语句子（可能包含中文翻译或仅仅是英文原句）。
2. 提取情境与情绪：深度分析该句子在真实母语者交流中适用的具体场景（如：职场、日常寒暄、极限情境等）以及说话者当下的情绪状态（如：愤怒、无奈、绝望、热血鼓励、平静等），将语言与真实生活紧密相连。
3. 格式化输出：严格按照下方【输出格式】生成卡片。绝对不要给出干瘪的直译。

【Rules / 生成规则】
- 卡片正面 (front) 的结构必须是：[具体的情绪或场景描述]：\"[贴切的中文口语翻译]\"用英语怎么说？
- 场景描述要求：必须生动、聚焦，能够瞬间唤起使用者的画面感（例如不能只写"表达无奈"，要写"向别人抱怨自己已经跌入人生谷底"）。
- 卡片背面 (back) 的结构必须是：[纯英文原句]（不需要多余的解释，保持简洁）。
- 如果用户输入文本中包含多个句子（用换行 / 句号 / 列表分隔），请逐句生成卡片。

【Examples / 少量样本提示】
输入: My life couldn't get any fucking worse.
输出:
front: 向别人抱怨自己已经跌入人生谷底：\"反正我的生活也不能更烂了\"用英语怎么说？
back: My life couldn't get any fucking worse.

输入: just lean all in and go for it.
输出:
front: 热血地鼓励他人毫无保留地投入行动：\"全力以赴，放手一搏吧\"用英语怎么说？
back: just lean all in and go for it.

输入: I am walking outside.
输出:
front: 一个人在外面散步，感受当下的平静时在脑海中对自己说：\"我正走在外面\"用英语怎么说？
back: I am walking outside.

【Output / 输出格式】
你必须**只输出一个 JSON 对象**，不要任何额外解释、Markdown 代码块标记或前后缀。结构如下：
{
  "cards": [
    { "front": "...", "back": "..." },
    { "front": "...", "back": "..." }
  ]
}
"""


REFINE_SYSTEM_PROMPT = """你是一个英语情境化抽认卡的优化助手。
用户会提供一张已有的抽认卡（front/back）以及修改意图，请按用户意图调整卡片，但保持以下规则：
- 卡片背面 (back) 应保留原英文句子（除非用户明确要求修改英文）。
- 卡片正面 (front) 必须是：[具体的情绪或场景描述]：\"[贴切的中文口语翻译]\"用英语怎么说？

只输出 JSON：{ "card": { "front": "...", "back": "..." } }，不要任何额外说明。
"""


def _extract_json(text: str) -> Optional[dict]:
    """从可能包含 markdown 代码块的文本中提取 JSON"""
    if not text:
        return None
    # 去除 ```json ``` 包裹
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    else:
        # 找最外层 { }
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except Exception as e:
        logger.warning(f"JSON parse failed: {e}; raw={candidate[:200]}")
        return None


class CardAIService:
    """通过豆包 LLM 解析/优化抽认卡"""

    def __init__(self):
        self.api_key = settings.ark_api_key
        self.endpoint = settings.ark_llm_endpoint
        if self.api_key:
            os.environ.setdefault("ARK_API_KEY", self.api_key)

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.endpoint)

    async def _call(self, system_prompt: str, user_text: str, max_tokens: int = 1500) -> str:
        """调用 LLM 并返回完整文本"""
        from arkitect.core.component.context.context import Context
        from arkitect.types.llm.model import ArkChatParameters

        ctx = Context(
            model=self.endpoint,
            parameters=ArkChatParameters(
                temperature=0.6,
                max_tokens=max_tokens,
            ),
        )
        await ctx.init()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

        full = ""
        try:
            stream = await ctx.completions.create(messages=messages, stream=True)
            async for chunk in stream:
                try:
                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)
                    content = getattr(delta, "content", None) if delta else None
                except Exception:
                    content = None
                if content:
                    full += content
        except Exception as e:
            logger.error(f"[CardAI] stream failed: {e}", exc_info=True)
            raise
        return full

    async def parse_cards(self, raw_text: str) -> List[Dict[str, str]]:
        """解析原始文本为卡片候选列表"""
        if not self.available:
            raise RuntimeError("LLM 未配置：请在 .env 中设置 ARK_API_KEY 和 ARK_LLM_ENDPOINT")
        text = await self._call(CARD_SYSTEM_PROMPT, raw_text, max_tokens=2000)
        data = _extract_json(text)
        if not data or not isinstance(data.get("cards"), list):
            logger.error(f"[CardAI] invalid response: {text[:500]}")
            raise RuntimeError("AI 返回的数据格式无效，请稍后重试或调整输入")
        cards = []
        for c in data["cards"]:
            front = (c.get("front") or "").strip()
            back = (c.get("back") or "").strip()
            if front and back:
                cards.append({"front": front, "back": back})
        return cards

    async def refine_card(
        self,
        front: str,
        back: str,
        instruction: str,
        original_source: Optional[str] = None,
    ) -> Dict[str, str]:
        """根据用户指令优化单张卡片"""
        if not self.available:
            raise RuntimeError("LLM 未配置")
        payload = {
            "current_card": {"front": front, "back": back},
            "user_instruction": instruction,
        }
        if original_source:
            payload["original_source"] = original_source
        user_text = json.dumps(payload, ensure_ascii=False)
        text = await self._call(REFINE_SYSTEM_PROMPT, user_text, max_tokens=800)
        data = _extract_json(text)
        if not data or not isinstance(data.get("card"), dict):
            raise RuntimeError("AI 返回数据格式无效")
        card = data["card"]
        return {
            "front": (card.get("front") or front).strip(),
            "back": (card.get("back") or back).strip(),
        }


_service: Optional[CardAIService] = None


def get_card_ai() -> CardAIService:
    global _service
    if _service is None:
        _service = CardAIService()
    return _service
