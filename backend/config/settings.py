"""
Central configuration loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Azure OpenAI (Microsoft Foundry) ---
    AZURE_OPENAI_API_KEY: str      = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT: str     = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_VERSION: str  = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

    # Deployment names — set in Foundry Studio, not model names
    AZURE_DEPLOYMENT_SMALL: str    = os.getenv("AZURE_DEPLOYMENT_SMALL", "gpt-4o-mini")
    AZURE_DEPLOYMENT_MEDIUM: str   = os.getenv("AZURE_DEPLOYMENT_MEDIUM", "o3-mini")
    AZURE_DEPLOYMENT_LARGE: str    = os.getenv("AZURE_DEPLOYMENT_LARGE", "gpt-4o")

    # --- Routing thresholds ---
    ROUTER_SMALL_MAX: float                = float(os.getenv("ROUTER_SMALL_MAX", "0.35"))
    ROUTER_MEDIUM_MAX: float               = float(os.getenv("ROUTER_MEDIUM_MAX", "0.65"))
    ROUTER_CONFIDENCE_BUMP_THRESHOLD: float = float(
        os.getenv("ROUTER_CONFIDENCE_BUMP_THRESHOLD", "0.60")
    )

   # --- Azure SQL ---
    AZURE_SQL_SERVER:   str = os.getenv("AZURE_SQL_SERVER", "")
    AZURE_SQL_DATABASE: str = os.getenv("AZURE_SQL_DATABASE", "")
    AZURE_SQL_USERNAME: str = os.getenv("AZURE_SQL_USERNAME", "")
    AZURE_SQL_PASSWORD: str = os.getenv("AZURE_SQL_PASSWORD", "")


settings = Settings()