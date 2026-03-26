"""Environment-based configuration for the Olympus backend."""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache

ENV_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")

class Settings(BaseSettings):
    # LLM
    openai_api_key: str = ""
    agent_model: str = "gpt-5-mini"
    agent_temperature: float = 0.1

    # Database
    database_url: str = "postgresql+asyncpg://agent_cp:agent_cp_pass@localhost:5432/agent_control_plane"
    database_url_sync: str = "postgresql://agent_cp:agent_cp_pass@localhost:5432/agent_control_plane"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Agent
    shell_working_dir: str = ".."

    model_config = {"env_file": ENV_FILE_PATH, "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
