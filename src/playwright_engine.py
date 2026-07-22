"""Raw Playwright engine — zero LLM tokens for browser control.

Uses direct CSS selectors per platform. The LLM is only called once
after page extraction to parse raw text into structured post data.
"""

import asyncio
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger
from openai import OpenAI
from playwright.async_api import async_playwright, BrowserContext, Page


# ── Platform-specific selectors ──────────────────────────────────

PLATFORM_CONFIGS = {
    "youtube": {
        "search_url": "https://www.youtube.com/results?search_query={keyword}",
        "comment_selector": "ytd-comment-thread-renderer #content-text",
        "reply_box_selector": "#simplebox-placeholder, #placeholder-area",
        "reply_input_selector": "#contenteditable-root",
        "submit_selector": "#submit-button button",
    },
    "facebook": {
        "search_url": "https://www.facebook.com/search/posts?q={keyword}",
        "comment_selector": "div[role=article] div[dir=auto]",
        "reply_box_selector": "div[role=textbox]",
        "reply_input_selector": "div[role=textbox]",
        "submit_selector": "div[aria-label=Comment]",
    },
    "instagram": {
        "search_url": "https://www.instagram.com/explore/search/keyword/?q={keyword}",
        "comment_selector": "article ul li span",
        "reply_box_selector": "textarea[aria-label='Add a comment']",
        "reply_input_selector": "textarea[aria-label='Add a comment']",
        "submit_selector": "div[role=button]:has-text('Post')",
    },
    "lihkg": {
        "search_url": "https://lihkg.com/search?q={keyword}",
        "comment_selector": "div.post-content, div.reply-content",
        "reply_box_selector": "textarea#reply-form-textarea",
        "reply_input_selector": "textarea#reply-form-textarea",
        "submit_selector": "button:has-text('回覆')",
    },
    "xiaohongshu": {
        "search_url": "https://www.xiaohongshu.com/search_result?keyword={keyword}&sort=time",
        "comment_selector": ".note-content, .note-text, .desc",
        "reply_box_selector": ".comment-input textarea, .input-box textarea",
        "reply_input_selector": ".comment-input textarea, .input-box textarea",
        "submit_selector": ".submit-btn, button:has-text('发送')",
    },
    "x": {
        "search_url": "https://x.com/search?q={keyword}&f=live",
        "comment_selector": "article div[data-testid=tweetText]",
        "reply_box_selector": "div[data-testid=tweetTextarea_0]",
        "reply_input_selector": "div[data-testid=tweetTextarea_0]",
        "submit_selector": "button[data-testid=tweetButton]",
    },
    "linkedin": {
        "search_url": "https://www.linkedin.com/search/results/content/?keywords={keyword}&sortBy=date",
        "comment_selector": "div.feed-shared-update-v2__description",
        "reply_box_selector": "div.ql-editor[contenteditable=true]",
        "reply_input_selector": "div.ql-editor[contenteditable=true]",
        "submit_selector": "button.comments-comment-box__submit-button",
    },
}

EXTRACTION_PROMPT = """You are a data extraction assistant. Below is text scraped from social media
search results. Extract up to {max_posts} relevant posts about indoor air quality (IAQ),
formaldehyde (甲醛), air purifiers (空氣清新機), dehumidifiers (抽濕機), new flats,
home renovation, or related HK topics.

For each post, return a JSON object with these fields:
- post_id: unique identifier from the URL or a hash of the text
- url: full URL to the post
- author: username or display name
- text: the post content
- language: "en", "zh", or "yue"
- timestamp: when posted (ISO format or relative like "2 hours ago")
- engagement: likes/comments/shares info if visible
- media_description: describe any images/videos mentioned
- is_replyable: true if you can comment on it

Return ONLY a JSON array, no other text.
Example: [{{"post_id": "...", "url": "...", ...}}]

RAW PAGE TEXT:
{page_text}"""


@dataclass
class PlaywrightConfig:
    """Configuration for the Playwright engine."""
    headed: bool = False
    profile_dir: str = "./data/profiles"
    human_delay_min: float = 1.0
    human_delay_max: float = 3.0
    scroll_pause: float = 3.0     # seconds to wait after scroll
    max_scrolls: int = 5           # how many times to scroll for content
    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "deepseek/deepseek-chat"


