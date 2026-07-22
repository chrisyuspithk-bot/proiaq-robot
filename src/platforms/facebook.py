"""Facebook platform handler."""

from src.platforms.base import BasePlatform


class FacebookPlatform(BasePlatform):
    """Facebook — second priority. Public posts, pages, groups."""

    def search_task(self, keyword: str, max_posts: int,
                    max_age_hours: int) -> str:
        encoded = keyword.replace(" ", "%20")
        return f"""Go to https://www.facebook.com/search/posts?q={encoded}
        and filter by most recent posts.
        Scroll to load results. Extract up to {max_posts} relevant public posts
        about indoor air quality, formaldehyde, air purifiers, dehumidifiers,
        or Hong Kong housing from the last {max_age_hours} hours.
        For each post extract: author, full text, URL, timestamp, engagement.
        Return as JSON list with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Find the comment box. Click to activate.
        Type: "{escaped}". Wait 2 seconds, press Enter or click Post.
        Confirm posted. Return 'success' or error."""
