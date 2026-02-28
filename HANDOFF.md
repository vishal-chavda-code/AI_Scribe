# AI Scribe — Handoff Context for AI Assistant

> **Purpose:** This file gives you (the AI assistant) full context about this project so you can
> help the user deploy, debug, and iterate effectively. Read this before doing anything else.

---

## What This Project Is

AI Scribe is a **Streamlit web app** that converts messy, real-time meeting notes into structured
professional meeting minutes via an LLM. It runs locally on a Windows desktop with Outlook.

**User profile:** The owner is a non-engineer in financial services who built this entirely via
AI pair-programming. They understand the product deeply but may need help with Python internals.
Treat them as a capable product owner — explain *what* and *why*, not just *how*.

---

## Architecture

```
AI_Scribe/
├── app.py                  # Main Streamlit app — 3 phases: capture → review → finalized
├── .env                    # Local config (gitignored) — API keys, model, paths
├── .env.example            # Template for .env
├── .streamlit/config.toml  # toolbarMode=minimal (hides deploy button)
├── requirements.txt        # streamlit, openai, python-dotenv, pywin32
├── lib/
│   ├── llm_client.py       # OpenAI-compatible HTTP client (points at internal endpoint)
│   ├── prompts.py          # System prompts + message builders (date-aware, attendees, meeting body)
│   ├── file_manager.py     # Folder creation + file saving under NOTES_ROOT
│   ├── html_formatter.py   # Markdown → Outlook-compatible HTML (inline styles)
│   ├── outlook_cal.py      # Outlook COM integration (calendar read, reply-to-meeting)
│   └── clipboard.py        # win32clipboard CF_HTML copy for rich paste into Outlook
```

---

## Key Design Decisions

1. **The `openai` Python package is used as a protocol client only.** It connects to whatever
   `OPENAI_BASE_URL` is set in `.env`. No data goes to OpenAI's cloud. The env var names say
   `OPENAI_*` but they point at an internal corporate endpoint.

2. **Outlook COM via pywin32.** Calendar reads, meeting replies, and clipboard operations all use
   Windows COM. Every COM function calls `pythoncom.CoInitialize()` / `CoUninitialize()` because
   Streamlit runs callbacks on different threads.

3. **Session state drives everything.** The app has three phases (`capture`, `review`, `finalized`)
   tracked in `st.session_state.phase`. All state keys are defined in the `DEFAULTS` dict at the
   top of `app.py`. `reset_session()` restores all defaults.

4. **Meeting confirmation gate.** The user must explicitly click "Start Scribing" before the
   capture UI appears. Changing meetings with unsaved notes triggers a keep/discard/cancel dialog.

5. **Protective scrubbing is in the prompt, not in code.** The system prompt instructs the LLM to
   silently remove personal commentary, editorializing, and anything that could embarrass
   participants. This is a critical feature for a financial services environment.

6. **`captured_chunks` stores `(timestamp_str, text)` tuples.** Each captured segment gets an
   `HH:MM` timestamp. When joining for the LLM, use `"\n\n".join(text for _, text in chunks)`.

---

## First-Run Setup — Step by Step

Follow these steps in order. Each step must succeed before moving on. If the user doesn't
know an answer, help them find it — the details are all on their work machine.

---

### Step 1: Confirm Python is available

```powershell
python --version
```
Requires **Python 3.10 or newer** (the code uses `list[str] | None` union syntax from PEP 604).
If Python isn't installed, install it from https://www.python.org/downloads/ and make sure
"Add Python to PATH" is checked during installation.

---

### Step 2: Clone the repository

```powershell
git clone https://github.com/vishal-chavda-code/AI_Scribe.git
cd AI_Scribe\AI_Scribe
```
> **Note:** The working directory is the inner `AI_Scribe/AI_Scribe/` folder (where `app.py`
> lives), not the outer repo root.

If git isn't available, the user can download the ZIP from GitHub and unzip it manually.

---

### Step 3: Create a virtual environment (recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
This keeps dependencies isolated. The `.venv/` folder is already in `.gitignore`.

---

### Step 4: Install dependencies

```powershell
pip install -r requirements.txt
```
This installs exactly four packages:
- `streamlit>=1.30.0` — the web UI framework
- `openai>=1.12.0` — HTTP client for the LLM endpoint (protocol only, no data goes to OpenAI)
- `python-dotenv>=1.0.0` — loads `.env` config
- `pywin32>=306` — Windows COM automation (Outlook, clipboard)

If pip fails on `pywin32`, confirm you're on Windows (this app is Windows-only).

---

### Step 5: Get the LLM API key and endpoint URL

**This is the most important step.** The user needs three values from their internal LLM
platform (this is NOT OpenAI's cloud — it's whatever internal endpoint their company provides):

