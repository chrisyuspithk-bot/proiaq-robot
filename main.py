#!/usr/bin/env python3
"""
Pro-IAQ Social Media Monitor + Intelligent Reply System
========================================================

Usage:
    python main.py              # Run with schedule from config
    python main.py --once       # Run once and exit
    python main.py --dry-run    # Extract + generate replies without posting
    python main.py --status     # Show current stats

Environment:
    Copy .env.example to .env and fill in your keys before running.
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import load_config, load_keywords
from src.logging_config import setup_logging
from src.orchestrator import Orchestrator
from src.scheduler import Scheduler


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pro-IAQ Social Media Monitor & Reply System",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run one monitoring cycle and exit",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Extract posts + generate replies but do NOT post anything",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current system status and exit",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load configuration
    config = load_config()
    keywords = load_keywords()

    # Setup logging
    log_cfg = config.get("logging", {})
    setup_logging(
        log_level=log_cfg.get("level", "INFO"),
        log_dir=log_cfg.get("dir", "./logs"),
        rotation=log_cfg.get("rotation", "10 MB"),
        retention=log_cfg.get("retention", "30 days"),
    )

    # Override dry_run from CLI
    if args.dry_run:
        config["dry_run"] = True

    # Override scheduler mode
    if args.once:
        config["scheduler"]["mode"] = "once"

    # Build orchestrator
    orchestrator = Orchestrator(config=config, keywords=keywords)

    # Status mode
    if args.status:
        status = orchestrator.get_status()
        print("\n=== Pro-IAQ Monitor Status ===")
        print(f"Total replies tracked: {status['total_replies']}")
        print(f"Enabled platforms: {', '.join(status['enabled_platforms'])}")
        print(f"\nRecent replies:")
        for r in status["recent"]:
            print(f"  [{r['status']}] {r['platform']}: {r['url'][:80]}")
        return

    # Run
    scheduler = Scheduler(orchestrator=orchestrator, config=config)
    scheduler.start()


if __name__ == "__main__":
    main()
