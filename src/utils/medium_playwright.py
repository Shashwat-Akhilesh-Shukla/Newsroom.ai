"""
Medium Publisher via Playwright browser automation.

Replaces the defunct Medium REST API with a Playwright-driven browser session
that logs in, creates a new story, fills content, adds tags, and publishes.

Usage:
    from src.utils.medium_playwright import MediumPlaywrightPublisher

    publisher = MediumPlaywrightPublisher()
    url = publisher.publish(
        title="My Article Title",
        content_markdown="## Intro\\n\\nHello world...",
        tags=["technology", "ai"],
    )
    print(url)  # https://medium.com/@username/my-article-title-abc123
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Screenshot / log output directory
# ---------------------------------------------------------------------------
_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)


class MediumPublishError(Exception):
    """Raised when publishing to Medium fails."""


class MediumPlaywrightPublisher:
    """
    Publishes articles to Medium via Playwright browser automation.

    Credentials are read from environment variables by default:
        MEDIUM_EMAIL     — your Medium account email
        MEDIUM_PASSWORD  — your Medium account password
        MEDIUM_HEADLESS  — 'true' (default) or 'false' to watch the browser
    """

    SIGNIN_URL = "https://medium.com/m/signin"
    NEW_STORY_URL = "https://medium.com/new-story"

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        headless: Optional[bool] = None,
    ):
        self.email = email or os.getenv("MEDIUM_EMAIL", "")
        self.password = password or os.getenv("MEDIUM_PASSWORD", "")
        if headless is None:
            headless = os.getenv("MEDIUM_HEADLESS", "true").lower() != "false"
        self.headless = headless

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish(
        self,
        title: str,
        content_markdown: str,
        tags: Optional[List[str]] = None,
        subtitle: str = "",
    ) -> str:
        """
        Publish an article to Medium.

        Args:
            title: Article headline
            content_markdown: Article body in Markdown format
            tags: Up to 5 Medium tags
            subtitle: Optional subtitle / subheading

        Returns:
            Published article URL (str)

        Raises:
            MediumPublishError: if any step fails
        """
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

        tags = (tags or [])[:5]
        body_text = self._convert_markdown(content_markdown)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            try:
                self._login(page)
                url = self._create_story(page, title, subtitle, body_text, tags)
                logger.info(f"Article published successfully: {url}")
                return url

            except PWTimeoutError as e:
                self._screenshot(page, "timeout_error")
                raise MediumPublishError(f"Timeout during publishing: {e}") from e

            except Exception as e:
                self._screenshot(page, "general_error")
                raise MediumPublishError(f"Publishing failed: {e}") from e

            finally:
                context.close()
                browser.close()

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    def _login(self, page) -> None:
        """Log into Medium using email + password."""
        logger.info("Navigating to Medium sign-in page...")
        page.goto(self.SIGNIN_URL, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(2)

        # Click "Sign in with email"
        logger.info("Clicking 'Sign in with email'...")
        email_btn = page.locator("text=Sign in with email").first
        email_btn.wait_for(state="visible", timeout=15_000)
        email_btn.click()
        time.sleep(1)

        # Fill email field
        logger.info("Filling email...")
        email_input = page.locator('input[type="email"], input[name="email"]').first
        email_input.wait_for(state="visible", timeout=10_000)
        email_input.fill(self.email)
        page.keyboard.press("Enter")
        time.sleep(2)

        # Fill password field (appears after email submission)
        logger.info("Filling password...")
        pw_input = page.locator('input[type="password"]').first
        pw_input.wait_for(state="visible", timeout=10_000)
        pw_input.fill(self.password)
        page.keyboard.press("Enter")

        # Wait for redirect away from sign-in page
        logger.info("Waiting for login to complete...")
        page.wait_for_url(lambda url: "signin" not in url, timeout=30_000)
        logger.info("Login successful.")
        time.sleep(2)

    def _create_story(
        self,
        page,
        title: str,
        subtitle: str,
        body_text: str,
        tags: List[str],
    ) -> str:
        """Navigate to new story editor, fill content, publish, return URL."""
        logger.info("Opening new story editor...")
        page.goto(self.NEW_STORY_URL, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(3)

        # ---- Title ----
        logger.info("Typing title...")
        title_el = page.locator(
            'h3[data-testid="editorTitle"], '
            'h1[data-test-id="editorTitle"], '
            'div[data-contents="true"] h3'
        ).first
        title_el.wait_for(state="visible", timeout=15_000)
        title_el.click()
        page.keyboard.type(title, delay=30)
        page.keyboard.press("Enter")
        time.sleep(0.5)

        # ---- Subtitle (optional) ----
        if subtitle:
            page.keyboard.type(subtitle, delay=20)
            page.keyboard.press("Enter")

        # ---- Body ----
        logger.info(f"Typing body ({len(body_text)} chars)...")
        # Use clipboard paste for speed — avoids per-char delay for long articles
        self._paste_text(page, body_text)
        time.sleep(1)

        # ---- Tags ----
        if tags:
            self._add_tags(page, tags)

        # ---- Publish ----
        return self._publish_story(page)

    def _paste_text(self, page, text: str) -> None:
        """Paste text via clipboard (faster than key-by-key typing)."""
        # Set clipboard content then Ctrl+V
        page.evaluate(
            """(text) => {
                navigator.clipboard.writeText(text).catch(() => {});
            }""",
            text,
        )
        # Some headless environments block navigator.clipboard; fall back to
        # typing in chunks if paste produces nothing.
        page.keyboard.press("Control+v")
        time.sleep(1)
        # Verify something was typed; if not, chunk-type
        content = page.locator('div[data-contents="true"]').inner_text()
        if len(content.strip()) < 10:
            logger.warning("Clipboard paste may have failed; typing in chunks...")
            chunk_size = 500
            for i in range(0, len(text), chunk_size):
                page.keyboard.type(text[i : i + chunk_size], delay=5)

    def _add_tags(self, page, tags: List[str]) -> None:
        """Open publish panel (if needed) to add tags."""
        logger.info(f"Adding tags: {tags}")
        # Tags are added in the publish modal — we'll open it, add tags, then proceed.
        # First check if a tag input is already visible (some editor versions show it inline).
        tag_input = page.locator('input[placeholder*="tag" i], input[placeholder*="Tag" i]').first
        if not tag_input.is_visible():
            # Open publish modal to get to tags
            publish_btn = page.locator('button:has-text("Publish")').first
            if publish_btn.is_visible():
                publish_btn.click()
                time.sleep(2)
                tag_input = page.locator('input[placeholder*="tag" i], input[placeholder*="Add a tag" i]').first

        if tag_input.is_visible():
            for tag in tags:
                tag_input.click()
                tag_input.fill(tag)
                page.keyboard.press("Enter")
                time.sleep(0.5)
        else:
            logger.warning("Could not find tag input — skipping tags.")

    def _publish_story(self, page) -> str:
        """
        Click through the publish flow and return the final article URL.
        Medium's publish flow:
          1. Click green 'Publish' button (top-right)
          2. Optionally fill tags in the modal
          3. Click 'Publish now'
          4. Capture the URL from the success screen or current page URL
        """
        logger.info("Initiating publish flow...")

        # Step 1 — open publish modal
        publish_btn = page.locator('button:has-text("Publish")').first
        publish_btn.wait_for(state="visible", timeout=10_000)
        publish_btn.click()
        time.sleep(2)

        # Step 2 — click 'Publish now' inside the modal
        publish_now = page.locator(
            'button:has-text("Publish now"), button:has-text("Publish story")'
        ).first
        publish_now.wait_for(state="visible", timeout=10_000)
        publish_now.click()
        time.sleep(3)

        # Step 3 — capture URL from success banner or page URL
        url = self._capture_published_url(page)
        return url

    def _capture_published_url(self, page) -> str:
        """Try several strategies to grab the final published URL."""
        # Strategy A: page navigates to the article
        try:
            page.wait_for_url(
                lambda u: "/p/" in u or ("medium.com/@" in u and "/new-story" not in u),
                timeout=15_000,
            )
            url = page.url
            if "/p/" in url or "medium.com/@" in url:
                logger.info(f"Captured URL from page navigation: {url}")
                return url
        except Exception:
            pass

        # Strategy B: look for a 'View your story' / 'See your story' link
        try:
            link = page.locator(
                'a:has-text("View your story"), a:has-text("See your story"), '
                'a:has-text("View story")'
            ).first
            if link.is_visible():
                url = link.get_attribute("href") or ""
                logger.info(f"Captured URL from success link: {url}")
                return url
        except Exception:
            pass

        # Strategy C: return current page URL as best-effort
        url = page.url
        logger.warning(f"Using current page URL as fallback: {url}")
        return url

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _convert_markdown(self, text: str) -> str:
        """
        Convert Markdown to a clean plain-text format suitable for Medium's
        rich-text editor.

        Medium's new editor accepts plain text with line breaks.
        We preserve structure by:
          - H1/H2/H3 → ALL CAPS line (Medium auto-styles pasted caps as subheads)
          - Bold/italic markers stripped
          - Inline code → backtick-quoted (Medium renders these)
          - Code blocks → indented
          - Bullet lists → dash-prefixed (Medium preserves these)
          - Numbered lists → kept as-is
        """
        lines = text.split("\n")
        result = []

        in_code_block = False
        for line in lines:
            # Code fences
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                if in_code_block:
                    result.append("")  # blank line before code
                else:
                    result.append("")  # blank line after code
                continue

            if in_code_block:
                result.append("    " + line)  # indent code lines
                continue

            # ATX headings → keep as bold-uppercase label
            heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                # Strip residual markdown in heading text
                heading_text = self._strip_inline(heading_text)
                if level == 1:
                    result.append(heading_text.upper())
                elif level == 2:
                    result.append(heading_text.upper())
                else:
                    result.append(heading_text)
                result.append("")
                continue

            # Horizontal rules
            if re.match(r"^[-*_]{3,}\s*$", line):
                result.append("— — —")
                continue

            # Normal line: strip inline markdown
            result.append(self._strip_inline(line))

        return "\n".join(result)

    @staticmethod
    def _strip_inline(text: str) -> str:
        """Remove bold, italic, link syntax, and similar inline Markdown."""
        # Bold+italic
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        # Italic
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        # Strikethrough
        text = re.sub(r"~~(.+?)~~", r"\1", text)
        # Links: [text](url) → text
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        # Images: ![alt](url) → alt
        text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", text)
        # Inline code — keep backtick-quoted for Medium
        # (no change needed)
        return text

    def _screenshot(self, page, label: str) -> None:
        """Save a screenshot for debugging."""
        try:
            path = _LOG_DIR / f"medium_playwright_{label}_{int(time.time())}.png"
            page.screenshot(path=str(path))
            logger.info(f"Screenshot saved: {path}")
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {e}")
