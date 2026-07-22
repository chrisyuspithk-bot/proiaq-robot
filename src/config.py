"""Configuration management — merges config.yaml + .env + defaults."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_CONFIG = CONFIG_DIR / "config.yaml"
KEYWORDS_CONFIG = CONFIG_DIR / "keywords.yaml"


def _resolve_env(value: str) -> str:
    """Resolve ${VAR} placeholders in string values."""
    if isinstance(value, str):
        pattern = re.compile(r"\$\{(\w+)\}")
        for match in pattern.findall(value):
            env_val = os.getenv(match, "")
            value = value.replace(f"${{{match}}}", env_val)
        return value
    return value


def _resolve_dict(d: dict) -> dict:
    """Recursively resolve env vars in a dict."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _resolve_dict(v)
        elif isinstance(v, str):
            result[k] = _resolve_env(v)
        else:
            result[k] = v
    return result


def _merge_env_overrides(config: dict) -> dict:
    """Override config values from environment variables where applicable."""
    overrides = {
        "llm": {
            "api_key": os.getenv("LLM_API_KEY"),
            "base_url": os.getenv("LLM_BASE_URL"),
            "model": os.getenv("LLM_MODEL"),
        },
        "browser": {
            "mode": os.getenv("BROWSER_USE_MODE"),
            "headed": os.getenv("BROWSER_HEADED"),
            "profile_dir": os.getenv("CHROME_PROFILE_DIR"),
        },
        "scheduler": {
            "mode": os.getenv("SCHEDULE_MODE"),
        },
        "limits": {
            "max_posts_per_platform": _parse_int(os.getenv("MAX_POSTS_PER_PLATFORM")),
            "post_max_age_hours": _parse_int(os.getenv("POST_MAX_AGE_HOURS")),
            "post_max_age_days": _parse_int(os.getenv("POST_MAX_AGE_DAYS")),
        },
        "dry_run": _parse_bool(os.getenv("DRY_RUN")),
        "database": {
            "path": os.getenv("SQLITE_DB_PATH"),
        },
        "logging": {
            "level": os.getenv("LOG_LEVEL"),
            "dir": os.getenv("LOG_DIR"),
        },
    }
    for section, vals in overrides.items():
        if section not in config:
            config[section] = {}
        if isinstance(vals, dict):
            for k, v in vals.items():
                if v is not None:
                    config[section][k] = v
        elif vals is not None:
            config[section] = vals
    return config


def _parse_int(val: str | None) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _parse_bool(val: str | None) -> bool | None:
    if val is None:
        return None
    return val.strip().lower() in ("true", "1", "yes")


def load_config() -> dict[str, Any]:
    """Load and merge configuration from YAML and environment."""
    with open(DEFAULT_CONFIG) as f:
        config = yaml.safe_load(f)
    config = _resolve_dict(config)
    config = _merge_env_overrides(config)
    return config


def load_keywords() -> dict[str, Any]:
    """Load keyword sets from keywords.yaml."""
    with open(KEYWORDS_CONFIG) as f:
        return yaml.safe_load(f)
