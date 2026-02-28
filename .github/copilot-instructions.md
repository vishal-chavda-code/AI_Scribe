# AI Scribe — Project-Specific Copilot Instructions

> These rules are **additive** to the global instructions in `vishal-chavda-code/.github`.
> Only include things unique to this project here — shared standards live in the global file.

---

## Project Context

AI Scribe is a Streamlit app that converts messy meeting notes into structured professional
minutes via an LLM. It runs on Windows with Outlook desktop integration.

**Read `HANDOFF.md` first** for full architecture, deployment steps, and design rationale.

---

## Tech Stack Rules

- **Streamlit** is the UI framework — all UI goes through `st.*` calls, not HTML/JS
- **`openai` package** is used as a protocol client only — it points at an internal corporate
  LLM endpoint via `OPENAI_BASE_URL`. No data goes to OpenAI's cloud.
- **`pywin32`** handles all Windows COM automation (Outlook calendar, meeting replies, clipboard)
- **Never add `anthropic` as a dependency** — it was intentionally removed

---

## COM / Threading

Every function that touches Outlook or the Windows clipboard must:
1. Call `pythoncom.CoInitialize()` at the start
2. Call `pythoncom.CoUninitialize()` in a `finally` block
3. Never cache COM objects (`win32com.client.Dispatch`) across calls

This is because Streamlit runs callbacks on background threads that don't inherit the
main thread's COM apartment. Skipping this causes silent failures or `CoInitialize` errors.

---

## Session State

All session state keys are defined in the `DEFAULTS` dict at the top of `app.py`.
- Always add new keys to `DEFAULTS` — never create ad-hoc `st.session_state` keys elsewhere
- `reset_session()` restores all defaults — update it if you add new state
- The three phases are: `capture` → `review` → `finalized`

---

## Prompt Engineering

The system prompt in `lib/prompts.py` contains **protective scrubbing instructions** that
tell the LLM to silently remove personal commentary, editorializing, and anything that
could embarrass meeting participants. **Never remove or weaken these instructions** — they
are a compliance requirement for the financial services environment.

---

## Clipboard

The app uses `win32clipboard` with `CF_HTML` format for rich-text copy. The clipboard
must always be released in a `try/finally` block — if `CloseClipboard()` isn't called,
it locks the clipboard system-wide and breaks other apps (including Outlook paste).

---

## File Saving

Meeting notes save to `NOTES_ROOT` in this structure:
```
NOTES_ROOT/
└── 2026-02-28/              ← date folder
    └── 01_Meeting_Subject/  ← sequential number + sanitized subject
        ├── raw_notes.txt
        ├── structured_output.md
        └── structured_output.html
```

The `_sanitize_name()` function guards against Windows reserved names (CON, NUL, etc.)
and empty strings. Don't bypass it.
