"""AI Scribe — Streamlit meeting notes structuring app."""

import datetime
import streamlit as st
from lib.llm_client import get_completion, validate_llm_config
from lib.prompts import (
    get_system_prompt,
    get_refine_system_prompt,
    build_generation_messages,
    build_refinement_messages,
)
from lib.file_manager import build_meeting_folder, save_meeting_files, validate_notes_root
from lib.html_formatter import markdown_to_outlook_html
from lib.outlook_cal import (
    is_available as outlook_available,
    get_todays_meetings,
    get_meeting_display_label,
    reply_to_meeting_with_notes,
)
from lib.clipboard import copy_html_to_clipboard

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="AI Scribe", page_icon="📋", layout="wide")

# ── Session state defaults ───────────────────────────────────────────────────
DEFAULTS = {
    "captured_chunks": [],       # list of (timestamp_str, text) tuples
    "structured_output": None,
    "chat_history": [],
    "meeting_folder": None,
    "phase": "capture",          # capture → review → finalized
    "outlook_meetings": None,
    "confirm_generate": False,
    "confirm_new_meeting": False,
    "selected_meeting": None,    # full meeting dict from Outlook
    "direct_edit_mode": False,   # toggle for manual editing in review phase
    "meeting_confirmed": False,  # gate: user must explicitly confirm meeting choice
    "confirm_change_meeting": False,  # two-step unlock when notes exist
    "finalized_html": None,          # cached HTML output after finalization
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_session():
    """Reset all state for a new meeting."""
    for key, val in DEFAULTS.items():
        st.session_state[key] = val


# ── Pre-flight: validate NOTES_ROOT ──────────────────────────────────────────
_notes_ok, _notes_msg = validate_notes_root()
if not _notes_ok:
    st.error(f"⚠️ Storage path error: {_notes_msg}")
    st.stop()
_llm_ok, _llm_msg = validate_llm_config()
if not _llm_ok:
    st.error(f"⚠️ LLM config error: {_llm_msg}")
    st.stop()
# ── Sidebar: Meeting Setup ───────────────────────────────────────────────────
# Initialize sidebar-scoped variables with safe defaults
meeting_subject = ""
meeting_time = None
meeting_attendees: list[str] = []
meeting_body = ""
meetings = []  # safe default when Outlook branch is skipped

with st.sidebar:
    st.title("📋 AI Scribe")
    st.caption("Meeting notes → structured minutes")
    st.divider()

    # Meeting source
    source_options = ["Unscheduled"]
    if outlook_available():
        source_options.insert(0, "Outlook Calendar")

    meeting_source = st.radio(
        "Meeting Source", source_options, horizontal=True,
        disabled=st.session_state.meeting_confirmed,
    )

    if meeting_source == "Outlook Calendar":
        if st.session_state.outlook_meetings is None:
            with st.spinner("Loading calendar..."):
                st.session_state.outlook_meetings = get_todays_meetings()

        # Calendar refresh button
        if st.button("🔄 Refresh Calendar", use_container_width=True):
            st.session_state.outlook_meetings = get_todays_meetings()
            st.rerun()

        meetings = st.session_state.outlook_meetings
        if meetings:
            labels = [get_meeting_display_label(m) for m in meetings]
            selected_idx = st.selectbox(
                "Select Meeting", range(len(labels)), format_func=lambda i: labels[i],
                disabled=st.session_state.meeting_confirmed,
            )
            selected_meeting = meetings[selected_idx]
            st.session_state.selected_meeting = selected_meeting
            meeting_subject = selected_meeting["subject"]
            meeting_time = selected_meeting["start_time"].replace(":", "")
            meeting_attendees = selected_meeting.get("attendees", [])
            st.caption(f"Organizer: {selected_meeting.get('organizer', 'N/A')}")
            if meeting_attendees:
                st.caption(f"Attendees: {', '.join(meeting_attendees[:5])}")
                if len(meeting_attendees) > 5:
                    st.caption(f"  +{len(meeting_attendees) - 5} more")
            meeting_body = selected_meeting.get("body", "")
            if meeting_body:
                with st.expander("📄 Meeting Invite Body", expanded=False):
                    st.text(meeting_body[:2000] + ("..." if len(meeting_body) > 2000 else ""))
        else:
            st.warning("No meetings found for today. Using Unscheduled mode.")
            meeting_source = "Unscheduled"
            meeting_subject = ""
            meeting_time = None
            meeting_attendees = []
            meeting_body = ""

    if meeting_source == "Unscheduled":
        meeting_subject = st.text_input(
            "Meeting Subject", placeholder="e.g., Data Science Sync",
            disabled=st.session_state.meeting_confirmed,
        )
        meeting_time = None
        meeting_attendees = []
        meeting_body = ""

    key_player = st.text_input(
        "Key Player / Contact", placeholder="e.g., J. Smith",
        disabled=st.session_state.meeting_confirmed,
    )

    # ── Confirm / Lock-in meeting selection ──────────────────────────────────
    if not st.session_state.meeting_confirmed:
        _can_confirm = (
            (meeting_source == "Outlook Calendar" and meetings)
            or (meeting_source == "Unscheduled" and meeting_subject.strip())
        )
        if st.button(
            "🔒 Start Scribing",
            use_container_width=True,
            type="primary",
            disabled=not _can_confirm,
        ):
            st.session_state.meeting_confirmed = True
            st.rerun()
        if not _can_confirm and meeting_source == "Unscheduled":
            st.caption("Enter a meeting subject to begin.")
    else:
        st.success(f"🔒 Locked: **{meeting_subject}**")

        if not st.session_state.confirm_change_meeting:
            if st.button("🔓 Change Meeting", use_container_width=True):
                if st.session_state.captured_chunks or st.session_state.structured_output:
                    st.session_state.confirm_change_meeting = True
                    st.rerun()
                else:
                    st.session_state.meeting_confirmed = False
                    st.rerun()
        else:
            n = len(st.session_state.captured_chunks)
            st.warning(
                f"⚠️ You have **{n} captured segment{'s' if n != 1 else ''}**. "
                "Changing the meeting will **discard** all notes and output."
            )
            cm_keep, cm_discard, cm_cancel = st.columns([1, 1, 1])
            with cm_keep:
                if st.button("Keep & Switch", use_container_width=True, help="Unlock meeting but keep your notes"):
                    st.session_state.confirm_change_meeting = False
                    st.session_state.meeting_confirmed = False
                    st.rerun()
            with cm_discard:
                if st.button("Discard & Switch", use_container_width=True, type="primary"):
                    st.session_state.confirm_change_meeting = False
                    reset_session()
                    st.rerun()
            with cm_cancel:
                if st.button("Cancel", key="cancel_change", use_container_width=True):
                    st.session_state.confirm_change_meeting = False
                    st.rerun()

    st.divider()

    # New meeting button — with confirmation
    if not st.session_state.confirm_new_meeting:
        if st.button("🔄 New Meeting", use_container_width=True):
            if st.session_state.captured_chunks or st.session_state.structured_output:
                st.session_state.confirm_new_meeting = True
                st.rerun()
            else:
                reset_session()
                st.rerun()
    else:
        st.warning("⚠️ This will erase all captured notes and output.")
        cnm_yes, cnm_no = st.columns([1, 1])
        with cnm_yes:
            if st.button("Yes, reset", use_container_width=True, type="primary"):
                st.session_state.confirm_new_meeting = False
                reset_session()
                st.rerun()
        with cnm_no:
            if st.button("Cancel", key="cancel_new", use_container_width=True):
                st.session_state.confirm_new_meeting = False
                st.rerun()

    # Status indicator with segment/word count
    st.divider()
    phase = st.session_state.phase
    chunks = st.session_state.captured_chunks
    if phase == "capture":
        if chunks:
            total_words = sum(len(c[1].split()) for c in chunks)
            st.info(f"📝 **Capturing** — {len(chunks)} segments, ~{total_words} words")
        else:
            st.info("📝 **Capturing** — Type notes and press Enter")
    elif phase == "review":
        st.success("✏️ **Reviewing** — Refine output, then Finalize")
    elif phase == "finalized":
        st.success("✅ **Finalized** — Notes saved")


# ── Main area ────────────────────────────────────────────────────────────────
today_str = datetime.date.today().isoformat()

# ── CAPTURE PHASE ────────────────────────────────────────────────────────────
if st.session_state.phase == "capture":
    st.header("Meeting Notes Input")

    # Gate: must confirm meeting before capturing
    if not st.session_state.meeting_confirmed:
        st.info("👈 Select a meeting (or enter an Unscheduled subject) in the sidebar, then click **Start Scribing** to begin.")
        st.stop()

    # Show accumulated notes so far (with timestamps and delete buttons)
    if st.session_state.captured_chunks:
        with st.expander(
            f"📄 Captured so far ({len(st.session_state.captured_chunks)} segments)",
            expanded=True,
        ):
            delete_idx = None
            for i, (ts, text) in enumerate(st.session_state.captured_chunks):
                col_note, col_del = st.columns([10, 1])
                with col_note:
                    st.text(f"[{ts}] {text}")
                with col_del:
                    if st.button("✕", key=f"del_{i}", help="Delete this segment"):
                        delete_idx = i
            if delete_idx is not None:
                st.session_state.captured_chunks.pop(delete_idx)
                st.rerun()

    # ── Enter-to-capture: form submits on Enter ─────────────────────────────
    with st.form(key="capture_form", clear_on_submit=True):
        notes_input = st.text_input(
            "Type a note and press Enter to capture",
            key="notes_input_field",
            placeholder="Type a thought... press Enter to bank it. Messy is fine.",
        )
        submitted = st.form_submit_button("📌 Capture", use_container_width=True)
        if submitted and notes_input.strip():
            ts = datetime.datetime.now().strftime("%H:%M")
            st.session_state.captured_chunks.append((ts, notes_input.strip()))
            st.session_state.confirm_generate = False
            st.rerun()

    # ── Long note area ───────────────────────────────────────────────────────
    with st.expander("📝 Long Note (multi-line)"):
        long_note = st.text_area(
            "Paste or type a longer note here",
            key="long_note_area",
            height=150,
            placeholder="Use this for pasting larger blocks of text, agendas, etc.",
        )
        if st.button("📌 Capture Long Note", use_container_width=True):
            if long_note.strip():
                ts = datetime.datetime.now().strftime("%H:%M")
                st.session_state.captured_chunks.append((ts, long_note.strip()))
                st.session_state.confirm_generate = False
                st.rerun()

    # ── Generate Notes (with confirmation) ───────────────────────────────────
    can_generate = bool(st.session_state.captured_chunks)

    if not st.session_state.confirm_generate:
        if st.button(
            "🚀 Generate Notes",
            use_container_width=True,
            type="primary",
            disabled=not can_generate,
        ):
            st.session_state.confirm_generate = True
            st.rerun()
    else:
        st.warning(
            f"⚠️ All **{len(st.session_state.captured_chunks)} captured segments** will be "
            "combined and sent as a single prompt to the LLM. "
            "You can still refine the output afterwards."
        )
        col_yes, col_no = st.columns([1, 1])
        with col_yes:
            if st.button("✅ Yes, Generate", use_container_width=True, type="primary"):
                if not meeting_subject.strip():
                    st.error("Please enter a meeting subject in the sidebar.")
                else:
                    full_notes = "\n\n".join(text for _, text in st.session_state.captured_chunks)
                    with st.spinner("Generating structured notes..."):
                        try:
                            messages = build_generation_messages(
                                raw_notes=full_notes,
                                meeting_subject=meeting_subject,
                                date=today_str,
                                key_player=key_player or "Not specified",
                                attendees=meeting_attendees if meeting_attendees else None,
                                meeting_body=meeting_body if meeting_body else None,
                            )
                            result = get_completion(get_system_prompt(), messages)
                            st.session_state.structured_output = result
                            st.session_state.confirm_generate = False
                            st.session_state.phase = "review"
                            st.rerun()
                        except Exception as e:
                            st.error(f"LLM Error: {e}")
        with col_no:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_generate = False
                st.rerun()


# ── REVIEW PHASE ─────────────────────────────────────────────────────────────
elif st.session_state.phase == "review":
    st.header("Review & Refine")

    # Direct edit toggle
    st.session_state.direct_edit_mode = st.toggle(
        "✏️ Direct Edit Mode", value=st.session_state.direct_edit_mode
    )

    if st.session_state.direct_edit_mode:
        edited = st.text_area(
            "Edit the output directly:",
            value=st.session_state.structured_output,
            height=500,
            key="direct_edit_area",
        )
        if st.button("💾 Save Edits", use_container_width=True):
            st.session_state.structured_output = edited
            st.session_state.direct_edit_mode = False
            st.rerun()
    else:
        # Display current structured output
        st.markdown(st.session_state.structured_output)

    st.divider()

    # Refinement chat
    st.subheader("💬 Request Changes")
    st.caption("e.g., 'Remove the section about vendor pricing' or 'Change action item 2 owner to Sarah'")

    refine_input = st.text_input(
        "What would you like to change?",
        key="refine_input",
        placeholder="Type your change request...",
    )

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("🔄 Apply Change", use_container_width=True, type="secondary"):
            if refine_input.strip():
                full_notes = "\n\n".join(text for _, text in st.session_state.captured_chunks)
                with st.spinner("Applying changes..."):
                    try:
                        messages = build_refinement_messages(
                            raw_notes=full_notes,
                            current_output=st.session_state.structured_output,
                            chat_history=st.session_state.chat_history,
                            user_request=refine_input.strip(),
                        )
                        result = get_completion(get_refine_system_prompt(), messages)
                        st.session_state.structured_output = result
                        st.session_state.chat_history.append(
                            {"role": "user", "content": refine_input.strip()}
                        )
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": result}
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"LLM Error: {e}")
            else:
                st.warning("Enter a change request first.")

    with col2:
        if st.button("↩️ Back to Capture", use_container_width=True):
            st.session_state.phase = "capture"
            st.session_state.structured_output = None
            st.session_state.chat_history = []
            st.rerun()

    with col3:
        if st.button("✅ Finalize", use_container_width=True, type="primary"):
            if not meeting_subject.strip():
                st.error("Meeting subject is required.")
            else:
                with st.spinner("Saving..."):
                    is_unscheduled = meeting_source == "Unscheduled"
                    folder = build_meeting_folder(
                        meeting_subject=meeting_subject,
                        start_time=meeting_time if meeting_time else None,
                        is_unscheduled=is_unscheduled,
                    )

                    raw_notes = "\n\n".join(text for _, text in st.session_state.captured_chunks)
                    html_output = markdown_to_outlook_html(st.session_state.structured_output)

                    paths = save_meeting_files(
                        meeting_folder=folder,
                        raw_notes=raw_notes,
                        structured_text=st.session_state.structured_output,
                        structured_html=html_output,
                    )

                    st.session_state.meeting_folder = folder
                    st.session_state.finalized_html = html_output
                    st.session_state.phase = "finalized"
                    st.rerun()


