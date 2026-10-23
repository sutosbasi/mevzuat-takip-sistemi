import difflib
from bs4 import BeautifulSoup


def extract_plain_text(html_content: str) -> str:
    """HTML kodlarını temizleyip saf metin satırları üretir."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def generate_text_diff(old_html: str, new_html: str) -> str:
    """HTML kodlarından tamamen arındırılmış saf metin karşılaştırması (Diff)

    üretir.
    """
    old_text = extract_plain_text(old_html) or "Eski metin bulunamadı."
    new_text = extract_plain_text(new_html) or "Yeni metin bulunamadı."

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    differ = difflib.HtmlDiff(wrapcolumn=60)
    diff_table = differ.make_table(
        old_lines,
        new_lines,
        fromdesc="Mevcut / Eski Metin",
        todesc="Resmî Gazete Değişikliği (Yeni Metin)",
        context=True,
        numlines=2,
    )

    custom_css = """
    <style>
        table.diff {font-family: Arial, sans-serif; font-size: 13px; width: 100%; border-collapse: collapse;}
        .diff_header {background-color: #f1f5f9; font-weight: bold; padding: 4px; border: 1px solid #cbd5e1;}
        td.diff_header {text-align: right; width: 30px;}
        .diff_next {background-color: #f8fafc;}
        .diff_add {background-color: #dcfce7; color: #15803d; font-weight: bold; text-decoration: none;}
        .diff_chg {background-color: #fef9c3; color: #a16207;}
        .diff_sub {background-color: #fee2e2; color: #b91c1c; text-decoration: line-through;}
        table.diff td {padding: 6px 10px; border: 1px solid #e2e8f0; vertical-align: top; word-break: break-word;}
    </style>
    """
    return custom_css + diff_table