| What you need | Where to find it | Example |
|---------------|-----------------|---------|
| **API key** | The internal AI/ML platform portal, API keys section | `sk-abc123...` or a bearer token |
| **Base URL** | The platform docs or admin — must be the OpenAI-compatible URL | `https://llm.company.com/v1` |
| **Model name** | The platform's model catalog — pick the best available chat model | `gpt-4o`, `gpt-4.1`, or an internal model alias |

**How to verify the base URL format:** It must end in `/v1` (or wherever the platform's
`/chat/completions` endpoint lives). The app will POST to `{OPENAI_BASE_URL}/chat/completions`.

**Ask the user:** "What LLM endpoint do you use at work? Do you have an API key for it?
Where do you usually access it (a portal, a wiki page, etc.)?"

If the user doesn't have an API key yet, help them request one. Common internal platforms
include Azure OpenAI Service, AWS Bedrock, vLLM, or a custom deployment. Whichever it is,
the app just needs an OpenAI-compatible `/v1/chat/completions` endpoint.

---

### Step 6: Choose where to save meeting notes

The `NOTES_ROOT` folder is where the app saves `.md` and `.html` files for each meeting.
Good choices:
- A OneDrive/SharePoint-synced folder (auto-backed-up, accessible from other devices)
- A local folder like `C:/Users/USERNAME/Documents/MeetingNotes`

The folder will be created automatically if it doesn't exist. The user just needs to decide
the path. Use forward slashes in the path value.

---

### Step 7: Create the `.env` file

```powershell
Copy-Item .env.example .env
```

Then open `.env` in a text editor and fill in the real values:

```dotenv
# Replace ALL placeholder values below with real ones

# ── LLM Connection ──────────────────────────────────────
OPENAI_API_KEY=paste-your-real-api-key-here
OPENAI_BASE_URL=https://your-real-endpoint.company.com/v1
OPENAI_MODEL=your-model-name

# ── File Storage ─────────────────────────────────────────
NOTES_ROOT=C:/Users/YourName/OneDrive/MeetingNotes

# ── Optional (safe defaults already set) ─────────────────
MAX_TOKENS=16384
LLM_TIMEOUT=120
```

**Critical:** The app's preflight check rejects any key that starts with `your-`. Make sure
you replace every placeholder. The validation logic is in `lib/llm_client.py` →
`validate_llm_config()`, which checks both `OPENAI_API_KEY` and `OPENAI_BASE_URL`.

---

### Step 8: Ensure Outlook is running

Open **Microsoft Outlook desktop app** (not the web version). The app reads today's calendar
via COM automation and needs the desktop client running. If Outlook isn't open, the app still
works — it just defaults to "Unscheduled" mode without calendar integration.

---

### Step 9: Launch the app

```powershell
streamlit run app.py
```

This opens `http://localhost:8501` in your default browser. On first launch, two preflight
checks run automatically:

1. **NOTES_ROOT validation** — Checks the path exists (or creates it) and is writable.
   If this fails: fix the `NOTES_ROOT` path in `.env`.
2. **LLM config validation** — Checks that `OPENAI_API_KEY` and `OPENAI_BASE_URL` are set
   and don't contain placeholder values.
   If this fails: fix the API key and URL in `.env`, then refresh the browser.

If both pass, you'll see the app UI with the sidebar showing today's meetings.

---

### Step 10: Smoke test — verify everything works

Run through this checklist one item at a time:

- [ ] **App starts** — No red error banners at the top of the page
- [ ] **Calendar loads** — Sidebar shows today's meetings from Outlook (click 🔄 to refresh)
- [ ] **Select a meeting** — Pick any meeting and click "🔒 Start Scribing"
- [ ] **Capture a note** — Type "test note hello world" and press Enter or click Capture
- [ ] **Generate output** — Click "Generate" → confirm → LLM returns formatted minutes
- [ ] **Review phase** — Output appears with a Refine chat box and action buttons
- [ ] **Copy to clipboard** — Click "📋 Copy" → open Outlook → paste into a new email →
      verify it has formatted text (bold headers, bullet points), not raw HTML
- [ ] **Reply to meeting** — Click "Reply-to-Meeting" → Outlook reply/forward window opens
      with the minutes in the body
- [ ] **Save files** — Click "💾 Save" → check that folders appeared under `NOTES_ROOT`
      (structure: `NOTES_ROOT/2026-02-28/01_Meeting_Name/`)
- [ ] **New meeting** — Click "🔄 New Meeting" → confirm discard → app resets cleanly

**If the LLM call fails** with a connection error:
- Double-check `OPENAI_BASE_URL` — try opening it in a browser or curling it
- Check if VPN is required on the work machine
- Check if the API key has expired or needs activation

