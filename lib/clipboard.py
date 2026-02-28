"""Windows clipboard helper — copies HTML in CF_HTML format for Outlook paste."""

import logging

logger = logging.getLogger(__name__)


def _build_cf_html(html_fragment: str) -> bytes:
    """Wrap an HTML fragment in the CF_HTML clipboard envelope.

    CF_HTML requires a specific header with byte-offset markers so that
    applications like Outlook know where the fragment starts/ends.
    """
    MARKER = "Version:0.9\r\nStartHTML:{:08d}\r\nEndHTML:{:08d}\r\nStartFragment:{:08d}\r\nEndFragment:{:08d}\r\n"
    prefix = "<html><body>\r\n<!--StartFragment-->"
    suffix = "<!--EndFragment-->\r\n</body></html>"

    # Calculate with placeholder lengths first
    dummy_header = MARKER.format(0, 0, 0, 0)
    start_html = len(dummy_header.encode("utf-8"))
    start_fragment = start_html + len(prefix.encode("utf-8"))
    end_fragment = start_fragment + len(html_fragment.encode("utf-8"))
    end_html = end_fragment + len(suffix.encode("utf-8"))

    header = MARKER.format(start_html, end_html, start_fragment, end_fragment)
    return (header + prefix + html_fragment + suffix).encode("utf-8")


def copy_html_to_clipboard(html: str) -> bool:
    """Copy HTML to Windows clipboard in CF_HTML format (rich paste in Outlook).

    Returns True on success, False on failure.
    """
    try:
        import win32clipboard
        import win32con

        CF_HTML = win32clipboard.RegisterClipboardFormat("HTML Format")
        cf_html_data = _build_cf_html(html)

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            # Also set plain-text version as fallback
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, html)
            win32clipboard.SetClipboardData(CF_HTML, cf_html_data)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        logger.error("Clipboard error: %s", e)
        return False


def copy_text_to_clipboard(text: str) -> bool:
    """Copy plain text to Windows clipboard.

    Returns True on success, False on failure.
    """
    try:
        import win32clipboard
        import win32con

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        logger.error("Clipboard error: %s", e)
        return False
