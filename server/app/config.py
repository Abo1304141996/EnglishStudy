"""
配置管理模块
"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8888
    debug: bool = False

    # 存储后端: json (默认) | postgres (后续)
    storage_backend: str = "json"

    # 数据路径
    data_dir: str = "./data"

    # 日志配置
    log_level: str = "INFO"

    # === LLM 配置（预留） ===
    ark_api_key: Optional[str] = None
    llm_endpoint: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 便捷访问
settings = get_settings()

# 确保数据目录存在
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
