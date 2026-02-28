"""File manager for saving and organizing meeting notes."""

import os
import re
import datetime
from dotenv import load_dotenv

load_dotenv()

NOTES_ROOT = os.getenv("NOTES_ROOT", os.path.expanduser("~/MeetingNotes"))


def validate_notes_root() -> tuple[bool, str]:
    """Check if NOTES_ROOT is accessible and writable.

    Returns:
        Tuple of (is_valid, message).
    """
    if not os.path.exists(NOTES_ROOT):
        try:
            os.makedirs(NOTES_ROOT, exist_ok=True)
            return True, f"Created: {NOTES_ROOT}"
        except OSError as e:
            return False, f"Cannot create NOTES_ROOT '{NOTES_ROOT}': {e}"

    if not os.access(NOTES_ROOT, os.W_OK):
        return False, f"NOTES_ROOT '{NOTES_ROOT}' is not writable (permissions or offline?)."

    return True, NOTES_ROOT


_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})


def _sanitize_name(name: str) -> str:
    """Remove or replace characters that are invalid in folder/file names."""
    sanitized = re.sub(r'[<>:"/\\|?*]', "", name)
    sanitized = sanitized.strip(". ")
    sanitized = re.sub(r"\s+", "_", sanitized)
    sanitized = sanitized[:80]  # Cap length for filesystem safety
    # Guard against Windows reserved device names
    if sanitized.upper() in _WINDOWS_RESERVED:
        sanitized = f"_{sanitized}"
    # Guard against empty result (subject was all special chars)
    return sanitized or "untitled"


def _get_date_folder() -> str:
    """Get or create today's date folder."""
    today = datetime.date.today().isoformat()  # e.g., 2026-02-28
    date_path = os.path.join(NOTES_ROOT, today)
    os.makedirs(date_path, exist_ok=True)
    return date_path


def _get_next_sequence(date_folder: str) -> int:
    """Determine the next sequence number for today's meetings."""
    existing = [
        d for d in os.listdir(date_folder)
        if os.path.isdir(os.path.join(date_folder, d))
    ] if os.path.exists(date_folder) else []

    max_seq = 0
    for dirname in existing:
        try:
            seq = int(dirname.split("_")[0])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            pass

    return max_seq + 1


def build_meeting_folder(
    meeting_subject: str,
    start_time: str | None = None,
    is_unscheduled: bool = False,
) -> str:
    """Create and return the path for a meeting's output folder.

    Folder format: {seq}_{time}_{subject} or {seq}_{time}_Unscheduled_{subject}

    Args:
        meeting_subject: The meeting name or topic.
        start_time: Time string like '0930'. Defaults to current time.
        is_unscheduled: Whether this is an unscheduled/ad-hoc meeting.

    Returns:
        Full path to the created meeting folder.
    """
    date_folder = _get_date_folder()
    seq = _get_next_sequence(date_folder)

    if start_time is None:
        start_time = datetime.datetime.now().strftime("%H%M")

    subject_clean = _sanitize_name(meeting_subject)
    prefix = "Unscheduled_" if is_unscheduled else ""
    folder_name = f"{seq:02d}_{start_time}_{prefix}{subject_clean}"

    meeting_path = os.path.join(date_folder, folder_name)
    os.makedirs(meeting_path, exist_ok=True)
    return meeting_path


def save_meeting_files(
    meeting_folder: str,
    raw_notes: str,
    structured_text: str,
    structured_html: str,
) -> dict:
    """Save all meeting artifacts to the designated folder.

    Returns:
        Dict with paths to each saved file.
    """
    paths = {}

    raw_path = os.path.join(meeting_folder, "raw_input.txt")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_notes)
    paths["raw"] = raw_path

    txt_path = os.path.join(meeting_folder, "structured_output.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(structured_text)
    paths["txt"] = txt_path

    html_path = os.path.join(meeting_folder, "structured_output.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(structured_html)
    paths["html"] = html_path

    return paths
