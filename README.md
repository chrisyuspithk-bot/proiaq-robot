# Pro-IAQ Social Media Monitor + Intelligent Reply System

A fully automated Python system that monitors social media platforms for indoor air
quality (IAQ) discussions relevant to Pro-IAQ (Hong Kong), generates context-aware
replies using an LLM, and optionally posts them — all via browser automation.

---

## How It Works

```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────┐
│ Scheduler │ ──▶ │ Search       │ ──▶ │ Filter + │ ──▶ │ Post     │
│ (hourly/  │     │ (browser-use │     │ LLM      │     │ Reply    │
│  daily)   │     │  per platfm) │     │ Generate │     │ (optional)│
└──────────┘     └──────────────┘     └──────────┘     └──────────┘
                                             │
                                        ┌────▼─────┐
                                        │ SQLite   │
                                        │ State    │
                                        │ (no dups)│
                                        └──────────┘
```

---

## Supported Platforms

| Priority | Platform     | Domain(s)                        | Notes                          |
|----------|-------------|----------------------------------|---------------------------------|
| 1        | YouTube     | youtube.com                      | Videos + comments              |
| 2        | Facebook    | facebook.com                     | Public posts, pages, groups    |
| 3        | Instagram   | instagram.com                    | Visual + lifestyle             |
| 4        | LIHKG       | lihkg.com                        | Hong Kong discussion board     |
| 5        | Xiaohongshu | xiaohongshu.com                  | Lifestyle + discovery (小紅書) |
| 6        | X (Twitter) | x.com, twitter.com               | Real-time public discussion    |
| 7        | LinkedIn    | linkedin.com                     | Professional content           |

Each platform can be enabled/disabled independently in `config/config.yaml`.

---

## Quick Start

### Prerequisites

- Python ≥ 3.11
- An LLM API key (OpenRouter, DeepSeek direct, or any OpenAI-compatible endpoint)
- Playwright system dependencies (installed automatically)

### 1. Install

```bash
git clone <this-repo>
cd proiaq-monitor

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure

```bash
# Copy and edit environment file
cp .env.example .env
# Edit .env with your API keys and settings
```

Required settings in `.env`:
- `LLM_API_KEY` — Your OpenRouter or DeepSeek API key
- `LLM_BASE_URL` — API endpoint (default: OpenRouter)
- `LLM_MODEL` — Model name (default: `deepseek/deepseek-chat`)

Optional:
- `BROWSER_USE_API_KEY` — For Browser Use Cloud (stealth browsers)
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — For notifications

### 3. Create Browser Profiles (Login Once)

Each platform needs a persistent browser profile so logins survive across runs.
Uses raw Playwright — **no API key needed**, just `playwright install chromium`.

Run this ONCE per platform:

```bash
# Setup all platforms (one at a time):
python scripts/setup_profiles.py youtube
python scripts/setup_profiles.py facebook
python scripts/setup_profiles.py instagram
# ... etc for each platform you want to monitor
# Or do them all:
python scripts/setup_profiles.py all
```

A browser window will open. **Log in manually**, then close the window.
The session is saved to `data/profiles/<platform>/` and reused automatically.

### 4. Run

```bash
# Dry run: extract + generate replies WITHOUT posting (test first!)
python main.py --once --dry-run

# Run once (extract + reply + post)
python main.py --once

# Run on schedule (hourly or daily, per config.yaml)
python main.py

# Check status
python main.py --status
```

---

## Configuration Reference

### `config/config.yaml`

| Section | Key | Description | Default |
|---------|-----|-------------|---------|
| `platforms.<name>` | `enabled` | Enable/disable platform | `true` |
| `scheduler` | `mode` | `hourly`, `daily`, or `once` | `hourly` |
| `scheduler` | `hourly_interval` | Hours between runs | `1` |
| `scheduler` | `daily_time` | HH:MM for daily runs | `09:00` |
| `limits` | `max_posts_per_platform` | Posts to process per platform per run | `3` |
| `limits` | `post_max_age_hours` | Max post age for hourly mode | `48` |
| `limits` | `post_max_age_days` | Max post age for daily mode | `7` |
| `browser` | `engine` | `playwright` or `browser-use` | `playwright` |
| `browser` | `mode` | `local` or `cloud` (browser-use only) | `local` |
| `browser` | `headed` | Show browser window | `false` |
| `dry_run` | — | Extract + generate, don't post | `false` |

### `config/keywords.yaml`

Bilingual keyword sets used for search. Rotated per run to avoid pattern detection.
Add or remove keywords here to tune what the system searches for.

---

## Browser Engine: Playwright vs Browser-Use

Set via `BROWSER_ENGINE` in `.env` or `browser.engine` in `config.yaml`.

| | **playwright** (default) | **browser-use** |
|---|---|---|
| **How it works** | Direct CSS selectors per platform | LLM reads pages, decides what to click |
| **LLM tokens for control** | Zero — LLM only for reply generation | Every page action burns tokens |
| **Cost** | Free (just the reply LLM call) | ~$0.05–0.50 per task depending on model |
| **Reliability** | Breaks if platform changes its HTML | Adapts to UI changes automatically |
| **Anti-bot** | Needs manual stealth (user-agent, delays) | Cloud mode has built-in stealth |
| **Login handling** | Same persistent profiles | Same persistent profiles |
| **Speed** | Fast (direct DOM manipulation) | Slower (LLM thinks between actions) |

### Switching

```bash
# .env
BROWSER_ENGINE=playwright    # free, fast, direct selectors
BROWSER_ENGINE=browser-use   # LLM-driven, adapts to UI changes
```

Both engines share the same persistent browser profiles in `data/profiles/`,
so logins work regardless of which engine you use.

### Playwright selector maintenance

If a platform redesigns its UI, the CSS selectors in
`src/playwright_engine.py` → `PLATFORM_CONFIGS` may need updating.
Check the logs for `Playwright reply failed` or `Playwright search failed`
to identify broken selectors.

---

## Project Structure

```
proiaq-monitor/
├── main.py                   # CLI entry point
├── src/
│   ├── config.py             # Configuration management (YAML + .env)
│   ├── logging_config.py     # Structured logging (loguru + rotation)
│   ├── state.py              # SQLite persistent state (no duplicate replies)
│   ├── llm.py                # Reply generator + full bilingual knowledge base
│   ├── browser.py            # Browser-use wrapper + unified dispatch
│   ├── playwright_engine.py   # Raw Playwright engine (free, CSS selectors)
│   ├── orchestrator.py       # Core loop: search → filter → reply → post
│   ├── scheduler.py          # APScheduler + error recovery + notifications
│   └── platforms/
│       ├── base.py           # Abstract platform base class
│       ├── youtube.py        # YouTube search + reply templates
│       ├── facebook.py       # Facebook search + reply templates
│       ├── instagram.py      # Instagram search + reply templates
│       ├── lihkg.py          # LIHKG search + reply templates
│       ├── xiaohongshu.py    # Xiaohongshu search + reply templates
│       ├── x.py              # X/Twitter search + reply templates
│       └── linkedin.py       # LinkedIn search + reply templates
├── config/
│   ├── config.yaml           # Main configuration
│   └── keywords.yaml         # Bilingual keyword sets
├── data/                     # SQLite DB + browser profiles (gitignored)
│   └── profiles/             # Persistent browser sessions
├── logs/                     # Structured log files (rotated)
├── scripts/
│   └── setup_profiles.py     # One-time login setup helper
├── tests/
│   └── test_dry_run.py       # Dry-run test (state + LLM, no browser)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Docker Deployment

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Run manual dry-run
docker-compose run --rm proiaq-monitor python main.py --once --dry-run

