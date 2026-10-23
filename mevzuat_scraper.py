import re
from bs4 import BeautifulSoup
import requests
from database import Mevzuat, SessionLocal


def clean_mevzuat_html(html_content: str) -> str:
    if not html_content or len(html_content.strip()) < 50:
        return "<p style='color:red;'>Mevzuat metni çekilemedi veya boş içerik döndü.</p>"

    soup = BeautifulSoup(html_content, "html.parser")

    # Gereksiz ögeleri temizle
    for tag in soup(["script", "style", "nav", "header", "footer", "iframe", "form", "button", "a", "img"]):
        tag.extract()

    # Gövdeyi tespit et
    main_area = (
        soup.find("div", {"id": "fck_content"})
        or soup.find("div", class_=re.compile(r"content|mevzuat|text|body", re.I))
        or soup.find("body")
        or soup
    )

    clean_blocks = []

    # Şık Tipografi için Konteyner Başlangıcı
    clean_blocks.append("""
    <style>
        .mevzuat-container { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; color: #1e293b; line-height: 1.8; font-size: 14px; max-width: 900px; margin: 0 auto; padding: 15px; }
        .m-baslik-ana { color: #0f172a; font-size: 18px; font-weight: 700; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-top: 30px; margin-bottom: 15px; text-transform: uppercase; }
        .m-baslik-bolum { color: #1e3a8a; font-size: 15px; font-weight: 600; margin-top: 24px; margin-bottom: 10px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }
        .m-madde-kart { background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 10px 16px; margin-top: 20px; margin-bottom: 12px; font-weight: 700; color: #1e40af; border-radius: 0 6px 6px 0; font-size: 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .m-fikra { margin-bottom: 10px; text-align: justify; text-indent: 20px; color: #334155; }
        .m-bend { margin-left: 35px; margin-bottom: 6px; text-align: justify; color: #475569; }
    </style>
    <div class="mevzuat-container">
    """)

    for elem in main_area.find_all(["p", "div", "h1", "h2", "h3", "h4", "tr", "td", "span"]):
        text = elem.get_text(strip=True)

        if not text or len(text) < 3 or text.startswith("http"):
            continue

        if any(x in text for x in ["Mevzuat Bilgi Sistemi", "T.C. CUMHURBAŞKANLIĞI", "Mevzuat Türü", "Kanunlar Fihristi"]):
            continue

        # 1. Ana Kanun / Tebliğ İsmi
        if re.match(r"^(VERGİ USUL KANUNU|KANUN|TEBLİĞ|GENEL TEBLİĞ)\b", text, re.I) and len(text) < 80:
            clean_blocks.append(f"<div class='m-baslik-ana'>{text}</div>")

        # 2. Madde ve Geçici Madde Başlıkları (Kart Tasarımı)
        elif re.match(r"^(MADDE|GEÇİCİ MADDE)\s+\d+", text, re.I):
            clean_blocks.append(f"<div class='m-madde-kart'>{text}</div>")

        # 3. Bölüm / Kısım Başlıkları
        elif re.match(r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ)\s+(BÖLÜM|KISIM)\b", text, re.I):
            clean_blocks.append(f"<div class='m-baslik-bolum'>{text}</div>")

        # 4. Bendler (a), b), 1., 2. gibi alt maddeler)
        elif re.match(r"^([a-zçğıöşü]\)|[0-9]+\.)\s+", text, re.I):
            clean_blocks.append(f"<div class='m-bend'>{text}</div>")

        # 5. Standart Fıkra Paragrafları
        else:
            clean_blocks.append(f"<div class='m-fikra'>{text}</div>")

    clean_blocks.append("</div>") # Konteyner Kapanış
    result_html = "".join(clean_blocks)
    return result_html


def fetch_and_save_mevzuat(mevzuat_url: str, mevzuat_no: str, baslik: str, tur: str) -> bool:
    db = SessionLocal()
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        
        res = session.get(mevzuat_url, timeout=15)
        res.encoding = "utf-8"

        soup = BeautifulSoup(res.text, "html.parser")
        frame = soup.find("frame", {"name": "main"}) or soup.find("iframe")
        
        if frame and frame.get("src"):
            target_src = frame["src"]
            if not target_src.startswith("http"):
                target_src = "https://www.mevzuat.gov.tr/" + target_src.lstrip("/")
            res = session.get(target_src, timeout=15)
            res.encoding = "utf-8"

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