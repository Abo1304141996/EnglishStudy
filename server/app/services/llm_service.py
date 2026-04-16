"""
LLM 对话服务（预留）
后续用于：
- 解释英语表达的用法/语法
- 生成练习题
- 智能推荐复习卡片
"""
import logging

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 服务（预留）"""

    def __init__(self):
        self.available = False
        logger.info("LLMService initialized (not configured yet)")

    async def explain_expression(self, expression: str) -> dict:
        """解释某个英语表达的用法"""
        if not self.available:
            return {
                "success": False,
                "message": "LLM 服务尚未配置，请在 .env 中设置 ARK_API_KEY 和 LLM_ENDPOINT",
            }
        # 后续实现
        return {"success": False, "message": "功能开发中"}

    async def generate_practice(self, topic: str) -> dict:
        """生成练习题"""
        if not self.available:
            return {
                "success": False,
                "message": "LLM 服务尚未配置",
            }
        # 后续实现
        return {"success": False, "message": "功能开发中"}
