"""
存储管理器工厂
根据配置自动选择合适的存储后端
"""
import logging
from typing import Optional

from app.storage.base import BaseStudyStorage

logger = logging.getLogger(__name__)

# 全局单例
_storage: Optional[BaseStudyStorage] = None


async def get_storage() -> BaseStudyStorage:
    """获取存储管理器单例

    根据环境变量自动选择后端：
    - STORAGE_BACKEND=json (默认) → JSON 文件存储
    - STORAGE_BACKEND=postgres   → PostgreSQL 存储（后续）
    """
    global _storage

    if _storage is None:
        _storage = await _create_storage()

    return _storage


async def _create_storage() -> BaseStudyStorage:
    """创建存储管理器实例"""
    import os

    backend = os.getenv("STORAGE_BACKEND", "json").lower()

    if backend == "postgres":
        # 后续实现 PostgreSQL 后端
        logger.warning("PostgreSQL backend not yet implemented, falling back to JSON")
        return await _create_json_storage()
    else:
        return await _create_json_storage()


async def _create_json_storage() -> BaseStudyStorage:
    """创建 JSON 文件存储"""
    from app.storage.json_backend import JSONStudyStorage

    storage = JSONStudyStorage()
    await storage.initialize()

    logger.info("Using JSONStudyStorage (file storage)")
    return storage


async def close_storage() -> None:
    """关闭存储管理器"""
    global _storage

    if _storage:
        await _storage.close()
        _storage = None
        logger.info("Storage closed")
