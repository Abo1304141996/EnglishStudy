"""
存储模块
"""
from .factory import get_storage, close_storage
from .base import BaseStudyStorage

__all__ = [
    "get_storage",
    "close_storage",
    "BaseStudyStorage",
]
