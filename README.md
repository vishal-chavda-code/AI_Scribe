# AI Scribe

Meeting notes → structured minutes in seconds. Type raw notes during meetings, hit generate, refine with chat, finalize and copy to Outlook.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API credentials and file save path
```

## Run

```bash
streamlit run app.py
```

## Configuration (.env)

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Internal API key |
| `OPENAI_BASE_URL` | Internal endpoint URL |
| `OPENAI_MODEL` | Internal model name |
| `NOTES_ROOT` | Root folder for saved notes (e.g., SharePoint shortcut path) |
| `MAX_TOKENS` | Max response tokens (default 16384) |
| `LLM_TIMEOUT` | LLM request timeout in seconds (default 120) |

## Workflow

1. **Select meeting** from Outlook calendar or create an Unscheduled meeting
2. **Type notes** in the input area — messy is fine
3. **Capture** periodically to bank chunks (clears input, appends to buffer)
4. **Generate Notes** when meeting ends — sends all captured text to LLM
5. **Refine** via chat — request specific changes until satisfied
6. **Finalize** — saves raw input, structured text, and HTML to organized folders
7. **Copy HTML** — paste directly into Outlook reply

## File Structure

```
MeetingNotes/
└── 2026-02-28/
    ├── 01_0930_Risk_Committee_Review/
    │   ├── raw_input.txt
    │   ├── structured_output.txt
    │   └── structured_output.html
    └── 02_1400_Unscheduled_DataScience_Sync/
        ├── ...
```

## Outlook Calendar Integration

Requires Windows with Outlook desktop app. Falls back to Unscheduled mode on other systems. Install `pywin32` for calendar access:

```bash
pip install pywin32
```

## Notes

- Outlook HTML copy uses the Windows `win32clipboard` API with the `CF_HTML` format for rich paste directly into Outlook. If clipboard access fails, use the HTML download fallback.
- The LLM is instructed to never hallucinate. Missing info is marked `[unclear]` or `TBD`.
- Protective scrubbing is built into the prompt — personal commentary, editorializing, side conversations, and anything that could embarrass a participant or the scribe is silently removed. Substantive disagreements are preserved in professional language.
- Disclaimer `📋 Tool-Assisted Meeting Notes` is auto-prepended to every output.
