import re
from bs4 import BeautifulSoup
import requests
from database import Mevzuat, SessionLocal


def clean_mevzuat_html(html_content: str) -> str:
    """Sitenin navigasyon, header, footer, menü ve yönlendirme linklerini temizleyip

    yalnızca okunabilir madde ve kanun metnini döndürür.
    """
    if not html_content:
        return "<p>İçerik bulunamadı.</p>"

    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Menü, navigasyon, script, stil, header ve footer elemanlarını sök at
    for tag in soup(
        [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "iframe",
            "form",
            "button",
            "a",
        ]
    ):
        tag.extract()

    # 2. Ana içerik alanını yakala
    main_area = (
        soup.find("div", {"id": "fck_content"})
        or soup.find("div", class_=re.compile(r"content|mevzuat|text", re.I))
        or soup.find("body")
        or soup
    )

    clean_paragraphs = []
    for elem in main_area.find_all(
        ["p", "div", "h1", "h2", "h3", "h4", "tr", "td"]
    ):
        text = elem.get_text(strip=True)

        # Menü yazıları ve yönlendirme kalıntılarını filtrele
        if (
            text
            and len(text) > 8
            and not text.startswith("http")
            and "Mevzuat Bilgi Sistemi" not in text
            and "Cumhurbaşkanlığı" not in text
        ):
            # Madde ve Bölüm Başlıklarını Vurgula
            if re.match(
                r"^(MADDE|GEÇİCİ MADDE|BİRİNCİ BÖLÜM|İKİNCİ BÖLÜM|ÜÇÜNCÜ BÖLÜM|KANUN|TEBLİĞ)\b",
                text,
                re.I,
            ):
                clean_paragraphs.append(
                    f"<br/><b style='color:#1E3A8A; font-size:15px;'>{text}</b><br/>"
                )
            else:
                clean_paragraphs.append(
                    f"<p style='margin-bottom:8px; line-height:1.6; text-align:justify;'>{text}</p>"
                )

    result_html = "".join(clean_paragraphs)
    return (
        result_html
        if result_html
        else "<p>Mevzuat metni ayrıştırılamadı (Saf metin bulunamadı).</p>"
    )


def fetch_and_save_mevzuat(
    mevzuat_url: str, mevzuat_no: str, baslik: str, tur: str
) -> bool:
    """Verilen URL'den mevzuat içeriğini çeker, temizler ve veritabanına kaydeder."""
    db = SessionLocal()
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(mevzuat_url, headers=headers, timeout=12)
        res.encoding = "utf-8"

        # HTML içeriğini temizle
        clean_body = clean_mevzuat_html(res.text)

        exists = (
            db.query(Mevzuat).filter(Mevzuat.mevzuat_url == mevzuat_url).first()
        )
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
        print(f"Mevzuat çekme hatası: {e}")
        return False
    finally:
        db.close()