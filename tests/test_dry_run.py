#!/usr/bin/env python3
"""
Dry-run test: demonstrates extraction + reply generation without posting.

This test exercises the LLM reply generator and state management
without requiring browser-use or actual social media credentials.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, load_keywords
from src.llm import PostContext, ReplyGenerator
from src.state import StateManager


def test_state_manager():
    """Test SQLite state management."""
    print("\n=== Testing State Manager ===")
    state = StateManager(db_path=":memory:")

    # Test dedup
    assert not state.is_already_replied("youtube", "post123"), "Should not be replied yet"
    state.mark_replied("youtube", "post123", "https://youtube.com/watch?v=123",
                       "Great tips on formaldehyde!")
    assert state.is_already_replied("youtube", "post123"), "Should be marked replied"

    # Test ignore duplicate
    state.mark_replied("youtube", "post123", "https://youtube.com/watch?v=123",
                       "Duplicate entry")
    assert state.get_reply_count() == 1, "Should still be 1 (unique constraint)"

    # Test skip
    state.mark_skipped("instagram", "post456", "https://instagram.com/p/456",
                       "spam post")
    assert state.get_reply_count() == 2
    assert state.get_reply_count("instagram") == 1

    # Test recent
    recent = state.get_recent_replies(5)
    assert len(recent) == 2

    print("  ✓ State manager tests passed")


def test_llm_reply_generator():
    """Test LLM reply generation (requires valid API key in .env)."""
    print("\n=== Testing LLM Reply Generator ===")

    config = load_config()
    llm_cfg = config.get("llm", {})

    api_key = llm_cfg.get("api_key", "")
    if not api_key or api_key == "your-api-key-here":
        print("  ⚠ No API key configured — skipping LLM test")
        print("    Set LLM_API_KEY in .env to run this test")
        return

    gen = ReplyGenerator(
        api_key=api_key,
        base_url=llm_cfg.get("base_url", "https://openrouter.ai/api/v1"),
        model=llm_cfg.get("model", "deepseek/deepseek-chat"),
    )

    # Test 1: Cantonese post about formaldehyde
    post1 = PostContext(
        platform="lihkg",
        post_url="https://lihkg.com/thread/12345",
        author="hk_homeowner",
        post_text="啱啱收樓，一入去就聞到好大陣甲醛味，有冇人試過自己除甲醛？定係一定要搵公司搞？",
        language="yue",
        timestamp="2026-07-21",
    )
    reply1 = gen.generate_reply(post1)
    print(f"\n  Test 1 (Cantonese, formaldehyde):")
    print(f"  Post: {post1.post_text}")
    print(f"  Reply: {reply1}")

    # Test 2: English post about air purifier
    post2 = PostContext(
        platform="facebook",
        post_url="https://facebook.com/post/67890",
        author="expat_hk",
        post_text="Any recommendations for air purifiers in HK? The humidity is killing me and my allergies are getting worse.",
        language="en",
        timestamp="2026-07-21",
    )
    reply2 = gen.generate_reply(post2)
    print(f"\n  Test 2 (English, air purifier):")
    print(f"  Post: {post2.post_text}")
    print(f"  Reply: {reply2}")

    # Test 3: Short Instagram reply
    post3 = PostContext(
        platform="instagram",
        post_url="https://instagram.com/p/abc",
        author="hk_foodie",
        post_text="新屋裝修完，想知點樣快啲除甲醛 😷",
        language="yue",
        timestamp="2026-07-21",
    )
    reply3 = gen.generate_reply(post3)
    print(f"\n  Test 3 (Cantonese, short):")
    print(f"  Post: {post3.post_text}")
    print(f"  Reply: {reply3}")

    print("\n  ✓ LLM reply generator tests completed")


def main():
    print("=" * 60)
    print("Pro-IAQ Monitor — Dry Run Test Suite")
    print("=" * 60)

    test_state_manager()
    test_llm_reply_generator()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