# ── FINALIZED PHASE ──────────────────────────────────────────────────────────
elif st.session_state.phase == "finalized":
    st.header("✅ Notes Finalized")
    st.success(f"Saved to: `{st.session_state.meeting_folder}`")

    # Display the final output
    st.markdown(st.session_state.structured_output)
    st.divider()

    # ── Copy for Outlook ─────────────────────────────────────────────────────
    html_output = st.session_state.finalized_html or markdown_to_outlook_html(
        st.session_state.structured_output
    )

    st.subheader("📧 Send to Outlook")

    # Reply-to-meeting button (only if meeting was selected from Outlook calendar)
    selected = st.session_state.get("selected_meeting")
    if selected and selected.get("entry_id"):
        st.caption(
            f"Reply to: **{selected['subject']}** "
            f"({selected['start_time']}, organized by {selected.get('organizer', 'N/A')})"
        )
        if st.button("📨 Reply to Meeting in Outlook", use_container_width=True, type="primary"):
            result = reply_to_meeting_with_notes(
                entry_id=selected["entry_id"],
                html_body=html_output,
                subject=selected["subject"],
            )
            if result.startswith("✓"):
                st.success(result)
            else:
                st.error(result)
    else:
        st.info("No Outlook meeting selected — use the copy/download buttons below.")

    st.divider()
    st.caption("Or copy/download manually:")

    if st.button("📋 Copy to Clipboard", use_container_width=True):
        if copy_html_to_clipboard(html_output):
            st.success("✓ Copied! Paste into Outlook with Ctrl+V")
        else:
            st.error("Clipboard copy failed — use the download button below.")

    st.download_button(
        "⬇️ Download HTML file",
        data=html_output,
        file_name="meeting_notes.html",
        mime="text/html",
        use_container_width=True,
    )

    st.divider()
    if st.button("🔄 Start New Meeting", use_container_width=True, type="primary"):
        reset_session()
        st.rerun()
