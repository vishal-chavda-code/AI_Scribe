"""Outlook calendar integration via win32com. Gracefully degrades on non-Windows systems."""

import datetime

OUTLOOK_AVAILABLE = False

try:
    import win32com.client
    import pythoncom
    OUTLOOK_AVAILABLE = True
except ImportError:
    pass


def is_available() -> bool:
    """Check if Outlook COM integration is available."""
    return OUTLOOK_AVAILABLE


def get_todays_meetings() -> list[dict]:
    """Retrieve today's calendar items from Outlook.

    Returns:
        List of dicts with keys: subject, start_time, organizer, attendees
        Returns empty list if Outlook is unavailable.
    """
    if not OUTLOOK_AVAILABLE:
        return []

    try:
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        calendar = namespace.GetDefaultFolder(9)  # 9 = olFolderCalendar

        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)

        # Filter for today's appointments
        restriction = (
            f"[Start] >= '{today.strftime('%m/%d/%Y')} 12:00 AM' AND "
            f"[Start] < '{tomorrow.strftime('%m/%d/%Y')} 12:00 AM'"
        )
        appointments = calendar.Items
        appointments.Sort("[Start]")
        appointments.IncludeRecurrences = True
        filtered = appointments.Restrict(restriction)

        meetings = []
        for appt in filtered:
            attendee_list = []
            try:
                for recipient in appt.Recipients:
                    attendee_list.append(recipient.Name)
            except Exception:
                pass

            # Store EntryID so we can find this appointment later for reply
            entry_id = None
            try:
                entry_id = appt.EntryID
            except Exception:
                pass

            meetings.append({
                "subject": appt.Subject,
                "start_time": appt.Start.strftime("%H:%M"),
                "start_datetime": appt.Start,
                "organizer": appt.Organizer,
                "attendees": attendee_list,
                "entry_id": entry_id,
            })

        return meetings

    except Exception as e:
        print(f"Outlook calendar error: {e}")
        return []
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def get_meeting_display_label(meeting: dict) -> str:
    """Format a meeting dict for display in dropdown."""
    return f"{meeting['start_time']} — {meeting['subject']}"


def reply_to_meeting_with_notes(entry_id: str, html_body: str, subject: str) -> str:
    """Create a Reply-All to a meeting invite and populate with HTML notes.

    This finds the original meeting by EntryID, creates a ReplyAll on the
    associated email (forward if no direct mail item), sets the HTML body,
    and displays it for the user to review before sending.

    Args:
        entry_id: The Outlook EntryID of the calendar appointment.
        html_body: The formatted HTML meeting notes.
        subject: Meeting subject (used as fallback for subject line).

    Returns:
        Status message string.
    """
    if not OUTLOOK_AVAILABLE:
        return "Outlook COM not available."

    try:
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")

        # Get the appointment by EntryID
        appt = namespace.GetItemFromID(entry_id)

        # Try to create a ReplyAll — works on MeetingItem (the invite in inbox)
        # AppointmentItem doesn't have ReplyAll, so we forward instead
        try:
            # ForwardAsVcal won't work; use Forward to create a mail item
            # that goes to all attendees
            mail = appt.Forward()
        except Exception:
            # Fallback: create a new mail item
            mail = outlook.CreateItem(0)  # 0 = olMailItem
            mail.Subject = f"RE: {subject}"

        # Build recipient list from the appointment's attendees
        # Clear any pre-filled recipients from Forward and rebuild
        try:
            while mail.Recipients.Count > 0:
                mail.Recipients.Remove(1)
        except Exception:
            pass

        try:
            for recipient in appt.Recipients:
                mail.Recipients.Add(recipient.Address or recipient.Name)
        except Exception:
            pass

        mail.Subject = f"RE: {subject}"
        mail.HTMLBody = html_body
        mail.Display()  # Open for review — user clicks Send

        return "✓ Reply opened in Outlook — review and hit Send."

    except Exception as e:
        return f"Outlook reply error: {e}"
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
