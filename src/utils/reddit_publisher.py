"""
Reddit Publisher — posts AI Newsroom articles to Reddit via PRAW.

Reddit supports Markdown natively, so article content renders perfectly as
rich text in a self (text) post.

Setup:
    1. Go to https://www.reddit.com/prefs/apps
    2. Click "Create app" → choose "script"
    3. Fill in name, description, redirect URI = http://localhost:8080
    4. Copy the client_id (under the app name) and client_secret
    5. Set all four env vars below in your .env file

Required env vars:
    REDDIT_CLIENT_ID      — from prefs/apps
    REDDIT_CLIENT_SECRET  — from prefs/apps
    REDDIT_USERNAME       — your Reddit username
    REDDIT_PASSWORD       — your Reddit password
    REDDIT_SUBREDDIT      — subreddit to post to (default: artificial)
    REDDIT_USER_AGENT     — e.g. "AI_Newsroom/1.0 by YourUsername"
    REDDIT_POST_FLAIR     — (optional) flair text to apply to the post
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RedditPublishError(Exception):
    """Raised when posting to Reddit fails."""


class RedditPublisher:
    """
    Publishes articles to Reddit as self (text) posts via PRAW.

    Reddit natively renders Markdown, so the article body is used as-is.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        subreddit: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET", "")
        self.username = username or os.getenv("REDDIT_USERNAME", "")
        self.password = password or os.getenv("REDDIT_PASSWORD", "")
        self.subreddit = subreddit or os.getenv("REDDIT_SUBREDDIT", "artificial")
        self.user_agent = (
            user_agent
            or os.getenv("REDDIT_USER_AGENT", "")
            or f"AI_Newsroom/1.0 by {self.username}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish(
        self,
        title: str,
        content_markdown: str,
        flair_text: Optional[str] = None,
    ) -> str:
        """
        Post an article to Reddit as a self (text) post.

        Args:
            title: Post title (≤ 300 chars)
            content_markdown: Article body in Markdown (≤ 40 000 chars)
            flair_text: Optional post flair label

        Returns:
            Full URL of the created Reddit post

        Raises:
            RedditPublishError: if credentials are missing or the post fails
        """
        self._validate_credentials()

        try:
            import praw
        except ImportError:
            raise RedditPublishError(
                "praw is not installed. Run: pip install praw"
            )

        # Truncate content to Reddit's 40 000-char limit
        if len(content_markdown) > 40_000:
            content_markdown = content_markdown[:39_950] + "\n\n*(truncated)*"

        # Truncate title to Reddit's 300-char limit
        title = title[:300]

        try:
            reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                username=self.username,
                password=self.password,
                user_agent=self.user_agent,
            )

            sub = reddit.subreddit(self.subreddit)
            logger.info(f"Submitting post to r/{self.subreddit}: '{title}'")

            submission = sub.submit(
                title=title,
                selftext=content_markdown,
            )

            # Apply flair if requested and available
            env_flair = flair_text or os.getenv("REDDIT_POST_FLAIR", "")
            if env_flair:
                try:
                    self._apply_flair(submission, env_flair)
                except Exception as e:
                    logger.warning(f"Could not apply flair '{env_flair}': {e}")

            url = f"https://www.reddit.com{submission.permalink}"
            logger.info(f"Post published: {url}")
            return url

        except praw.exceptions.PRAWException as e:
            raise RedditPublishError(f"PRAW error: {e}") from e
        except Exception as e:
            raise RedditPublishError(f"Unexpected Reddit error: {e}") from e

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_credentials(self) -> None:
        """Raise RedditPublishError if any required credential is missing."""
        missing = []
        for field in ("client_id", "client_secret", "username", "password"):
            if not getattr(self, field):
                missing.append(field.upper())
        if missing:
            raise RedditPublishError(
                f"Missing Reddit credentials: {', '.join('REDDIT_' + m for m in missing)}. "
                "Set them in your .env file. "
                "Create an app at https://www.reddit.com/prefs/apps to get "
                "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET."
            )

    @staticmethod
    def _apply_flair(submission, flair_text: str) -> None:
        """Apply a flair to a submission if the subreddit has matching flairs."""
        choices = list(submission.flair.choices())
        for choice in choices:
            if flair_text.lower() in choice.get("flair_text", "").lower():
                submission.flair.select(choice["flair_template_id"])
                logger.info(f"Flair '{choice['flair_text']}' applied.")
                return
        logger.warning(
            f"No matching flair for '{flair_text}'. "
            f"Available: {[c.get('flair_text') for c in choices]}"
        )

    def verify_credentials(self) -> bool:
        """
        Quick connectivity check — returns True if credentials work.
        Does NOT post anything.
        """
        try:
            import praw
            self._validate_credentials()
            reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                username=self.username,
                password=self.password,
                user_agent=self.user_agent,
            )
            # Accessing .me() forces authentication
            me = reddit.user.me()
            logger.info(f"Authenticated as u/{me.name} (karma: {me.link_karma})")
            return True
        except Exception as e:
            logger.error(f"Credential check failed: {e}")
            return False
