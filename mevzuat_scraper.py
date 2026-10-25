# -*- coding: utf-8 -*-
import re
from bs4 import BeautifulSoup
import requests
from database import Mevzuat, SessionLocal


def clean_mevzuat_html(html_content: str) -> str:
    if not html_content or len(html_content.strip()) < 50:
        return "<p style='color:red;'>Mevzuat metni çekilemedi veya boş içerik döndü.</p>"

    soup = BeautifulSoup(html_content, "html.parser")

    # Gereksiz etiketleri temizle
    for tag in soup(
        ["script", "style", "nav", "header", "footer", "iframe", "form", "button", "a", "img"]
    ):
        tag.extract()

    # Tabloları düzleştir
    for table in soup.find_all("table"):
        table.replace_with(soup.new_string("\n" + table.get_text(separator="\n") + "\n"))

    main_area = (
        soup.find("div", {"id": "fck_content"})
        or soup.find("div", class_=re.compile(r"content|mevzuat|text|body", re.I))
        or soup.find("body")
        or soup
    )

    raw_text = main_area.get_text(separator="\n", strip=True)

    # Madde, fıkra ve bentleri zorunlu satır başlarına kır
    formatted_text = re.sub(r"(?i)(?=(?:MADDE|GEÇİCİ MADDE)\s+\d+)", "\n\n", raw_text)
    formatted_text = re.sub(r"(?i)(?=\n?\(\d+\)\s+)", "\n", formatted_text)
    formatted_text = re.sub(r"(?i)(?=\n?[a-zçğıöşü]\)\s+)", "\n", formatted_text)

    raw_lines = [line.strip() for line in formatted_text.splitlines() if line.strip()]

    # "MADDE" ve "1" ifadelerini birleştir
    lines = []
    i = 0
    while i < len(raw_lines):
        current = raw_lines[i]
        if any(
            x in current
            for x in [
                "Mevzuat Bilgi Sistemi",
                "T.C. CUMHURBAŞKANLIĞI",
                "Mevzuat Türü",
                "Kanunlar Fihristi",
            ]
        ):
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

    # HTML blokları oluştur
    clean_blocks = []

    # Koyu renkli, belirgin CSS
    css_style = """
    <style>
        .mevzuat-wrapper {
            font-family: 'Segoe UI', -apple-system, Roboto, sans-serif;
            color: #0f172a;
            line-height: 1.85;
            font-size: 14px;
            max-width: 960px;
            margin: 0 auto;
            padding: 20px;
        }
        .m-ana-baslik {
            color: #1e3a8a;
            font-size: 20px;
            font-weight: 900;
            border-bottom: 3px solid #1d4ed8;
            padding-bottom: 8px;
            margin-top: 30px;
            margin-bottom: 20px;
            text-transform: uppercase;
        }
        .m-bolum-baslik {
            color: #0f172a;
            font-size: 16px;
            font-weight: 900;
            margin-top: 32px;
            margin-bottom: 12px;
            background-color: #e0e7ff;
            padding: 10px 14px;
            border-radius: 4px;
            border-left: 5px solid #1d4ed8;
            text-transform: uppercase;
        }
        .m-madde-box {
            background-color: #dbeafe;
            border-left: 6px solid #1d4ed8;
            padding: 14px 18px;
            margin-top: 28px;
            margin-bottom: 16px;
            font-weight: 900;
            color: #0c1e4a;
            font-size: 15px;
            border-radius: 0 6px 6px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            line-height: 1.6;
        }
        .m-fikra-p {
            margin-bottom: 12px;
            text-align: justify;
            color: #1e293b;
            margin-top: 6px;
            padding-left: 8px;
        }
        .m-bend-p {
            margin-left: 24px;
            margin-bottom: 8px;
            text-align: justify;
            color: #334155;
            font-weight: 500;
            padding-left: 8px;
        }
    </style>
    <div class="mevzuat-wrapper">
    """
    clean_blocks.append(css_style)

    # Satırları işle
    i = 0
    while i < len(lines):
        text = lines[i]
        if len(text) < 2 or text.startswith("http"):
            i += 1
            continue

        # Ana başlık (KANUN, TEBLİĞ vb.)
        if (
            re.match(
                r"^(VERGİ USUL KANUNU|KANUN|TEBLİĞ|GENEL TEBLİĞ|YÖNETMELİK)\b",
                text,
                re.I,
            )
            and len(text) < 120
        ):
            clean_blocks.append(f"<div class='m-ana-baslik'>{text}</div>")
            i += 1
            continue

        # Madde başlığı — sonraki satır kısa bir başlıksa birleştir
        if re.match(r"^(MADDE|GEÇİCİ MADDE)\s+\d+", text, re.I):
            combined = text
            if i + 1 < len(lines):
                next_text = lines[i + 1]
                if (
                    len(next_text) < 80
                    and not re.match(r"^[\(\[]?\d", next_text)
                    and not re.match(r"^[a-zçğıöşü]\)", next_text)
                    and not re.match(
                        r"^(MADDE|GEÇİCİ MADDE|BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ)",
                        next_text,
                        re.I,
                    )
                ):
                    combined = f"{text} — {next_text}"
                    i += 1
            clean_blocks.append(f"<div class='m-madde-box'>{combined}</div>")
            i += 1
            continue

        # Bölüm başlığı
        if re.match(
            r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCI|ONUNCU)\s+(BÖLÜM|KISIM|AYRIM)\b",
            text,
            re.I,
        ):
            clean_blocks.append(f"<div class='m-bolum-baslik'>{text}</div>")
            i += 1
            continue

        # Bent (a), b), 1., 2., (1), (2))
        if re.match(r"^([a-zçğıöşü]\)|[0-9]+\.|\(\d+\))\s+", text, re.I):
            clean_blocks.append(f"<div class='m-bend-p'>{text}</div>")
            i += 1
            continue

        # Normal fıkra
        clean_blocks.append(f"<div class='m-fikra-p'>{text}</div>")
        i += 1

    clean_blocks.append("</div>")
    return "".join(clean_blocks)


def fetch_and_save_mevzuat(mevzuat_url: str, mevzuat_no: str, baslik: str, tur: str) -> bool:
    db = SessionLocal()
    try:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
        )

        target_url = mevzuat_url
        if mevzuat_no and mevzuat_no.strip() == "213":
            target_url = (
                "https://www.mevzuat.gov.tr/anasayfa/"
                "MevzuatFihristDetayIframe?MevzuatTur=1&MevzuatNo=213&MevzuatTertip=4"
            )

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