class PlaywrightEngine:
    """Raw Playwright browser automation — no LLM tokens for control.

    Uses direct CSS selectors. The LLM is called once per search
    to parse scraped text into structured data.
    """

    def __init__(self, config: PlaywrightConfig):
        self.config = config
        self._llm: Optional[OpenAI] = None
        Path(self.config.profile_dir).mkdir(parents=True, exist_ok=True)

    @property
    def llm(self) -> OpenAI:
        if self._llm is None:
            self._llm = OpenAI(
                api_key=self.config.llm_api_key,
                base_url=self.config.llm_base_url,
            )
        return self._llm

    def _profile_path(self, platform: str) -> str:
        return str(Path(self.config.profile_dir) / platform)

    def _human_delay(self) -> None:
        time.sleep(random.uniform(
            self.config.human_delay_min, self.config.human_delay_max))

    # ── Search ────────────────────────────────────────────────────

    async def search(self, platform: str, keyword: str,
                     max_posts: int = 3, max_age_hours: int = 48) -> list[dict]:
        """Search a platform and return structured post data using Playwright."""
        plat = PLATFORM_CONFIGS.get(platform)
        if not plat:
            raise ValueError(f"No selectors configured for platform: {platform}")

        encoded = keyword.replace(" ", "+")
        search_url = plat["search_url"].format(keyword=encoded)

        logger.info(f"Playwright search: {platform} '{keyword}' -> {search_url[:80]}...")

        async with async_playwright() as p:
            context = await self._create_context(p, platform)
            page = await context.new_page()

            try:
                await page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                self._human_delay()

                # Scroll to load dynamic content
                for _ in range(self.config.max_scrolls):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await asyncio.sleep(self.config.scroll_pause)

                # Extract all visible text
                page_text = await page.evaluate("document.body.innerText")

                # Try extracting any visible links/URLs
                links_js = await page.evaluate("""() => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href;
                        const text = a.innerText.trim().slice(0, 100);
                        if (href && !href.startsWith('javascript:')) {
                            links.push({url: href, text: text});
                        }
                    });
                    return links.slice(0, 50);
                }""")

                # Build enriched text for LLM parsing
                link_lines = "\n".join(
                    f"LINK: {l['url']} | TEXT: {l['text']}"
                    for l in links_js
                )
                full_text = f"PAGE URLS:\n{link_lines}\n\nPAGE CONTENT:\n{page_text}"

                # Parse with LLM (single call)
                posts = self._extract_posts(full_text[:30000], max_posts)
                for p in posts:
                    p["platform"] = platform
                return posts

            except Exception as e:
                logger.error(f"Playwright search failed: {e}")
                raise
            finally:
                await context.close()

    # ── Reply ─────────────────────────────────────────────────────

    async def post_reply(self, platform: str, post_url: str,
                         reply_text: str) -> str:
        """Post a reply/comment using direct Playwright selectors."""
        plat = PLATFORM_CONFIGS.get(platform)
        if not plat:
            raise ValueError(f"No selectors for platform: {platform}")

        logger.info(f"Playwright reply: {platform} -> {post_url[:80]}...")

        async with async_playwright() as p:
            context = await self._create_context(p, platform)
            page = await context.new_page()

            try:
                await page.goto(post_url, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                self._human_delay()

                # Scroll down to reveal the comment box
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1)

                # Click the reply box / comment area to activate it
                box = plat.get("reply_box_selector", "")
                inp = plat.get("reply_input_selector", "")
                submit = plat.get("submit_selector", "")

                if box:
                    try:
                        await page.click(box, timeout=5000)
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass

                # Type the reply
                if inp:
                    try:
                        await page.fill(inp, reply_text, timeout=5000)
                    except Exception:
                        await page.keyboard.type(reply_text, delay=50)
                else:
                    await page.keyboard.type(reply_text, delay=50)

                self._human_delay()

                # Submit
                if submit:
                    try:
                        await page.click(submit, timeout=5000)
                    except Exception:
                        await page.keyboard.press("Enter")
                else:
                    await page.keyboard.press("Enter")

                await asyncio.sleep(2)
                return "success"

            except Exception as e:
                logger.error(f"Playwright reply failed: {e}")
                return f"error: {e}"
            finally:
                await context.close()

    # ── Helpers ───────────────────────────────────────────────────

    async def _create_context(self, p, platform: str) -> BrowserContext:
        profile = self._profile_path(platform)
        Path(profile).mkdir(parents=True, exist_ok=True)

        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile,
            headless=not self.config.headed,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        # Inject stealth to strip bot fingerprints (navigator.webdriver, etc.)
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            from playwright_stealth import Stealth
            await Stealth().apply_stealth_async(page)
        except ImportError:
            logger.warning("playwright-stealth not installed — bot detection possible")
        return context

    def _extract_posts(self, page_text: str, max_posts: int) -> list[dict]:
        """Use LLM to parse scraped page text into structured posts."""
        prompt = EXTRACTION_PROMPT.format(max_posts=max_posts, page_text=page_text)

        try:
            resp = self.llm.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": "You extract structured data from social media scrapes. Return only JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=2000,
            )
            raw = resp.choices[0].message.content.strip()

            # Extract JSON array
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])

            logger.warning(f"Could not parse LLM extraction output: {raw[:200]}")
            return []

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []
