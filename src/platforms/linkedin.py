"""LinkedIn platform handler."""

from src.platforms.base import BasePlatform


class LinkedInPlatform(BasePlatform):
    """LinkedIn — professional public content."""

    def search_task(self, keyword: str, max_posts: int,
                    max_age_hours: int) -> str:
        encoded = keyword.replace(" ", "%20")
        return f"""Go to https://www.linkedin.com/search/results/content/?keywords={encoded}
        and sort by most recent. Scroll to load results.
        Extract up to {max_posts} posts about IAQ, workplace wellness, air purification,
        formaldehyde, Hong Kong commercial property from the last {max_age_hours} hours.
        For each: author/company, full text, URL, timestamp, engagement.
        Return as JSON list with fields: post_id, url, author, text, language,
        timestamp, engagement, media_description, is_replyable."""

    def reply_task(self, post_url: str, reply_text: str) -> str:
        escaped = reply_text.replace('"', '\\"')
        return f"""Go to {post_url}. Find comment box. Click Add a comment.
        Type: "{escaped}". Wait 2 seconds, click Post.
        Confirm posted. Return 'success' or error."""
