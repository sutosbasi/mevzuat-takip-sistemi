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
    """İki metni kelime kelime karşılaştırır, değişenleri renklendirir."""
    old_words = old_text.split()
    new_words = new_text.split()

    matcher = difflib.SequenceMatcher(None, old_words, new_words)

    old_html_parts = []
    new_html_parts = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_segment = " ".join(old_words[i1:i2])
        new_segment = " ".join(new_words[j1:j2])

        if tag == "equal":
            old_html_parts.append(f'<span class="diff-equal">{old_segment}</span> ')
            new_html_parts.append(f'<span class="diff-equal">{new_segment}</span> ')
        elif tag == "delete":
            old_html_parts.append(f'<span class="diff-del">{old_segment}</span> ')
        elif tag == "insert":
            new_html_parts.append(f'<span class="diff-ins">{new_segment}</span> ')
        elif tag == "replace":
            old_html_parts.append(f'<span class="diff-del">{old_segment}</span> ')
            new_html_parts.append(f'<span class="diff-ins">{new_segment}</span> ')

    return "".join(old_html_parts), "".join(new_html_parts)


def generate_text_diff(old_html: str, new_html: str) -> str:
    old_text = extract_plain_text(old_html)
    new_text = extract_plain_text(new_html)

    if not old_text:
        old_text = "Mevcut mevzuat metni henuz kutuphaneden cekilmedi."
    if not new_text:
        new_text = "Resmi Gazete'den yeni revizyon bildirimi alindi."

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    # Satır bazında değişen blokları bul
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    blocks = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        old_block_lines = old_lines[i1:i2]
        new_block_lines = new_lines[j1:j2]

        # Her satırı MAX_LINE_LENGTH ile sınırla
        old_block_text = " ".join(old_block_lines)[:MAX_LINE_LENGTH]
        new_block_text = " ".join(new_block_lines)[:MAX_LINE_LENGTH]

        # Kelime bazlı karşılaştırma
        old_formatted, new_formatted = kelime_bazli_diff(old_block_text, new_block_text)

        blocks.append({
            "old": old_formatted,
            "new": new_formatted,
        })

        if len(blocks) >= MAX_DIFF_LINES:
            break

    if not blocks:
        return "<p style='padding: 20px; background: #f0f9ff; border-radius: 6px; color: #0f172a;'>Değişiklik bulunamadı.</p>"

    html_parts = ["""
    <style>
        .diff-container {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
            line-height: 1.8;
        }
        .diff-block {
            margin-bottom: 16px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            overflow: hidden;
        }
        .diff-old {
            background-color: #fef2f2;
            padding: 12px 16px;
            border-bottom: 1px solid #fecaca;
        }
        .diff-new {
            background-color: #f0fdf4;
            padding: 12px 16px;
        }
        .diff-label {
            font-weight: 700;
            font-size: 11px;
            text-transform: uppercase;
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }
        .diff-label.old { color: #b91c1c; }
        .diff-label.new { color: #15803d; }
        .diff-text { color: #1e293b; word-break: break-word; }
        .diff-equal { color: #64748b; }
        .diff-del {
            background-color: #fecaca;
            color: #991b1b;
            text-decoration: line-through;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: 600;
        }
        .diff-ins {
            background-color: #bbf7d0;
            color: #14532d;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: 600;
        }
        .diff-more {
            padding: 10px;
            text-align: center;
            color: #64748b;
            font-style: italic;
            font-size: 12px;
        }
    </style>
    <div class="diff-container">
    """]

    for block in blocks:
        html_parts.append('<div class="diff-block">')

        if block["old"]:
            html_parts.append('<div class="diff-old">')
            html_parts.append('<div class="diff-label old">Kütüphanedeki Metin (eski)</div>')
            html_parts.append(f'<div class="diff-text">{block["old"]}</div>')
            html_parts.append('</div>')

        if block["new"]:
            html_parts.append('<div class="diff-new">')
            html_parts.append('<div class="diff-label new">Resmî Gazete Değişikliği (yeni)</div>')
            html_parts.append(f'<div class="diff-text">{block["new"]}</div>')
            html_parts.append('</div>')

        html_parts.append('</div>')

    total_changes = sum(1 for tag, _, _, _, _ in matcher.get_opcodes() if tag != "equal")
    if total_changes > len(blocks):
        html_parts.append(
            f'<div class="diff-more">... ve {total_changes - len(blocks)} değişiklik daha var (gösterilmiyor)</div>'
        )

    html_parts.append('</div>')
    return "".join(html_parts)