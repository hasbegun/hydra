"""
Configuration management for Garak Backend
Loads settings from environment variables and .env file
"""
import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8888

    # CORS Configuration
    cors_origins: str = "*"

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"
    log_file: str | None = None  # File path; None = console only
    log_max_bytes: int = 10_485_760  # 10 MB
    log_backup_count: int = 5

    # Garak Configuration
    garak_path: str | None = None
    garak_reports_dir: str | None = None  # Default: ~/.local/share/garak/garak_runs
    garak_service_url: str = "http://localhost:9090"  # Garak service container URL

    # Ollama Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model_cache_ttl: int = 300  # Cache TTL in seconds (5 minutes)

    # Database Configuration
    database_url: str | None = None  # e.g. postgresql://hydra:secret@postgres:5432/hydra

    # Object Storage Configuration
    storage_backend: str = "local"  # "local" or "minio"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "hydra"
    minio_secret_key: str = ""  # Set via MINIO_SECRET_KEY env var or .env
    minio_bucket: str = "hydra-reports"
    minio_secure: bool = False  # Use TLS for Minio connections

    # API Configuration
    max_concurrent_scans: int = 5

    # Tenant Configuration
    tenant_mode: str = "single"  # "single" (no auth) or "multi" (Anima JWT required)

    # Redis Configuration
    redis_url: str = "redis://redis:6379/0"          # Broker (task queue)
    redis_result_url: str = "redis://redis:6379/1"   # Result backend

    @property
    def garak_reports_path(self) -> Path:
        """Get the garak reports directory path"""
        if self.garak_reports_dir:
            return Path(self.garak_reports_dir)
        return Path.home() / ".local" / "share" / "garak" / "garak_runs"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()
