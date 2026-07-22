#!/usr/bin/env python3
"""
One-time browser profile setup script — uses raw Playwright, no API keys needed.

Run this ONCE per platform to log in manually. The browser will open in headed mode.
After you log in, close the browser. The session cookies are persisted in
data/profiles/<platform>/ and will be reused on subsequent runs.

Usage:
    python scripts/setup_profiles.py youtube
    python scripts/setup_profiles.py all
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PLATFORM_LOGIN_URLS = {
    "youtube": "https://www.youtube.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "lihkg": "https://lihkg.com",
    "xiaohongshu": "https://www.xiaohongshu.com",
    "x": "https://x.com",
    "linkedin": "https://www.linkedin.com",
}


async def setup_profile(platform: str, profile_dir: str = "./data/profiles"):
    """Open a browser for manual login using raw Playwright, persist the profile."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    url = PLATFORM_LOGIN_URLS.get(platform)
    if not url:
        print(f"Unknown platform: {platform}")
        print(f"Available: {', '.join(PLATFORM_LOGIN_URLS.keys())}")
        sys.exit(1)

    profile_path = str(Path(profile_dir) / platform)
    Path(profile_path).mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Setting up profile for: {platform}")
    print(f"Profile directory: {profile_path}")
    print(f"Login URL: {url}")
    print(f"{'='*60}")
    print("\n1. A browser window will open to the login page.")
    print("2. Log in to your account manually.")
    print("3. After successful login, PRESS ENTER in this terminal.")
    print("   (or just close the browser — cookies are saved automatically)")
    print()

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # Inject stealth to strip bot fingerprints
        try:
            from playwright_stealth import Stealth
            await Stealth().apply_stealth_async(page)
            print("  ✓ Stealth mode enabled")
        except ImportError:
            print("  ⚠ playwright-stealth not installed — bot detection possible")

        await page.goto(url, wait_until="domcontentloaded")

        print("Browser is open. Log in now, then press Enter here to close...")
        input()

        await context.close()

    print(f"\n✓ Profile saved to: {profile_path}")
    print(f"  You can now run the monitor and it will use this logged-in session.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_profiles.py <platform|all>")
        print(f"Platforms: {', '.join(PLATFORM_LOGIN_URLS.keys())}, all")
        sys.exit(1)

    target = sys.argv[1].lower()

    if target == "all":
        for platform in PLATFORM_LOGIN_URLS:
            asyncio.run(setup_profile(platform))
    else:
        asyncio.run(setup_profile(target))


if __name__ == "__main__":
    main()
