"""Core orchestration loop: schedule → search → filter → reply → state update."""

import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from src.browser import BrowserConfig, search_platform, post_reply_engine
from src.llm import PostContext, ReplyGenerator
from src.platforms.base import PlatformConfig
from src.platforms.youtube import YouTubePlatform
from src.platforms.facebook import FacebookPlatform
from src.platforms.instagram import InstagramPlatform
from src.platforms.lihkg import LIHKGPlatform
from src.platforms.xiaohongshu import XiaohongshuPlatform
from src.platforms.x import XPlatform
from src.platforms.linkedin import LinkedInPlatform
from src.state import StateManager

PLATFORM_CLASSES = {
    "youtube": YouTubePlatform,
    "facebook": FacebookPlatform,
    "instagram": InstagramPlatform,
    "lihkg": LIHKGPlatform,
    "xiaohongshu": XiaohongshuPlatform,
    "x": XPlatform,
    "linkedin": LinkedInPlatform,
}


class Orchestrator:
    """Main orchestrator that runs the full monitoring + reply pipeline."""

    def __init__(self, config: dict, keywords: dict):
        self.config = config
        self.keywords = keywords
        self.state = StateManager(
            db_path=config.get("database", {}).get("path", "./data/state.db")
        )
        self.browser_config = self._build_browser_config()
        self.reply_gen = self._build_reply_generator()
        self.enabled_platforms = self._init_platforms()

        logger.info(
            f"Orchestrator ready: engine={self.browser_config.engine}, "
            f"dry_run={config.get('dry_run', False)}, "
            f"platforms={list(self.enabled_platforms.keys())}"
        )

    def _build_browser_config(self) -> BrowserConfig:
        bc = self.config.get("browser", {})
        engine = bc.get("engine") or "playwright"
        return BrowserConfig(
            engine=engine,
            mode=bc.get("mode", "local"),
            headed=bc.get("headed", False),
            profile_dir=bc.get("profile_dir", "./data/profiles"),
            default_timeout=bc.get("default_timeout", 30),
            human_delay_min=bc.get("human_delay_min", 1.0),
            human_delay_max=bc.get("human_delay_max", 3.0),
            api_key=bc.get("api_key", ""),
        )

    def _build_reply_generator(self) -> ReplyGenerator:
        llm_cfg = self.config.get("llm", {})
        return ReplyGenerator(
            api_key=llm_cfg.get("api_key", ""),
            base_url=llm_cfg.get("base_url", "https://openrouter.ai/api/v1"),
            model=llm_cfg.get("model", "deepseek/deepseek-chat"),
            temperature=llm_cfg.get("temperature", 0.7),
            max_tokens=llm_cfg.get("max_tokens", 600),
        )

    def _init_platforms(self) -> dict:
        """Initialize enabled platform handlers sorted by priority.
        Skips platforms with no stored browser profile."""
        platforms_cfg = self.config.get("platforms", {})
        limits = self.config.get("limits", {})
        max_posts = limits.get("max_posts_per_platform", 3)
        keywords_en = self.keywords.get("english", [])
        keywords_zh = self.keywords.get("chinese", [])
        profile_dir = self.browser_config.profile_dir

        enabled = {}
        for name, cls in PLATFORM_CLASSES.items():
            pcfg = platforms_cfg.get(name, {})
            if not pcfg.get("enabled", True):
                logger.info(f"Platform '{name}' is disabled, skipping")
                continue

            # Check profile is ready (user logged in successfully)
            profile_path = Path(profile_dir) / name
            ready_file = profile_path / ".ready"
            if not ready_file.exists():
                logger.info(
                    f"Platform '{name}': not ready (no .ready at {profile_path}) — "
                    f"skipping. Run: python scripts/setup_profiles.py {name}"
                )
                continue

            platform_config = PlatformConfig(
                name=name,
                enabled=True,
                domains=pcfg.get("domains", []),
                priority=pcfg.get("priority", 99),
                max_posts=max_posts,
            )
            enabled[name] = cls(
                config=platform_config,
                keywords_en=keywords_en,
                keywords_zh=keywords_zh,
                browser_config=self.browser_config,
            )

        # Sort by priority
        return dict(
            sorted(enabled.items(), key=lambda x: x[1].config.priority)
        )

    def run_once(self) -> dict:
        """Execute one complete monitoring + reply cycle.

        Returns a summary dict of actions taken.
        """
        dry_run = self.config.get("dry_run", False)
        llm_cfg = self.config.get("llm", {})
        limits = self.config.get("limits", {})
        max_age_hours = limits.get("post_max_age_hours", 48)
        max_posts = limits.get("max_posts_per_platform", 3)

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "platforms_scanned": 0,
            "posts_found": 0,
            "replies_generated": 0,
            "replies_posted": 0,
            "errors": 0,
            "details": [],
        }

        if not self.enabled_platforms:
            logger.warning(
                "No platforms with profiles found. "
                "Run setup first: python scripts/setup_profiles.py <platform>"
            )
            return summary

        for name, platform in self.enabled_platforms.items():
            logger.info(f"--- Processing platform: {name} (priority={platform.config.priority}) ---")
            platform_result = {
                "platform": name,
                "posts_found": 0,
                "replied": 0,
                "skipped": 0,
                "error": None,
            }

            try:
                posts = self._search_platform(
                    platform, max_posts, max_age_hours, llm_cfg
                )
                platform_result["posts_found"] = len(posts)
                summary["posts_found"] += len(posts)
                logger.info(f"  Found {len(posts)} posts on {name}")

                for post in posts:
                    result = self._process_post(post, platform, dry_run)
                    if result == "replied":
                        platform_result["replied"] += 1
                        summary["replies_posted"] += 1
                    elif result == "skipped":
                        platform_result["skipped"] += 1

            except Exception as e:
                logger.error(f"  Error processing {name}: {e}")
                platform_result["error"] = str(e)
                summary["errors"] += 1

            summary["platforms_scanned"] += 1
            summary["details"].append(platform_result)

        return summary

    def _search_platform(self, platform, max_posts: int,
                         max_age_hours: int, llm_cfg: dict) -> list[dict]:
        """Search a platform and return extracted posts."""
        keywords = platform.pick_keywords(count=3)
        all_posts = []

        for keyword in keywords:
            logger.debug(f"  Search task for '{keyword}' on {platform.name}")

            try:
                raw_result = asyncio.run(
                    search_platform(
                        platform=platform.name,
                        keyword=keyword,
                        config=self.browser_config,
                        max_posts=max_posts,
                        max_age_hours=max_age_hours,
                        llm_api_key=llm_cfg.get("api_key", ""),
                        llm_base_url=llm_cfg.get("base_url", ""),
                        llm_model=llm_cfg.get("model", ""),
                    )
                )
                # search_platform already returns parsed list[dict]
                if isinstance(raw_result, list):
                    all_posts.extend(raw_result)
                else:
                    parsed = self._parse_search_result(str(raw_result), platform.name)
                    all_posts.extend(parsed)
            except Exception as e:
                logger.warning(f"  Search failed for keyword '{keyword}': {e}")
                continue

            logger.info(f"  Keyword '{keyword}': {len(all_posts)} posts so far")

            if len(all_posts) >= max_posts:
                break

            # Rate limit: wait between keyword searches
            wait = random.uniform(5, 10)
            logger.debug(f"  Rate-limit wait: {wait:.1f}s")
            time.sleep(wait)

        return all_posts[:max_posts]

    def _parse_search_result(self, raw: str, platform: str) -> list[dict]:
        """Attempt to parse browser-use output into structured post data."""
        if not raw:
            return []

        # Try to extract JSON array from the result
        try:
            # Look for JSON array in the result
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                json_str = raw[start:end]
                posts = json.loads(json_str)
                for p in posts:
                    p["platform"] = platform
                return posts
        except (json.JSONDecodeError, ValueError):
            pass

        # If no structured JSON, try line-by-line URL extraction
        logger.debug(f"  Could not parse JSON from {platform} result, trying text extraction")
        return self._fallback_parse(raw, platform)

    def _fallback_parse(self, raw: str, platform: str) -> list[dict]:
        """Fallback parsing when JSON extraction fails."""
        posts = []
        lines = raw.strip().split("\n")
        current = {}

        for line in lines:
            line = line.strip()
            if not line:
                if current and "text" in current:
                    current["platform"] = platform
                    current.setdefault("post_id", f"{platform}_{hash(current.get('text', ''))}")
                    current.setdefault("url", "")
                    current.setdefault("author", "unknown")
                    current.setdefault("language", "unknown")
                    current.setdefault("timestamp", "")
                    current.setdefault("engagement", "")
                    current.setdefault("media_description", "")
                    current.setdefault("is_replyable", True)
                    posts.append(current)
                current = {}
            elif ":" in line:
                key, _, val = line.partition(":")
                current[key.strip().lower().replace(" ", "_")] = val.strip()
            else:
                current["text"] = current.get("text", "") + " " + line

        if current and "text" in current:
            current["platform"] = platform
            current.setdefault("post_id", f"{platform}_{hash(current.get('text', ''))}")
            current.setdefault("url", "")
            current.setdefault("author", "unknown")
            current.setdefault("language", "unknown")
            current.setdefault("timestamp", "")
            current.setdefault("engagement", "")
            current.setdefault("media_description", "")
            current.setdefault("is_replyable", True)
            posts.append(current)

        return posts

    def _process_post(self, post: dict, platform,
                      dry_run: bool) -> str:
        """Process a single post: check state, generate reply, optionally post.

        Returns: 'replied', 'skipped', or 'error'.
        """
        post_id = str(post.get("post_id", ""))
        url = str(post.get("url", ""))

        if not post_id:
            logger.warning("  Skipping post with no post_id")
            return "skipped"

        # Dedup check
        if self.state.is_already_replied(platform.name, post_id):
            logger.debug(f"  Already processed: {post_id}")
            return "skipped"

        # Skip if not replyable
        if not post.get("is_replyable", True):
            self.state.mark_skipped(platform.name, post_id, url, "not replyable")
            return "skipped"

        # Build PostContext and generate reply
        try:
            post_ctx = PostContext(
                platform=platform.name,
                post_url=url,
                author=str(post.get("author", "unknown")),
                post_text=str(post.get("text", "")),
                language=str(post.get("language", "unknown")),
                timestamp=str(post.get("timestamp", "")),
                engagement=str(post.get("engagement", "")),
                media_description=str(post.get("media_description", "")),
            )

            reply_text = self.reply_gen.generate_reply(post_ctx)
            logger.info(f"  Reply generated for {post_id}: {reply_text[:80]}...")

            if dry_run:
                logger.info(f"  [DRY RUN] Would post to {url}: {reply_text[:80]}...")
                self.state.mark_replied(
                    platform.name, post_id, url, reply_text, status="dry_run"
                )
                return "replied"

            # Post the reply via the selected engine
            result = asyncio.run(
                post_reply_engine(
                    platform=platform.name,
                    post_url=url,
                    reply_text=reply_text,
                    config=self.browser_config,
                    llm_api_key=self.config.get("llm", {}).get("api_key", ""),
                    llm_base_url=self.config.get("llm", {}).get("base_url", ""),
                    llm_model=self.config.get("llm", {}).get("model", ""),
                )
            )

            if "success" in str(result).lower():
                self.state.mark_replied(platform.name, post_id, url, reply_text)
                logger.success(f"  Reply POSTED on {platform.name}: {url}")
                return "replied"
            else:
                self.state.mark_error(platform.name, post_id, url, str(result))
                logger.error(f"  Reply FAILED on {platform.name}: {result}")
                return "error"

        except Exception as e:
            logger.error(f"  Error processing post {post_id}: {e}")
            self.state.mark_error(platform.name, post_id, url, str(e))
            return "error"

    def get_status(self) -> dict:
        """Get current status for reporting."""
        total = self.state.get_reply_count()
        return {
            "total_replies": total,
            "enabled_platforms": list(self.enabled_platforms.keys()),
            "recent": self.state.get_recent_replies(5),
        }
