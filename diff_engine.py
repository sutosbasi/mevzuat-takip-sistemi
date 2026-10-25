import difflib
import re
from bs4 import BeautifulSoup


MAX_DIFF_LINES = 50
MAX_LINE_LENGTH = 500


def extract_plain_text(html_content: str) -> str:
    if not html_content or str(html_content).strip() == "":
        return ""
    soup = BeautifulSoup(str(html_content), "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "a"]):
        tag.extract()
    lines = []
    for line in soup.get_text(separator="\n").splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def kelime_bazli_diff(old_text: str, new_text: str) -> str:
    old_words = old_text.split()
    new_words = new_text.split()
    matcher = difflib.SequenceMatcher(None, old_words, new_words)

    parts = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_segment = " ".join(old_words[i1:i2])
        new_segment = " ".join(new_words[j1:j2])

        if tag == "equal":
            parts.append(f'<span style="color: #64748b;">{old_segment}</span> ')
        elif tag == "delete":
            parts.append(
                f'<span style="background-color: #fecaca; color: #991b1b; '
                f'text-decoration: line-through; font-weight: 600;">{old_segment}</span> '
            )
        elif tag == "insert":
            parts.append(
                f'<span style="background-color: #bbf7d0; color: #14532d; '
                f'font-weight: 600;">{new_segment}</span> '
            )
        elif tag == "replace":
            parts.append(
                f'<span style="background-color: #fecaca; color: #991b1b; '
                f'text-decoration: line-through; font-weight: 600;">{old_segment}</span> '
            )
            parts.append(
                f'<span style="background-color: #bbf7d0; color: #14532d; '
                f'font-weight: 600;">{new_segment}</span> '
            )

    return "".join(parts)


def generate_text_diff(old_html: str, new_html: str) -> str:
    old_text = extract_plain_text(old_html)
    new_text = extract_plain_text(new_html)

    if not old_text:
        old_text = "Mevcut mevzuat metni henuz kutuphaneden cekilmedi."
    if not new_text:
        new_text = "Resmi Gazete'den yeni revizyon bildirimi alindi."

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    blocks = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        old_block = " ".join(old_lines[i1:i2])[:MAX_LINE_LENGTH]
        new_block = " ".join(new_lines[j1:j2])[:MAX_LINE_LENGTH]

        combined = kelime_bazli_diff(old_block, new_block)

        blocks.append({"combined": combined})

        if len(blocks) >= MAX_DIFF_LINES:
            break

    if not blocks:
        return (
            '<div style="padding: 20px; background: #f0f9ff; border-radius: 6px;">'
            '<p style="margin: 0; color: #0f172a;">Degisiklik bulunamadi.</p></div>'
        )

    html_parts = ["""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; line-height: 1.8;">
        <div style="background: #f8fafc; padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; border-left: 4px solid #1d4ed8;">
            <p style="margin: 0; font-size: 12px; color: #475569;">
                <strong style="color: #b91c1c;">Kirmizi ustu cizili</strong> = eski metinde silinen &nbsp;|&nbsp;
                <strong style="color: #15803d;">Yesil</strong> = yeni metinde eklenen &nbsp;|&nbsp;
                <strong style="color: #64748b;">Gri</strong> = degismeyen
            </p>
        </div>
    """]

    for idx, block in enumerate(blocks, 1):
        html_parts.append(
            f'<div style="margin-bottom: 16px; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 16px; background: #ffffff;">'
            f'<div style="font-size: 11px; color: #94a3b8; font-weight: 700; margin-bottom: 6px;">DEGISIKLIK #{idx}</div>'
            f'<div style="color: #1e293b; word-break: break-word;">{block["combined"]}</div>'
            f'</div>'
        )

    total_changes = sum(1 for tag, _, _, _, _ in matcher.get_opcodes() if tag != "equal")
    if total_changes > len(blocks):
        html_parts.append(
            f'<div style="padding: 10px; text-align: center; color: #64748b; font-style: italic; font-size: 12px;">'
            f'... ve {total_changes - len(blocks)} degisiklik daha var (gosterilmiyor)</div>'
        )

    html_parts.append("</div>")
    return "".join(html_parts)