# -*- coding: utf-8 -*-
import re
from bs4 import BeautifulSoup
import requests
from database import Mevzuat, SessionLocal


def clean_mevzuat_html(html_content: str) -> str:
    if not html_content or len(html_content.strip()) < 50:
        return "<p style='color:red;'>Mevzuat metni çekilemedi veya boş içerik döndü.</p>"

    soup = BeautifulSoup(html_content, "html.parser")

    # Gereksiz ve düzen bozucu öğeleri temizle
    for tag in soup(["script", "style", "nav", "header", "footer", "iframe", "form", "button", "a", "img"]):
        tag.extract()

    # Tablo yapılarını düzleştir (metin yapışmasın)
    for table in soup.find_all("table"):
        table.replace_with(soup.new_string("\n" + table.get_text(separator="\n") + "\n"))

    main_area = (
        soup.find("div", {"id": "fck_content"})
        or soup.find("div", class_=re.compile(r"content|mevzuat|text|body", re.I))
        or soup.find("body")
        or soup
    )

    raw_text = main_area.get_text(separator="\n", strip=True)

    # Yapışık Maddeleri ve Fıkraları Zorunlu Satır Başlarına Kır
    formatted_text = re.sub(r"(?i)(?=(?:MADDE|GEÇİCİ MADDE)\s+\d+)", "\n\n", raw_text)
    formatted_text = re.sub(r"(?i)(?=\n?\(\d+\)\s+)", "\n", formatted_text)
    formatted_text = re.sub(r"(?i)(?=\n?[a-zçğıöşü]\)\s+)", "\n", formatted_text)

    raw_lines = [line.strip() for line in formatted_text.splitlines() if line.strip()]

    # Kopmuş "MADDE" ve "1" ifadelerini tek satırda birleştir
    lines = []
    i = 0
    while i < len(raw_lines):
        current = raw_lines[i]
        if any(x in current for x in ["Mevzuat Bilgi Sistemi", "T.C. CUMHURBAŞKANLIĞI", "Mevzuat Türü", "Kanunlar Fihristi"]):
            i += 1
            continue

        if re.match(r"^(MADDE|GEÇİCİ MADDE)$", current, re.I) and i + 1 < len(raw_lines):
            next_line = raw_lines[i + 1]
            if re.match(r"^\d+", next_line):
                lines.append(f"{current} {next_line}")
                i += 2
                continue
        lines.append(current)
        i += 1

    clean_blocks = []

    # Tipografi CSS
    css_style = """
    <style>
        .mevzuat-wrapper { font-family: 'Segoe UI', -apple-system, Roboto, sans-serif; color: #0f172a; line-height: 1.85; font-size: 14px; max-width: 960px; margin: 0 auto; padding: 20px; }
        .m-ana-baslik { color: #0284c7; font-size: 20px; font-weight: 800; border-bottom: 3px solid #0284c7; padding-bottom: 8px; margin-top: 30px; margin-bottom: 20px; text-transform: uppercase; }
        .m-bolum-baslik { color: #0f172a; font-size: 16px; font-weight: 800; margin-top: 32px; margin-bottom: 12px; background-color: #f1f5f9; padding: 6px 12px; border-radius: 4px; text-transform: uppercase; }
        .m-madde-box { background-color: #eff6ff; border-left: 6px solid #1d4ed8; padding: 10px 16px; margin-top: 28px; margin-bottom: 14px; font-weight: 800; color: #1e3a8a; font-size: 15px; border-radius: 0 6px 6px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.04); }
        .m-fikra-p { margin-bottom: 12px; text-align: justify; text-indent: 24px; color: #1e293b; margin-top: 6px; }
        .m-bend-p { margin-left: 40px; margin-bottom: 8px; text-align: justify; color: #334155; font-weight: 600; }
    </style>
    <div class="mevzuat-wrapper">
    """
    clean_blocks.append(css_style)

    for text in lines:
        if len(text) < 2 or text.startswith("http"):
            continue

        if re.match(r"^(VERGİ USUL KANUNU|KANUN|TEBLİĞ|GENEL TEBLİĞ)\b", text, re.I) and len(text) < 90:
            clean_blocks.append(f"<div class='m-ana-baslik'>{text}</div>")
        elif re.match(r"^(MADDE|GEÇİCİ MADDE)\s+\d+", text, re.I):
            clean_blocks.append(f"<div class='m-madde-box'>{text}</div>")
        elif re.match(r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ)\s+(BÖLÜM|KISIM)\b", text, re.I):
            clean_blocks.append(f"<div class='m-bolum-baslik'>{text}</div>")
        elif re.match(r"^([a-zçğıöşü]\)|[0-9]+\.|\(\d+\))\s+", text, re.I):
            clean_blocks.append(f"<div class='m-bend-p'>{text}</div>")
        else:
            clean_blocks.append(f"<div class='m-fikra-p'>{text}</div>")

    clean_blocks.append("</div>")
    return "".join(clean_blocks)


def fetch_and_save_mevzuat(mevzuat_url: str, mevzuat_no: str, baslik: str, tur: str) -> bool:
    db = SessionLocal()
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })

        target_url = mevzuat_url
        if mevzuat_no and mevzuat_no.strip() == "213":
            target_url = "https://www.mevzuat.gov.tr/MevzuatMetin/1.5.213.htm"

        res = session.get(target_url, timeout=15)
        res.encoding = res.apparent_encoding or "utf-8"

        soup = BeautifulSoup(res.text, "html.parser")
        frame = soup.find("frame", {"name": "main"}) or soup.find("iframe")
        if frame and frame.get("src"):
            src = frame["src"]
            if not src.startswith("http"):
                src = "https://www.mevzuat.gov.tr/" + src.lstrip("/")
            res = session.get(src, timeout=15)
            res.encoding = res.apparent_encoding or "utf-8"

        clean_body = clean_mevzuat_html(res.text)

        exists = db.query(Mevzuat).filter(Mevzuat.mevzuat_url == mevzuat_url).first()
        if exists:
            exists.icerik_html = clean_body
            exists.baslik = baslik
            exists.mevzuat_no = mevzuat_no
            exists.tur = tur
        else:
            new_m = Mevzuat(
                mevzuat_url=mevzuat_url,
                mevzuat_no=mevzuat_no,
                baslik=baslik,
                tur=tur,
                icerik_html=clean_body,
            )
            db.add(new_m)

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Fetch Error: {e}")
        return False
    finally:
        db.close()