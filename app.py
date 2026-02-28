"""AI Scribe — Streamlit meeting notes structuring app."""

import datetime
import streamlit as st
from lib.llm_client import get_completion
from lib.prompts import (
    SYSTEM_PROMPT,
    REFINE_SYSTEM_PROMPT,
    build_generation_messages,
    build_refinement_messages,
)
from lib.file_manager import build_meeting_folder, save_meeting_files
from lib.html_formatter import markdown_to_outlook_html
from lib.outlook_cal import (
    is_available as outlook_available,
    get_todays_meetings,
    get_meeting_display_label,
    reply_to_meeting_with_notes,
)
from lib.clipboard import copy_html_to_clipboard, copy_text_to_clipboard

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="AI Scribe", page_icon="📋", layout="wide")

# ── Session state defaults ───────────────────────────────────────────────────
DEFAULTS = {
    "captured_chunks": [],
    "structured_output": None,
    "chat_history": [],
    "meeting_folder": None,
    "finalized": False,
    "phase": "capture",  # capture → review → finalized
    "outlook_meetings": None,
    "confirm_generate": False,
    "selected_meeting": None,  # full meeting dict from Outlook
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_session():
    """Reset all state for a new meeting."""
    for key, val in DEFAULTS.items():
        st.session_state[key] = val


# ── Sidebar: Meeting Setup ───────────────────────────────────────────────────
with st.sidebar:
    st.title("📋 AI Scribe")
    st.caption("Meeting notes → structured minutes")
    st.divider()

    # Meeting source
    source_options = ["Unscheduled"]
    if outlook_available():
        source_options.insert(0, "Outlook Calendar")

    meeting_source = st.radio("Meeting Source", source_options, horizontal=True)

    if meeting_source == "Outlook Calendar":
        if st.session_state.outlook_meetings is None:
            with st.spinner("Loading calendar..."):
                st.session_state.outlook_meetings = get_todays_meetings()

        meetings = st.session_state.outlook_meetings
        if meetings:
            labels = [get_meeting_display_label(m) for m in meetings]
            selected_idx = st.selectbox(
                "Select Meeting", range(len(labels)), format_func=lambda i: labels[i]
            )
            selected_meeting = meetings[selected_idx]
            st.session_state.selected_meeting = selected_meeting
            meeting_subject = selected_meeting["subject"]
            meeting_time = selected_meeting["start_time"].replace(":", "")
            st.caption(f"Organizer: {selected_meeting.get('organizer', 'N/A')}")
            if selected_meeting.get("attendees"):
                st.caption(f"Attendees: {', '.join(selected_meeting['attendees'][:5])}")
        else:
            st.warning("No meetings found for today. Using Unscheduled mode.")
            meeting_source = "Unscheduled"
            meeting_subject = ""
            meeting_time = None

    if meeting_source == "Unscheduled":
        meeting_subject = st.text_input("Meeting Subject", placeholder="e.g., Data Science Sync")
        meeting_time = None

    key_player = st.text_input("Key Player / Contact", placeholder="e.g., J. Smith")

    st.divider()

    # New meeting button
    if st.button("🔄 New Meeting", use_container_width=True):
        reset_session()
        st.rerun()

    # Status indicator
    st.divider()
    phase = st.session_state.phase
    if phase == "capture":
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

    # Show accumulated notes so far
    if st.session_state.captured_chunks:
        with st.expander(
            f"📄 Captured so far ({len(st.session_state.captured_chunks)} segments)",
            expanded=True,
        ):
            for i, chunk in enumerate(st.session_state.captured_chunks, 1):
                st.text(f"[{i}] {chunk}")

    # ── Enter-to-capture: form submits on Enter ─────────────────────────────
    with st.form(key="capture_form", clear_on_submit=True):
        notes_input = st.text_input(
            "Type a note and press Enter to capture",
            key="notes_input_field",
            placeholder="Type a thought... press Enter to bank it. Messy is fine.",
        )
        submitted = st.form_submit_button("📌 Capture", use_container_width=True)
        if submitted and notes_input.strip():
            st.session_state.captured_chunks.append(notes_input.strip())
            st.session_state.confirm_generate = False  # reset confirmation on new input
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
                    full_notes = "\n\n".join(st.session_state.captured_chunks)
                    with st.spinner("Generating structured notes..."):
                        try:
                            messages = build_generation_messages(
                                raw_notes=full_notes,
                                meeting_subject=meeting_subject,
                                date=today_str,
                                key_player=key_player or "Not specified",
                            )
                            result = get_completion(SYSTEM_PROMPT, messages)
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
                full_notes = "\n\n".join(st.session_state.captured_chunks)
                with st.spinner("Applying changes..."):
                    try:
                        messages = build_refinement_messages(
                            raw_notes=full_notes,
                            current_output=st.session_state.structured_output,
                            chat_history=st.session_state.chat_history,
                            user_request=refine_input.strip(),
                        )
                        result = get_completion(REFINE_SYSTEM_PROMPT, messages)
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

                    raw_notes = "\n\n".join(st.session_state.captured_chunks)
                    html_output = markdown_to_outlook_html(st.session_state.structured_output)

                    paths = save_meeting_files(
                        meeting_folder=folder,
                        raw_notes=raw_notes,
                        structured_text=st.session_state.structured_output,
                        structured_html=html_output,
                    )

                    st.session_state.meeting_folder = folder
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
    html_output = markdown_to_outlook_html(st.session_state.structured_output)

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
