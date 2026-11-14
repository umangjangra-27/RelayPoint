"""RelayPoint Application Configuration.

Loads environment variables via Pydantic Settings, providing safe local defaults,
strict boundary validation, and protection against secret leakage in logs or representations.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core application settings.
    
    Attributes:
        APP_NAME: Name of the application service.
        APP_ENV: Deployment environment (development, test, production).
        APP_DEBUG: Toggle for debug logging and detailed diagnostic output.
        APP_HOST: Binding IP address for the local server.
        APP_PORT: Binding port number.
        API_VERSION: Semantic API version.
        DATABASE_PATH: Local filesystem path for the SQLite database file.
        CORS_ORIGINS: Allowed origins for cross-origin resource sharing.
        SECRET_KEY: Cryptographic key for session/security integrity.
        GITHUB_TOKEN: Optional Personal Access Token for GitHub API requests.
        GEMINI_API_KEY: Optional Google Gemini API key for knowledge synthesis.
        GEMINI_MODEL: Gemini model identifier.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "RelayPoint"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = Field(default=8000, ge=1, le=65535)
    API_VERSION: str = "0.1.0"

    # SQLite Database Location
    DATABASE_PATH: Union[str, Path] = "relaypoint.db"
    DATABASE_URL: Optional[str] = None

    # CORS origins (stored as list, supports comma-delimited strings from env)
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Secrets wrapped in SecretStr to prevent accidental leakage in logs/string formatting
    SECRET_KEY: SecretStr = SecretStr("change-me-in-production-use-a-secure-random-token")
    GITHUB_TOKEN: Optional[SecretStr] = None
    GEMINI_API_KEY: Optional[SecretStr] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Storage paths
    DATA_CACHE_DIR: Union[str, Path] = "./.cache"
    REPORT_OUTPUT_DIR: Union[str, Path] = "./generated_reports"

    # Ingestion Controls & Rate Limits
    MAX_COMMITS: int = Field(default=50, ge=1, le=500)
    MAX_ISSUES: int = Field(default=30, ge=1, le=500)
    MAX_PULL_REQUESTS: int = Field(default=30, ge=1, le=500)
    MAX_CONTENT_LENGTH: int = Field(default=8000, ge=500, le=50000)
    GITHUB_REQUEST_TIMEOUT: int = Field(default=15, ge=1, le=120)
    GIT_SUBPROCESS_TIMEOUT: int = Field(default=15, ge=1, le=120)

    # Gemini AI Synthesis & Context Controls
    GEMINI_REQUEST_TIMEOUT: int = Field(default=30, ge=5, le=180)
    GEMINI_MAX_RETRIES: int = Field(default=0, ge=0, le=5)
    MAX_CONTEXT_CHUNKS: int = Field(default=40, ge=5, le=200)
    MAX_PROMPT_CHARS: int = Field(default=35000, ge=1000, le=100000)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        """Convert comma-separated origin strings into a clean list of strings."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        """Validate known application environment stages."""
        allowed_environments = {"development", "test", "staging", "production"}
        lowered = value.strip().lower()
        if lowered not in allowed_environments:
            raise ValueError(
                f"Invalid APP_ENV: '{value}'. Allowed: {', '.join(sorted(allowed_environments))}"
            )
        return lowered

    def get_database_path(self) -> Path:
        """Resolve the SQLite database file path.
        
        Handles both raw file paths and sqlite:/// URLs.
        """
        if self.DATABASE_URL and self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "", 1)
            return Path(raw_path).expanduser().resolve()
        return Path(self.DATABASE_PATH).expanduser().resolve()

    def safe_summary(self) -> dict:
        """Return non-sensitive configuration summary suitable for health/diagnostics."""
        return {
            "app_name": self.APP_NAME,
            "app_env": self.APP_ENV,
            "app_debug": self.APP_DEBUG,
            "app_host": self.APP_HOST,
            "app_port": self.APP_PORT,
            "api_version": self.API_VERSION,
            "database_configured": bool(self.DATABASE_PATH or self.DATABASE_URL),
            "github_token_configured": self.GITHUB_TOKEN is not None and bool(self.GITHUB_TOKEN.get_secret_value().strip()),
            "gemini_api_key_configured": self.GEMINI_API_KEY is not None and bool(self.GEMINI_API_KEY.get_secret_value().strip()),
            "gemini_model": self.GEMINI_MODEL,
            "max_commits": self.MAX_COMMITS,
            "max_issues": self.MAX_ISSUES,
            "max_pull_requests": self.MAX_PULL_REQUESTS,
            "max_content_length": self.MAX_CONTENT_LENGTH,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()
