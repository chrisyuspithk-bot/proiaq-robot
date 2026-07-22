"""Base class for platform-specific handlers."""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from loguru import logger


@dataclass
class PlatformConfig:
    """Configuration for a single platform."""
    name: str
    enabled: bool
    domains: list[str]
    priority: int
    max_posts: int = 3


class BasePlatform(ABC):
    """Abstract base for platform-specific search and reply logic."""

    def __init__(self, config: PlatformConfig, keywords_en: list[str],
                 keywords_zh: list[str], browser_config):
        self.config = config
        self.keywords_en = keywords_en
        self.keywords_zh = keywords_zh
        self.browser_config = browser_config

    @property
    def name(self) -> str:
        return self.config.name

    def pick_keywords(self, count: int = 2) -> list[str]:
        """Pick a mix of English and Chinese keywords for search."""
        en_sample = random.sample(
            self.keywords_en,
            min(count // 2 + 1, len(self.keywords_en)),
        )
        zh_sample = random.sample(
            self.keywords_zh,
            min(count // 2 + 1, len(self.keywords_zh)),
        )
        combined = list(set(en_sample + zh_sample))
        random.shuffle(combined)
        return combined[:count]

    @abstractmethod
    def search_task(self, keyword: str, max_posts: int,
                    max_age_hours: int) -> str:
        """Return a browser-use task string for searching this platform."""
        ...

    @abstractmethod
    def reply_task(self, post_url: str, reply_text: str) -> str:
        """Return a browser-use task string for replying on this platform."""
        ...
