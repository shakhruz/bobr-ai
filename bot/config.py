"""Настройки из .env (без внешних зависимостей)."""
import os
from dataclasses import dataclass
from pathlib import Path


def load_env(path: str | Path = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Config:
    bot_token: str
    api_key: str
    model: str
    db_path: str
    effort: str


def get_config(require_secrets: bool = True) -> Config:
    load_env(Path(__file__).parent / ".env")
    cfg = Config(
        bot_token=os.environ.get("BOT_TOKEN", ""),
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        model=os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5-5",
        db_path=os.environ.get("DB_PATH") or "bobr.db",
        effort=os.environ.get("ANTHROPIC_EFFORT", "low"),
    )
    if require_secrets and (not cfg.bot_token or not cfg.api_key):
        raise SystemExit("Заполните BOT_TOKEN и ANTHROPIC_API_KEY в .env (см. .env.example)")
    return cfg
