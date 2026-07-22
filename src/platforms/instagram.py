"""Instagram platform handler."""

from src.platforms.base import BasePlatform


class InstagramPlatform(BasePlatform):
    """Instagram — third priority. Visual & lifestyle."""

    def search_task(self, keyword: str, max_posts: int,
                    max_age_hours: int) -> str:
        encoded = keyword.replace(" ", "%20")
        return f"""Go to https://www.instagram.com/explore/search/keyword/?q={encoded}
        and browse recent posts. Also check @pro.iaq_hk for recent comments.
        Extract up to {max_posts} relevant posts about IAQ, formaldehyde, air purifiers,
        dehumidifiers from the last {max_age_hours} hours.
        For each: username, caption, URL, timestamp, engagement.
        Return as JSON list with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Find comment field below post. Click to focus.
        Type: "{escaped}". Wait 2 seconds, click Post. Confirm comment appears.
        Return 'success' or error."""
