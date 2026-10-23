import difflib
from bs4 import BeautifulSoup


def extract_plain_text(html_content: str) -> str:
    if not html_content or str(html_content).strip() == "":
        return ""
    soup = BeautifulSoup(str(html_content), "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer", "a"]):
        tag.extract()

    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip()]
    return "\n".join(lines)


def generate_text_diff(old_html: str, new_html: str) -> str:
    old_text = extract_plain_text(old_html)
    new_text = extract_plain_text(new_html)

    if not old_text:
        old_text = "Mevcut mevzuat metni kütüphanede boş veya okunamadı."
    if not new_text:
        new_text = "Resmî Gazete değişiklik metni henüz çekilemedi veya bu revizyonda metin içeriği bulunmuyor."

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    differ = difflib.HtmlDiff(wrapcolumn=60)
    diff_table = differ.make_table(
        old_lines,
        new_lines,
        fromdesc="Mevcut Mevzuat Metni",
        todesc="Resmî Gazete Değişiklik Metni",
        context=True,
        numlines=2,
    )

    custom_css = """
    <style>
        table.diff {font-family: Arial, sans-serif; font-size: 13px; width: 100%; border-collapse: collapse;}
        .diff_header {background-color: #f1f5f9; font-weight: bold; padding: 4px; border: 1px solid #cbd5e1; text-align: right; width: 30px;}
        .diff_next {background-color: #f8fafc;}
        .diff_add {background-color: #dcfce7; color: #15803d; font-weight: bold;}
        .diff_chg {background-color: #fef9c3; color: #a16207;}
        .diff_sub {background-color: #fee2e2; color: #b91c1c; text-decoration: line-through;}
        table.diff td {padding: 6px 10px; border: 1px solid #e2e8f0; vertical-align: top; word-break: break-word;}
    </style>
    """
    return custom_css + diff_table