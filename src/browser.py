"""Browser-use wrapper — uses the real browser-use library API.

Supports:
- Local Playwright Chromium with persistent user profiles (so logins survive)
- Browser Use Cloud (stealth browsers) via `use_cloud=True`
- Any OpenAI-compatible LLM (DeepSeek, OpenRouter, etc.) via ChatOpenAI
"""

import random
import time
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass
class BrowserConfig:
    """Configuration for browser instances."""
    mode: str = "local"           # "local" or "cloud"
    headed: bool = False
    profile_dir: str = "./data/profiles"
    default_timeout: int = 30
    human_delay_min: float = 1.0
    human_delay_max: float = 3.0
    api_key: str = ""


@dataclass
class ExtractedPost:
    """Structured data extracted from a social media post."""
    platform: str
    post_id: str
    url: str
    author: str
    text: str
    language: str          # "en", "zh", "yue", "mixed"
    timestamp: str
    media_description: str = ""
    engagement: str = ""
    is_replyable: bool = True


class BrowserUseClient:
    """Builds platform-specific task strings for browser-use Agent execution.

    The task strings are natural-language instructions consumed by
    browser-use's Agent, which uses an LLM to drive the browser.

    Does NOT execute tasks directly — execution is handled by
    run_browser_task() which creates the Agent + Browser with the
    actual browser-use library API.
    """

    def __init__(self, config: BrowserConfig):
        self.config = config
        Path(self.config.profile_dir).mkdir(parents=True, exist_ok=True)

    def _profile_path(self, platform: str) -> str:
        return str(Path(self.config.profile_dir) / platform)

    def human_delay(self) -> None:
        """Introduce a random human-like delay between actions."""
        delay = random.uniform(
            self.config.human_delay_min,
            self.config.human_delay_max,
        )
        time.sleep(delay)

    # ── Search task templates ────────────────────────────────────────

    def build_search_task(self, platform: str, keyword: str,
                          max_posts: int = 3,
                          max_age_hours: int = 48) -> str:
        templates = {
            "youtube": self._youtube_search_task,
            "facebook": self._facebook_search_task,
            "instagram": self._instagram_search_task,
            "lihkg": self._lihkg_search_task,
            "xiaohongshu": self._xiaohongshu_search_task,
            "x": self._x_search_task,
            "linkedin": self._linkedin_search_task,
        }
        builder = templates.get(platform)
        if builder is None:
            raise ValueError(f"Unknown platform: {platform}")
        return builder(keyword, max_posts, max_age_hours)

    def _youtube_search_task(self, keyword: str, max_posts: int,
                             max_age_hours: int) -> str:
        return f"""Go to https://www.youtube.com/results?search_query={keyword.replace(' ', '+')}&sp=CAISAhAB
        (the sp=CAISAhAB filter shows videos from the last week).
        Scroll down to load at least {max_posts * 3} video results.
        For each relevant video about indoor air quality, formaldehyde, air purifiers,
        dehumidifiers, or Hong Kong housing, note: video title, channel name, URL,
        view count, and publication date.
        For each relevant video, go to its page, scroll to comments, and extract
        the top recent comments that mention IAQ-related topics.
        For each comment extract: author, comment text, timestamp, replyable status.
        Return as JSON array with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def _facebook_search_task(self, keyword: str, max_posts: int,
                              max_age_hours: int) -> str:
        return f"""Go to https://www.facebook.com/search/posts?q={keyword.replace(' ', '%20')}
        and filter by most recent posts.
        Scroll through the results and extract up to {max_posts} relevant public posts
        about IAQ, formaldehyde, air purifiers, dehumidifiers, Hong Kong housing
        from the last {max_age_hours} hours.
        For each: author/page name, full post text, URL, timestamp, engagement.
        Return as JSON array with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def _instagram_search_task(self, keyword: str, max_posts: int,
                               max_age_hours: int) -> str:
        return f"""Go to https://www.instagram.com/explore/search/keyword/?q={keyword.replace(' ', '%20')}
        and browse recent posts. Also check @pro.iaq_hk for recent comments.
        Extract up to {max_posts} posts about IAQ, formaldehyde, air purifiers,
        dehumidifiers from the last {max_age_hours} hours.
        For each: username, caption, URL, timestamp, engagement.
        Return as JSON array with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def _lihkg_search_task(self, keyword: str, max_posts: int,
                           max_age_hours: int) -> str:
        return f"""Go to https://lihkg.com and use search to find threads containing
        "{keyword}". Focus on last {max_age_hours} hours.
        Extract up to {max_posts} threads about IAQ, formaldehyde, air purifiers,
        dehumidifiers, new flats, home improvement.
        For each: thread title, OP username, main post content, URL, time, reply count.
        Return as JSON array with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def _xiaohongshu_search_task(self, keyword: str, max_posts: int,
                                 max_age_hours: int) -> str:
        return f"""Go to https://www.xiaohongshu.com/search_result?keyword={keyword.replace(' ', '%20')}
        and sort by newest. Scroll to load at least {max_posts * 2} results.
        Extract up to {max_posts} notes about 甲醛, 空氣清新機, 抽濕機,
        新樓, 裝修 from the last {max_age_hours} hours.
        For each: author, title, full text, URL, timestamp, engagement.
        Return as JSON array with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def _x_search_task(self, keyword: str, max_posts: int,
                       max_age_hours: int) -> str:
        return f"""Go to https://x.com/search?q={keyword.replace(' ', '%20')}&f=live
        and scroll through recent tweets.
        Extract up to {max_posts} tweets about IAQ, formaldehyde, air purifiers,
        dehumidifiers, Hong Kong housing from the last {max_age_hours} hours.
        For each: author handle, full text, URL, timestamp, engagement.
        Return as JSON array with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def _linkedin_search_task(self, keyword: str, max_posts: int,
                              max_age_hours: int) -> str:
        return f"""Go to https://www.linkedin.com/search/results/content/?keywords={keyword.replace(' ', '%20')}
        and sort by most recent. Scroll to load results.
        Extract up to {max_posts} posts about IAQ, workplace wellness, air purification,
        formaldehyde, Hong Kong commercial property from the last {max_age_hours} hours.
        For each: author/company, full text, URL, timestamp, engagement.
        Return as JSON array with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    # ── Reply task templates ─────────────────────────────────────────

    def build_reply_task(self, platform: str, post_url: str,
                         reply_text: str) -> str:
        templates = {
            "youtube": self._youtube_reply_task,
            "facebook": self._facebook_reply_task,
            "instagram": self._instagram_reply_task,
            "lihkg": self._lihkg_reply_task,
            "xiaohongshu": self._xiaohongshu_reply_task,
            "x": self._x_reply_task,
            "linkedin": self._linkedin_reply_task,
        }
        builder = templates.get(platform)
        if builder is None:
            raise ValueError(f"Unknown platform: {platform}")
        return builder(post_url, reply_text)

    def _youtube_reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Scroll to comments. Find reply box under
        the target comment. Click reply if needed. Type: "{escaped}".
        Wait 2 seconds, click submit. Confirm posted. Return 'success' or error."""

    def _facebook_reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Find comment box. Click to activate.
        Type: "{escaped}". Wait 2 seconds, press Enter or click Post.
        Confirm posted. Return 'success' or error."""

    def _instagram_reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Find comment field below post. Click to focus.
        Type: "{escaped}". Wait 2 seconds, click Post. Confirm comment appears.
        Return 'success' or error."""

    def _lihkg_reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Scroll to bottom to find reply box.
        Click text area. Type: "{escaped}". Wait 2 seconds, click submit.
        Confirm posted. Return 'success' or error."""

    def _xiaohongshu_reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Scroll to comment section. Find input box.
        Click to focus. Type: "{escaped}". Wait 2 seconds, click send.
        Confirm posted. Return 'success' or error."""

    def _x_reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Find Reply button below tweet. Click to open
        composer. Type: "{escaped}". Wait 2 seconds, click Reply.
        Confirm posted. Return 'success' or error."""

    def _linkedin_reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Find comment box. Click Add a comment.
        Type: "{escaped}". Wait 2 seconds, click Post.
        Confirm posted. Return 'success' or error."""