# Setup profiles (requires headed browser — run locally, not in Docker)
# Mount the profiles directory back to your host after setup
```

**Note for Docker**: Browser profiles must be created on the host first
(run `scripts/setup_profiles.py` locally) and then mounted into the container.

---

## Dry Run Mode

**Always start with dry-run mode** to verify extraction and reply quality
before enabling actual posting:

```bash
python main.py --once --dry-run
```

In dry-run mode:
- Posts are searched and extracted normally
- LLM replies are generated
- Replies are **NOT** posted to any platform
- State is recorded with status `dry_run`
- The log shows what WOULD have been posted

---

## Adding a New Platform

1. Create a new file in `src/platforms/` (e.g., `src/platforms/threads.py`)
2. Implement the `BasePlatform` abstract class with `search_task()` and `reply_task()`
3. Register the platform in `src/orchestrator.py`'s `PLATFORM_CLASSES` dict
4. Add configuration in `config/config.yaml`
5. Add login URL to `scripts/setup_profiles.py`

---

## Adding New Keywords

Edit `config/keywords.yaml`. Each run picks a random subset of keywords.
English and Chinese keywords are mixed to ensure bilingual coverage.

---

## Safety Notes

### Platform Terms of Service

Automated interactions may violate platform ToS. Before deploying:
1. Review each platform's ToS regarding automated posting
2. Start with **dry-run mode** only
3. Consider rate limits: the system includes random delays (1–3 seconds)
   between actions, but you may want to increase these
4. Use a dedicated account — do not risk your personal account

### Rate Limiting

The system includes built-in rate limiting:
- Random delays between browser actions (configurable: `human_delay_min`/`max`)
- Cooldown between keyword searches on the same platform
- Coalesced scheduler jobs (no overlapping runs)

### Data Privacy

- Browser profiles contain session cookies — store them securely
- SQLite database stores only post IDs, URLs, timestamps, and reply text
- No user data is collected or stored beyond the post content needed for replies

### Recommendations

1. **Start in dry-run mode** for at least a week
2. Review generated replies manually via logs before enabling posting
3. Monitor the `data/state.db` to track what's been replied to
4. Keep the `max_posts_per_platform` low (1–2) initially
5. Use Browser Use Cloud for better stealth if you encounter anti-bot measures

---

## LLM Configuration

### OpenRouter (recommended)

```env
LLM_API_KEY=sk-or-v1-...
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-chat
```

### DeepSeek Direct

```env
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

### Any OpenAI-Compatible Provider

```env
LLM_API_KEY=your-key
LLM_BASE_URL=https://your-endpoint/v1
LLM_MODEL=your-model-name
```

---

## Reply Guidelines (built into the LLM prompt)

- Match the language of the original post (Cantonese/Chinese vs English)
- Be helpful first, promotional second
- Soft CTA: website, phone, WhatsApp — never hard-sell
- Concise on Instagram/X; can be longer on Facebook/LIHKG/YouTube
- Never claim medical results or 100% guarantees
- Sound like a knowledgeable local IAQ specialist

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `browser-use not installed` | Only needed if `BROWSER_ENGINE=browser-use`. Default playwright engine works without it. |
| Browser won't start | Run `playwright install chromium` to download the browser |
| Login lost between runs | Re-run `python scripts/setup_profiles.py <platform>` |
| LLM returns empty/generic reply | Check `LLM_API_KEY` and model name; try a different model |
| Duplicate replies | The SQLite unique constraint prevents this. Check `data/state.db` |
| `BROWSER_USE_API_KEY` error | Switch to `BROWSER_ENGINE=playwright` — no browser-use key needed |

---

## License

Internal use for Pro-IAQ Limited. Not for redistribution.

---

*This project was created by an AI agent (OpenHands).*
