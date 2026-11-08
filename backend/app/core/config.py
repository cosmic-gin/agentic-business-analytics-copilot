from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
ProviderName = Literal["openai", "groq"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore", hide_input_in_errors=True,
    )

    app_mode: Literal["demo", "llm"] = "demo"
    app_require_access_password: bool = False
    app_access_password: SecretStr | None = Field(default=None, min_length=20)
    llm_provider: Literal["none", "openai", "groq"] = "none"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_input_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    openai_output_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_input_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    groq_output_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    database_path: Path = ROOT / "data" / "analytics.sqlite"
    frontend_dist: Path = ROOT / "frontend" / "dist"
    llm_report_path: Path = ROOT / "evals" / "reports" / "llm-local.json"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def llm_enabled(self) -> bool:
        key = {"openai": self.openai_api_key, "groq": self.groq_api_key}.get(self.llm_provider)
        return bool(key and key.get_secret_value().strip())

    @property
    def llm_model(self) -> str:
        return self.groq_model if self.llm_provider == "groq" else self.openai_model
