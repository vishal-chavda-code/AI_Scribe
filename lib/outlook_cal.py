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

    Searches the Inbox for the corresponding meeting request so the reply
    threads correctly under the original invite. Falls back to creating
    a new mail item addressed to all attendees if no invite is found.

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

        mail = None

        # Strategy 1: Find the meeting request in Inbox and ReplyAll to it
        # This preserves email threading in Outlook
        try:
            inbox = namespace.GetDefaultFolder(6)  # 6 = olFolderInbox
            items = inbox.Items
            # Search for the meeting request by subject
            meeting_filter = f"@SQL=\"urn:schemas:httpmail:subject\" LIKE '%{subject.replace(chr(39), chr(39)+chr(39))}%'"
            filtered = items.Restrict(meeting_filter)
            for item in filtered:
                # MeetingItem class = 53
                try:
                    if item.Class == 53 or item.MessageClass.startswith("IPM.Schedule"):
                        mail = item.ReplyAll()
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Strategy 2: Forward the appointment (loses threading but works)
        if mail is None:
            try:
                mail = appt.Forward()
                # Clear Forward recipients and re-add from attendees
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
            except Exception:
                pass

        # Strategy 3: New mail item as last resort
        if mail is None:
            mail = outlook.CreateItem(0)  # 0 = olMailItem
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