**If Outlook integration fails:**
- Make sure Outlook desktop (not web) is open and logged in
- The COM calls require the same Windows user session — don't run the app as a different user

---

### Step 11 (optional): Create a launch shortcut

For convenience, create a `run.bat` file in the project folder:

```bat
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
streamlit run app.py
```

Double-click `run.bat` to launch. The file is already in `.gitignore`.

---

### Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "Missing or placeholder values for: OPENAI_API_KEY" | `.env` not created or still has `your-` values | Fill in real values in `.env` |
| "NOTES_ROOT is not writable" | Path doesn't exist or is on a disconnected drive | Fix path in `.env` |
| `ModuleNotFoundError: No module named 'streamlit'` | Dependencies not installed | `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'win32com'` | pywin32 not installed or not on Windows | `pip install pywin32>=306` |
| LLM returns empty or errors | Wrong model name, expired key, or endpoint down | Verify all three LLM env vars |
| Calendar shows "Unscheduled" only | Outlook not open or COM permissions | Open Outlook desktop, retry |
| Clipboard paste shows raw HTML | CF_HTML registration failed | Restart the app; check `lib/clipboard.py` |
| `SyntaxError` on `list[str] | None` | Python < 3.10 | Upgrade Python to 3.10+ |

---

## Known Behaviors & Edge Cases

- **Outlook must be open** for calendar/reply features. If it's not, the app gracefully falls
  back to Unscheduled mode only.
- **`IncludeRecurrences`** is set before `.Sort()` in outlook_cal.py — this is required by
  Microsoft's documentation. If recurring meetings aren't showing, check this order.
- **Clipboard `try/finally`** guarantees `CloseClipboard()` is called even on error. If clipboard
  issues occur, check if another app has the clipboard locked.
- **The meeting invite body** (agenda, pre-reads) is passed to the LLM as supplementary context.
  If it contains excessive boilerplate (legal disclaimers, dial-in noise), the prompt instructs
  the LLM to treat raw notes as the primary source.
- **Chat history is trimmed to the last 4 entries** (2 exchanges) during refinement to avoid
  token bloat. Prior refinements are already baked into `current_output`.

---

## What To Watch For After First Real Use

These are the things the user should evaluate and come back to iterate on:

1. **Prompt quality** — Does the LLM output match the team's expectations for tone, format,
   and level of detail? The system prompt is in `lib/prompts.py` → `get_system_prompt()`.
2. **Meeting body noise** — If Outlook invite bodies add too much irrelevant context to the LLM
   input, consider adding a filter or truncation in `build_generation_messages()`.
3. **Token limits** — If output gets truncated on long meetings, increase `MAX_TOKENS` in `.env`.
   If input is too large, the API will return a context-length error — consider summarizing
   the meeting body before passing it.
4. **Reply threading** — The reply-to-meeting function uses 3 strategies (find meeting request
   in Inbox → forward appointment → new mail). Test with your Exchange setup to confirm which
   strategy works.
5. **Folder naming** — Check that `NOTES_ROOT` folder structure makes sense for how files get
   shared or synced (e.g., OneDrive/SharePoint).

---

## File-by-File Quick Reference

| File | Lines | What it does | Key functions |
|------|-------|-------------|---------------|
| `app.py` | ~490 | Main UI, session state, 3-phase flow | `reset_session()` |
| `lib/llm_client.py` | ~88 | LLM HTTP client with timeout, validation | `get_completion()`, `validate_llm_config()` |
| `lib/prompts.py` | ~164 | System prompts + message construction | `get_system_prompt()`, `build_generation_messages()`, `build_refinement_messages()` |
| `lib/file_manager.py` | ~135 | Folder creation, file saving, path validation | `build_meeting_folder()`, `save_meeting_files()`, `validate_notes_root()` |
| `lib/html_formatter.py` | ~148 | Markdown → Outlook HTML (inline styles) | `markdown_to_outlook_html()` |
| `lib/outlook_cal.py` | ~180 | Outlook COM: calendar read, meeting reply | `get_todays_meetings()`, `reply_to_meeting_with_notes()` |
| `lib/clipboard.py` | ~70 | win32clipboard CF_HTML copy | `copy_html_to_clipboard()` |

---

## Important: Do Not

- **Do not install or reference the `anthropic` package.** It was fully removed. The app uses
  only the `openai` package (as a protocol client for the internal endpoint).
- **Do not hardcode API keys.** Everything goes through `.env` which is gitignored.
- **Do not cache COM objects across Streamlit reruns.** Create fresh COM instances in each
  function call with `CoInitialize()`/`CoUninitialize()` pairs.
- **Do not remove the protective scrubbing instructions from the system prompt.** They are a
  critical compliance feature for the financial services environment.

---

*Generated 2026-02-28. Project repo: github.com/vishal-chavda-code/AI_Scribe*
