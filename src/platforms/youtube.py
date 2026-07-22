"""YouTube platform handler."""

from src.platforms.base import BasePlatform


class YouTubePlatform(BasePlatform):
    """YouTube — highest priority. Search videos and comments."""

    def search_task(self, keyword: str, max_posts: int,
                    max_age_hours: int) -> str:
        encoded = keyword.replace(" ", "+")
        return f"""Go to https://www.youtube.com/results?search_query={encoded}&sp=CAISAhAB
        (the sp=CAISAhAB filter shows videos from the last week).
        Scroll down to load at least {max_posts * 3} video results.
        For each relevant video about indoor air quality, formaldehyde, air purifiers,
        dehumidifiers, or Hong Kong housing, note: video title, channel name, URL,
        view count, and publication date.
        For each relevant video, go to its page, scroll to comments, and extract
        the top recent comments that mention IAQ-related topics.
        For each comment extract: author, comment text, timestamp, replyable status.
        Return all extracted data in JSON format:
        [{{"post_id": "...", "url": "...", "author": "...", "text": "...",
        "language": "en|zh|yue", "timestamp": "...", "engagement": "...",
        "media_description": "...", "is_replyable": true|false}}]"""

    def reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Scroll to comments. Find the reply box under
        the target comment. Click reply if needed. Type: "{escaped}".
        Wait 2 seconds, click submit. Confirm posted. Return 'success' or error."""
