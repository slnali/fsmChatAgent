from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SOLUTION_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = SOLUTION_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=SOLUTION_ROOT / ".env", extra="ignore")

    anthropic_api_key: str = ""
    agent_model: str = "claude-sonnet-5-5"
    grader_model: str = "claude-sonnet-5-5"

    owner_database_url: str = "postgresql://fsm_owner:fsm_owner_local@localhost:5432/fsm"
    agent_ro_database_url: str = "postgresql://fsm_agent_ro:agent_ro_local@localhost:5432/fsm"
    app_database_url: str = "postgresql://fsm_app:app_local@localhost:5432/fsm"
    fsm_agent_ro_password: str = "agent_ro_local"
    fsm_app_password: str = "app_local"

    data_db_path: str = "data/data.db.gz"
    max_result_rows: int = 20
    max_agent_steps: int = 12
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def data_db_file(self) -> Path:
        path = Path(self.data_db_path)
        return path if path.is_absolute() else SOLUTION_ROOT / path

    def migration_variables(self) -> dict[str, str]:
        return {
            "fsm_agent_ro_password": self.fsm_agent_ro_password,
            "fsm_app_password": self.fsm_app_password,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
