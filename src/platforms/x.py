"""X (Twitter) platform handler."""

from src.platforms.base import BasePlatform


class XPlatform(BasePlatform):
    """X (Twitter) — public real-time discussion."""

    def search_task(self, keyword: str, max_posts: int,
                    max_age_hours: int) -> str:
        encoded = keyword.replace(" ", "%20")
        return f"""Go to https://x.com/search?q={encoded}&f=live
        and scroll through recent tweets.
        Extract up to {max_posts} tweets about IAQ, formaldehyde, air purifiers,
        dehumidifiers, Hong Kong housing from the last {max_age_hours} hours.
        For each: author handle, full text, URL, timestamp, engagement.
        Return as JSON list with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Find Reply button below tweet. Click to open
        composer. Type: "{escaped}". Wait 2 seconds, click Reply.
        Confirm posted. Return 'success' or error."""
