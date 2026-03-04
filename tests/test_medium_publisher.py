"""
Tests for the Playwright-based Medium publisher.

Usage:
    # Dry-run: tests markdown conversion only, no browser required
    python tests/test_medium_publisher.py --dry-run

    # Live integration test: opens browser, logs in, publishes a test article
    # Requires MEDIUM_EMAIL and MEDIUM_PASSWORD set in .env
    python tests/test_medium_publisher.py --live
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

# ── project root on path ──────────────────────────────────────────────────
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# load .env so credentials are available
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

from src.utils.medium_playwright import MediumPlaywrightPublisher, MediumPublishError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger("test_medium_publisher")

# ── Sample article used in live test ─────────────────────────────────────

SAMPLE_TITLE = f"[TEST] AI Newsroom Auto-Publish — {datetime.now().strftime('%Y-%m-%d %H:%M')}"

SAMPLE_MARKDOWN = """\
# AI Newsroom Automated Publishing Test

This article was published automatically by the **AI Newsroom** Playwright publisher.
It is a brief test post and can be safely deleted.

## What Is AI Newsroom?

AI Newsroom is a multi-agent system that:
- Scouts trending topics from Hacker News, Reddit, and ArXiv
- Researches each topic with LLM-powered agents
- Writes, edits, and publishes articles autonomously

## Why Playwright?

The Medium REST API was deprecated. Playwright lets us drive a real browser to:
1. Log in with email & password
2. Open a new story
3. Type the article content
4. Add tags and publish

## Conclusion

This is a short, harmless test article. If you see this on Medium, the integration works!
"""

SAMPLE_TAGS = ["technology", "ai", "automation", "test"]


# ── Tests ─────────────────────────────────────────────────────────────────

def test_markdown_conversion() -> bool:
    """Unit test: verify _convert_markdown() produces reasonable output."""
    logger.info("=" * 60)
    logger.info("DRY-RUN: Testing Markdown Conversion")
    logger.info("=" * 60)

    publisher = MediumPlaywrightPublisher(
        email="test@example.com",
        password="placeholder",
        headless=True,
    )

    result = publisher._convert_markdown(SAMPLE_MARKDOWN)

    passed = True
    checks = [
        ("Headings converted", "AI NEWSROOM AUTOMATED PUBLISHING TEST" in result),
        ("Bold stripped", "**AI Newsroom**" not in result and "AI Newsroom" in result),
        ("Bullet list preserved", "- Scouts" in result or "Scouts" in result),
        ("Numbered list preserved", "1." in result),
        ("Non-empty output", len(result.strip()) > 50),
    ]

    for name, ok in checks:
        status = "✅" if ok else "❌"
        logger.info(f"  {status} {name}")
        if not ok:
            passed = False

    if passed:
        logger.info("\n✅ Markdown conversion test PASSED")
    else:
        logger.error("\n❌ Markdown conversion test FAILED")
        logger.debug("Converted output:\n" + result)

    return passed


def test_strip_inline() -> bool:
    """Unit test: verify inline Markdown stripping."""
    logger.info("\n" + "=" * 60)
    logger.info("DRY-RUN: Testing Inline Markdown Stripping")
    logger.info("=" * 60)

    publisher = MediumPlaywrightPublisher(email="x", password="x")

    cases = [
        ("**bold**", "bold"),
        ("*italic*", "italic"),
        ("__underline__", "underline"),
        ("~~strike~~", "strike"),
        ("[link text](https://example.com)", "link text"),
        ("![alt](https://img.com/a.png)", "alt"),
        ("***bold-italic***", "bold-italic"),
    ]

    all_passed = True
    for source, expected in cases:
        actual = publisher._strip_inline(source)
        ok = actual == expected
        status = "✅" if ok else "❌"
        logger.info(f"  {status} '{source}' → '{actual}' (expected '{expected}')")
        if not ok:
            all_passed = False

    if all_passed:
        logger.info("\n✅ Inline stripping test PASSED")
    else:
        logger.error("\n❌ Inline stripping test FAILED")

    return all_passed


def test_live_publish() -> bool:
    """Integration test: actually publish a test article to Medium."""
    import os

    logger.info("\n" + "=" * 60)
    logger.info("LIVE: Publishing test article to Medium")
    logger.info("=" * 60)

    email = os.getenv("MEDIUM_EMAIL", "")
    password = os.getenv("MEDIUM_PASSWORD", "")

    if not email or not password:
        logger.error(
            "❌ MEDIUM_EMAIL and MEDIUM_PASSWORD must be set in .env to run the live test."
        )
        return False

    headless = os.getenv("MEDIUM_HEADLESS", "true").lower() != "false"
    logger.info(f"  Email   : {email}")
    logger.info(f"  Headless: {headless}")
    logger.info(f"  Title   : {SAMPLE_TITLE}")

    try:
        publisher = MediumPlaywrightPublisher(
            email=email,
            password=password,
            headless=headless,
        )
        url = publisher.publish(
            title=SAMPLE_TITLE,
            content_markdown=SAMPLE_MARKDOWN,
            tags=SAMPLE_TAGS,
        )
        logger.info(f"\n✅ Article published successfully!")
        logger.info(f"   URL: {url}")
        return True

    except MediumPublishError as e:
        logger.error(f"\n❌ Publishing failed: {e}")
        return False
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        return False


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Test the Playwright-based Medium publisher"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Run unit tests only (no browser, no credentials needed)",
    )
    group.add_argument(
        "--live",
        action="store_true",
        help="Run full integration test (opens browser, publishes to Medium)",
    )
    args = parser.parse_args()

    results = {}

    if args.dry_run or not args.live:
        # Always run unit tests
        results["markdown_conversion"] = test_markdown_conversion()
        results["inline_stripping"] = test_strip_inline()

    if args.live:
        results["live_publish"] = test_live_publish()

    # ── Summary ──
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"  {status}  {name}")

    all_passed = all(results.values())
    if all_passed:
        logger.info("\n✅ All tests passed!")
    else:
        logger.error("\n❌ Some tests failed — see logs above.")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
