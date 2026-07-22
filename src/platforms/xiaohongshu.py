"""Xiaohongshu (小紅書) platform handler."""

from src.platforms.base import BasePlatform


class XiaohongshuPlatform(BasePlatform):
    """Xiaohongshu — fastest growing lifestyle & discovery platform."""

    def search_task(self, keyword: str, max_posts: int,
                    max_age_hours: int) -> str:
        encoded = keyword.replace(" ", "%20")
        return f"""Go to https://www.xiaohongshu.com/search_result?keyword={encoded}
        and sort by newest. Scroll to load at least {max_posts * 2} results.
        Extract up to {max_posts} relevant notes about formaldehyde (甲醛),
        air purifiers (空氣清新機), dehumidifiers (抽濕機),
        new flats (新樓), renovation (裝修) from the last {max_age_hours} hours.
        For each: author, title, full text, URL, timestamp, engagement.
        Return as JSON list with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Scroll to comment section. Find input box.
        Click to focus. Type: "{escaped}". Wait 2 seconds, click send.
        Confirm posted. Return 'success' or error."""