async def run_browser_task(task: str, config: BrowserConfig,
                           platform: str = "default",
                           llm_api_key: str = "",
                           llm_base_url: str = "",
                           llm_model: str = "") -> str:
    """Execute a browser-use task using the real browser-use library API.

    Creates a Browser + Agent with an OpenAI-compatible LLM (ChatOpenAI),
    runs the natural-language task, and returns the final result string.

    Args:
        task: Natural language task description for the browser agent.
        config: Browser configuration (local/cloud, headed, profiles).
        platform: Platform name for profile isolation.
        llm_api_key: API key for the LLM that drives browser-use.
        llm_base_url: Base URL for the LLM API (OpenRouter, DeepSeek, etc.).
        llm_model: Model name (e.g., 'deepseek/deepseek-chat', 'deepseek-chat').

    Returns:
        The final result string from the browser agent.
    """
    from browser_use import Agent, Browser
    from browser_use.llm import ChatOpenAI

    # ── Build the Browser ────────────────────────────────────────
    if config.mode == "cloud":
        browser = Browser(use_cloud=True)
        logger.info(f"Browser Use Cloud — platform: {platform}")
    else:
        profile_path = str(Path(config.profile_dir) / platform)
        Path(profile_path).mkdir(parents=True, exist_ok=True)
        browser = Browser(
            headless=not config.headed,
            user_data_dir=profile_path,
            keep_alive=False,
            wait_between_actions=random.uniform(
                config.human_delay_min, config.human_delay_max
            ),
        )
        logger.info(f"Local browser — profile: {profile_path}, "
                     f"headless={not config.headed}")

    # ── Build the LLM for browser-use Agent ──────────────────────
    llm = ChatOpenAI(
        model=llm_model or "gpt-4o",
        api_key=llm_api_key,
        base_url=llm_base_url or None,
        temperature=0.2,
    )

    # ── Create and run the Agent ─────────────────────────────────
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )

    try:
        history = await agent.run()
        final = history.final_result() if history else ""
        logger.info(f"Browser task completed for {platform}: {final[:120]}...")
        return final
    except Exception as e:
        logger.error(f"Browser task failed for {platform}: {e}")
        raise
    finally:
        if config.mode != "cloud":
            try:
                await browser.close()
            except Exception:
                pass
