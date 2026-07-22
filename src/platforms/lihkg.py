"""LIHKG platform handler — Hong Kong's local discussion forum."""

from src.platforms.base import BasePlatform


class LIHKGPlatform(BasePlatform):
    """LIHKG — Hong Kong's real public discussion board."""

    def search_task(self, keyword: str, max_posts: int,
                    max_age_hours: int) -> str:
        return f"""Go to https://lihkg.com and use search to find threads containing
        "{keyword}". Focus on last {max_age_hours} hours.
        Extract up to {max_posts} threads about IAQ, formaldehyde, air purifiers,
        dehumidifiers, new flats, home improvement.
        For each: thread title, OP username, main post, URL, time, reply count.
        Return as JSON list with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Scroll to bottom to find reply box.
        Click text area. Type: "{escaped}". Wait 2 seconds, click submit.
        Confirm posted. Return 'success' or error."""
