"""Convert structured markdown output to Outlook-compatible HTML with inline styles."""

import re


def markdown_to_outlook_html(markdown_text: str) -> str:
    """Convert the structured meeting notes markdown to rich HTML for Outlook.

    Outlook's HTML renderer is notoriously limited, so this uses inline styles
    and simple HTML elements only. No external CSS, no <style> blocks.
    """
    lines = markdown_text.split("\n")
    html_parts = []
    in_table = False
    table_rows = []

    for line in lines:
        stripped = line.strip()

        # Horizontal rule
        if stripped == "---":
            if in_table:
                html_parts.append(_render_table(table_rows))
                table_rows = []
                in_table = False
            html_parts.append('<hr style="border:none;border-top:1px solid #ccc;margin:16px 0;">')
            continue

        # Table rows
        if "|" in stripped and stripped.startswith("|"):
            # Skip separator rows like |---|---|
            if re.match(r"^\|[\s\-|]+\|$", stripped):
                continue
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if not in_table:
                in_table = True
                table_rows = [cells]  # First row is header
            else:
                table_rows.append(cells)
            continue
        elif in_table:
            html_parts.append(_render_table(table_rows))
            table_rows = []
            in_table = False

        # Headers
        if stripped.startswith("## "):
            text = _inline_format(stripped[3:])
            html_parts.append(
                f'<h2 style="font-family:Calibri,Arial,sans-serif;font-size:16px;'
                f'color:#1a1a1a;margin:20px 0 8px 0;border-bottom:1px solid #ddd;'
                f'padding-bottom:4px;">{text}</h2>'
            )
        elif stripped.startswith("### "):
            text = _inline_format(stripped[4:])
            html_parts.append(
                f'<h3 style="font-family:Calibri,Arial,sans-serif;font-size:14px;'
                f'color:#333;margin:14px 0 6px 0;">{text}</h3>'
            )
        # Bullet points
        elif stripped.startswith("- "):
            text = _inline_format(stripped[2:])
            html_parts.append(
                f'<p style="font-family:Calibri,Arial,sans-serif;font-size:12px;'
                f'color:#333;margin:2px 0 2px 20px;padding-left:8px;">'
                f'• {text}</p>'
            )
        # Warning/disclaimer line
        elif stripped.startswith("📋"):
            text = _inline_format(stripped)
            html_parts.append(
                f'<p style="font-family:Calibri,Arial,sans-serif;font-size:11px;'
                f'color:#555;background:#f5f5f5;padding:8px 12px;'
                f'border-left:3px solid #888;margin:0 0 12px 0;">{text}</p>'
            )
        # Bold metadata lines (Meeting:, Date:, Key Contact:)
        elif stripped.startswith("**") and ":**" in stripped:
            text = _inline_format(stripped)
            html_parts.append(
                f'<p style="font-family:Calibri,Arial,sans-serif;font-size:12px;'
                f'color:#333;margin:2px 0;">{text}</p>'
            )
        # Empty lines
        elif not stripped:
            html_parts.append("")
        # Regular paragraph
        else:
            text = _inline_format(stripped)
            html_parts.append(
                f'<p style="font-family:Calibri,Arial,sans-serif;font-size:12px;'
                f'color:#333;margin:4px 0;">{text}</p>'
            )

    # Close any remaining table
    if in_table:
        html_parts.append(_render_table(table_rows))

    body = "\n".join(html_parts)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Calibri,Arial,sans-serif;font-size:12px;color:#333;max-width:700px;">
{body}
</body>
</html>"""


def _inline_format(text: str) -> str:
    """Handle bold and italic markdown inline."""
    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Italic: *text*
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text


def _render_table(rows: list[list[str]]) -> str:
    """Render a markdown table as an Outlook-compatible HTML table."""
    if not rows:
        return ""

    table_style = (
        'style="border-collapse:collapse;font-family:Calibri,Arial,sans-serif;'
        'font-size:12px;margin:8px 0;width:100%;"'
    )
    header_cell_style = (
        'style="border:1px solid #bbb;padding:6px 10px;background:#f0f0f0;'
        'font-weight:bold;text-align:left;"'
    )
    cell_style = (
        'style="border:1px solid #ddd;padding:6px 10px;text-align:left;"'
    )

    html = f"<table {table_style}>\n<thead><tr>\n"
    for cell in rows[0]:
        html += f"  <th {header_cell_style}>{_inline_format(cell)}</th>\n"
    html += "</tr></thead>\n<tbody>\n"

    for row in rows[1:]:
        html += "<tr>\n"
        for cell in row:
            html += f"  <td {cell_style}>{_inline_format(cell)}</td>\n"
        html += "</tr>\n"

    html += "</tbody></table>"
    return html
