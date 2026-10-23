import datetime
import re
from bs4 import BeautifulSoup
import requests
from database import (
    Mevzuat,
    MevzuatOnerisi,
    MevzuatRevizyon,
    SessionLocal,
    TakipKelimesi,
)


def fetch_content_from_url(url: str) -> str:
    """Sayfadaki gereksiz HTML ögelerini, linkleri ve menüleri temizleyerek

    yalnızca saf okunabilir mevzuat metnini ve maddelerini döndürür.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = "iso-8859-9" if "resmigazete" in url else "utf-8"

        soup = BeautifulSoup(res.text, "html.parser")

        # 1. Gereksiz HTML etiketlerini ve sayfa içi kalıntıları temizle
        for element in soup(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "form",
                "iframe",
                "button",
            ]
        ):
            element.extract()

        # 2. Resmî Gazete ana içerik gövdesini yakala
        main_body = (
            soup.find("div", {"id": "fck_content"})
            or soup.find("body")
            or soup
        )

        paragraphs = []
        for p in main_body.find_all(
            ["p", "div", "tr", "td", "h1", "h2", "h3", "h4"]
        ):
            text = p.get_text(strip=True)

            # Sayfa içi gereksiz linkleri ve yönlendirme metinlerini ele
            if (
                text
                and len(text) > 10
                and not text.startswith("http")
                and "resmigazete.gov.tr" not in text
            ):
                # Madde ve bölüm başlıklarını vurgula
                if re.match(
                    r"^(MADDE|GEÇİCİ MADDE|BİRİNCİ BÖLÜM|İKİNCİ BÖLÜM|ÜÇÜNCÜ BÖLÜM|KARAR)\b",
                    text,
                    re.I,
                ):
                    paragraphs.append(
                        f"<br/><b style='color: #1E3A8A; font-size: 15px;'>{text}</b><br/>"
                    )
                else:
                    paragraphs.append(
                        f"<p style='margin-bottom: 8px; line-height: 1.6; text-align: justify;'>{text}</p>"
                    )

        clean_html = "".join(paragraphs)
        return clean_html if clean_html else "<p>Mevzuat metni ayrıştırılamadı veya boş.</p>"

    except Exception as e:
        return f"<p>Metin çekilirken hata oluştu: {e}</p>"


def check_daily_revisions_against_library(days_back: int = 15):
    """Resmî Gazete'yi geriye dönük tarar, kütüphanedeki mevzuatlara ait

    revizyonları yakalayıp metinlerine işler ve takip kelimelerine uyan
    yeni içerikleri Öneriler sekmesine ekler.
    """
    db = SessionLocal()

    library_items = db.query(Mevzuat).all()
    keywords = [k.kelime.lower() for k in db.query(TakipKelimesi).all()]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    total_rev_count = 0
    total_sug_count = 0
    today = datetime.datetime.now()

    # Oturum içi çifte kayıt hatasını (IntegrityError) önleyen takip kümesi
    session_added_urls = set()

    print(
        f"🔍 Resmî Gazete geriye dönük tarama başlatıldı (Son {days_back} gün)..."
    )

    for i in range(days_back):
        target_date = today - datetime.timedelta(days=i)
        date_url_str = target_date.strftime("%Y%m%d")

        url = f"https://www.resmigazete.gov.tr/eskiler/{date_url_str[0:4]}/{date_url_str[4:6]}/{date_url_str}.htm"

        try:
            response = requests.get(url, headers=headers, timeout=8)
            if response.status_code != 200:
                continue

            response.encoding = "iso-8859-9"
            soup = BeautifulSoup(response.text, "html.parser")
            links = soup.find_all("a", href=True)

            for a in links:
                rg_title = a.get_text(strip=True)
                href = a["href"]

                if (
                    not rg_title
                    or len(rg_title) < 5
                    or "resmigazete.gov.tr" in rg_title
                ):
                    continue

                if href.startswith("./"):
                    full_url = f"https://www.resmigazete.gov.tr/eskiler/{date_url_str[0:4]}/{date_url_str[4:6]}/{href[2:]}"
                elif not href.startswith("http"):
                    full_url = f"https://www.resmigazete.gov.tr/eskiler/{date_url_str[0:4]}/{date_url_str[4:6]}/{href}"
                else:
                    full_url = href

                rg_title_lower = rg_title.lower()

                # A) Kütüphanedeki Mevcut Mevzuatlarla Eşleştirme VE İçerik Güncelleme
                for m in library_items:
                    clean_title = m.baslik.lower().strip()

                    # Örnek: "Kamu İhale Genel Tebliği" kütüphanedeyken gazetedeki "Kamu İhale Genel Tebliğinde Değişiklik Yapılmasına Dair Tebliğ" yakalanır
                    if clean_title in rg_title_lower or (
                        m.mevzuat_no and m.mevzuat_no in rg_title
                    ):
                        exists = (
                            db.query(MevzuatRevizyon)
                            .filter(MevzuatRevizyon.degisiklik_url == full_url)
                            .first()
                        )

                        if not exists and full_url not in session_added_urls:
                            # Değişiklik metnini gazeteden çek ve temizle
                            new_content_html = fetch_content_from_url(full_url)

                            new_rev = MevzuatRevizyon(
                                mevzuat_id=m.id,
                                resmi_gazete_tarihi=target_date,
                                resmi_gazete_sayi=date_url_str,
                                degisiklik_basligi=rg_title,
                                degisiklik_url=full_url,
                                aciklama=f"{target_date.strftime('%d.%m.%Y')} tarihli Resmî Gazete'de yayımlanan değişiklik metni eklendi.",
                            )
                            db.add(new_rev)

                            # Ana mevzuat metninin en üstüne yeni değişikliği belirgin şekilde işle
                            update_header = f"<div style='background-color: #FEF3C7; padding: 10px; border-left: 4px solid #D97706; margin-bottom: 12px;'>" \
                                            f"<b>[GÜNCELLEME: {target_date.strftime('%d.%m.%Y')} - {rg_title}]</b></div>"

                            m.icerik_html = (
                                update_header
                                + new_content_html
                                + "<hr style='margin: 20px 0;'/>"
                                + (m.icerik_html or "")
                            )
                            m.son_guncelleme = target_date

                            total_rev_count += 1
                            session_added_urls.add(full_url)

                # B) Anahtar Kelimeler ile Eşleştirme (Mevzuat Önerisi)
                for kw in keywords:
                    if kw in rg_title_lower:
                        if full_url in session_added_urls:
                            continue

                        in_lib = (
                            db.query(Mevzuat)
                            .filter(Mevzuat.mevzuat_url == full_url)
                            .first()
                        )
                        in_sug = (
                            db.query(MevzuatOnerisi)
                            .filter(MevzuatOnerisi.url == full_url)
                            .first()
                        )

                        if not in_lib and not in_sug:
                            new_sug = MevzuatOnerisi(
                                baslik=f"{rg_title} ({target_date.strftime('%d.%m.%Y')})",
                                url=full_url,
                                eslesen_kelime=kw,
                                tarih=target_date,
                            )
                            db.add(new_sug)
                            total_sug_count += 1
                            session_added_urls.add(full_url)

        except Exception as e:
            print(f"Hata ({date_url_str}): {e}")
            continue

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Veritabanı kayıt hatası engellendi: {e}")
    finally:
        db.close()

    print(
        f"✅ Tarama Bitti: Son {days_back} günde {total_rev_count} yeni revizyon ve {total_sug_count} yeni mevzuat önerisi işlendi."
    )
    return total_rev_count + total_sug_count