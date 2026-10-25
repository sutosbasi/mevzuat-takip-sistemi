import asyncio
import datetime
import re
import sys
import os
from bs4 import BeautifulSoup
import requests

# mali-musavir-mcp'yi Python yoluna ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "musavir-mcp"))

from resmi_gazete_module import ResmiGazeteClient

from database import (
    Mevzuat,
    MevzuatOnerisi,
    MevzuatRevizyon,
    SessionLocal,
    TakipKelimesi,
)

from bildirim import tarama_ozeti_bildir, revizyon_bildir


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def normalize_metin(text: str) -> str:
    """Türkçe karakterleri normalize eder (arama için)."""
    return (
        text.lower()
        .replace("ı", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ç", "c")
        .replace("İ", "i")
        .replace("I", "i")
    )


def belge_turu_cikar(baslik: str) -> str:
    normalize = normalize_metin(baslik)
    if "yonetmeli" in normalize:
        return "Yönetmelik"
    if "tebli" in normalize:
        return "Tebliğ"
    if "sirkule" in normalize:
        return "Sirküler"
    if "genelge" in normalize:
        return "Genelge"
    if "kararname" in normalize:
        return "Kararname"
    if "kanun" in normalize:
        return "Kanun"
    if "duyuru" in normalize:
        return "Duyuru"
    if "karar" in normalize:
        return "Karar"
    return "Diğer"


def baslik_temizle(baslik: str) -> str:
    """Başlıktaki bozuk karakterleri, tireleri ve kirlilikleri temizler."""
    if not baslik:
        return ""

    temiz = baslik

    bozuk_karakterler = [
        "\u00ad",
        "\u200b",
        "\u200c",
        "\u200d",
        "\ufeff",
        "",
        "",
        "Â",
    ]
    for k in bozuk_karakterler:
        temiz = temiz.replace(k, "")

    temiz = re.sub(r"^[\–\—\-\:\s]+", "", temiz)
    temiz = temiz.strip()

    if temiz.lower() in ("pdf görüntüle", "pdf", ""):
        return ""

    return temiz


MEVZUAT_TURLERI = {"Kanun", "Yönetmelik", "Tebliğ", "Sirküler", "Genelge", "Kararname"}


# ============================================================
# İÇERİK ÇEKME
# ============================================================

def fetch_content_from_url(url: str) -> str:
    """Resmî Gazete veya mevzuat sayfasından okunabilir HTML metni çeker."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = res.apparent_encoding or "utf-8"

        soup = BeautifulSoup(res.text, "html.parser")
        for element in soup(
            ["script", "style", "nav", "footer", "header", "form", "iframe", "button"]
        ):
            element.extract()

        main_body = (
            soup.find("div", {"id": "fck_content"}) or soup.find("body") or soup
        )

        paragraphs = []
        for p in main_body.find_all(
            ["p", "div", "tr", "td", "h1", "h2", "h3", "h4"]
        ):
            text = p.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()

            if (
                text
                and len(text) > 10
                and not text.startswith("http")
                and "resmigazete.gov.tr" not in text
            ):
                if re.match(
                    r"^(MADDE|GEÇİCİ MADDE|BİRİNCİ BÖLÜM|İKİNCİ BÖLÜM|ÜÇÜNCÜ BÖLÜM|"
                    r"DÖRDÜNCÜ BÖLÜM|BEŞİNCİ BÖLÜM|ALTINCI BÖLÜM|KARAR)\b",
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
        return (
            clean_html
            if clean_html
            else "<p>Mevzuat metni ayrıştırılamadı veya boş.</p>"
        )
    except Exception as e:
        return f"<p>Metin çekilirken hata oluştu: {e}</p>"


# ============================================================
# GÜNLÜK TARAMA
# ============================================================

async def _fetch_daily_bulletin_async(target_date):
    client = ResmiGazeteClient()
    try:
        return await client.get_daily_bulletin(target_date)
    finally:
        await client.close()


def fetch_daily_bulletin_sync(target_date):
    """Async bülten çekmeyi, event loop durumuna göre güvenli şekilde çalıştırır."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                asyncio.run, _fetch_daily_bulletin_async(target_date)
            )
            return future.result()
    else:
        return asyncio.run(_fetch_daily_bulletin_async(target_date))


def check_daily_revisions_against_library(days_back: int = 15):
    db = SessionLocal()
    library_items = db.query(Mevzuat).all()
    keywords = [normalize_metin(k.kelime) for k in db.query(TakipKelimesi).all()]

    total_rev_count = 0
    total_sug_count = 0
    today = datetime.datetime.now().date()
    session_added_urls = set()

    print(f"🔍 Resmî Gazete tarama başlatıldı (Son {days_back} gün)...")
    print(
        f"   Kütüphanede {len(library_items)} mevzuat, {len(keywords)} takip kelimesi"
    )

    for i in range(days_back):
        target_date = today - datetime.timedelta(days=i)
        print(f"   📅 {target_date.strftime('%d.%m.%Y')} taranıyor...")

        try:
            bultens = fetch_daily_bulletin_sync(target_date)
        except Exception as e:
            print(f"   ⚠️  Hata ({target_date}): {e}")
            continue

        if not bultens:
            print(f"   ℹ️  Bu tarihte bülten yok.")
            continue

        print(f"   ✅ {len(bultens)} belge bulundu")

        for item in bultens:
            rg_title = baslik_temizle(item.baslik)
            if not rg_title or len(rg_title) < 5:
                continue

            full_url = item.detay_url
            if not full_url:
                continue

            tur = belge_turu_cikar(rg_title)
            rg_title_normalized = normalize_metin(rg_title)
            rg_title_lower = rg_title.lower()

            # A) Kütüphanedeki mevzuatlarla eşleştirme
            for m in library_items:
                clean_title = m.baslik.lower().strip()
                if clean_title in rg_title_lower or (
                    m.mevzuat_no and m.mevzuat_no in rg_title
                ):
                    exists = (
                        db.query(MevzuatRevizyon)
                        .filter(MevzuatRevizyon.degisiklik_url == full_url)
                        .first()
                    )
                    if not exists and full_url not in session_added_urls:
                        new_content_html = fetch_content_from_url(full_url)
                        new_rev = MevzuatRevizyon(
                            mevzuat_id=m.id,
                            resmi_gazete_tarihi=datetime.datetime.combine(
                                target_date, datetime.time()
                            ),
                            resmi_gazete_sayi=item.sayi,
                            degisiklik_basligi=rg_title,
                            degisiklik_url=full_url,
                            aciklama=(
                                f"{target_date.strftime('%d.%m.%Y')} tarihli "
                                f"Resmî Gazete'de yayımlanan değişiklik. (Tür: {tur})"
                            ),
                        )
                        db.add(new_rev)
                        update_header = (
                            f"<div style='background-color: #FEF3C7; padding: 10px; "
                            f"border-left: 4px solid #D97706; margin-bottom: 12px;'>"
                            f"<b>[GÜNCELLEME: {target_date.strftime('%d.%m.%Y')} - {rg_title}]</b></div>"
                        )
                        m.icerik_html = (
                            update_header
                            + new_content_html
                            + "<hr style='margin: 20px 0;'/>"
                            + (m.icerik_html or "")
                        )
                        m.son_guncelleme = datetime.datetime.combine(
                            target_date, datetime.time()
                        )
                        total_rev_count += 1
                        session_added_urls.add(full_url)
                        print(f"      🔄 Revizyon: {rg_title[:60]}...")
                        revizyon_bildir(
                            m.baslik, rg_title, target_date.strftime("%d.%m.%Y")
                        )

            # B) Takip kelimeleriyle eşleştirme
            if tur not in MEVZUAT_TURLERI:
                continue

            for kw in keywords:
                if kw in rg_title_normalized:
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
                            baslik=f"[{tur}] {rg_title} ({target_date.strftime('%d.%m.%Y')})",
                            url=full_url,
                            eslesen_kelime=kw,
                            tarih=datetime.datetime.combine(
                                target_date, datetime.time()
                            ),
                        )
                        db.add(new_sug)
                        total_sug_count += 1
                        session_added_urls.add(full_url)
                        print(f"      💡 Öneri: [{tur}] {rg_title[:60]}...")
                    break

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"❌ Veritabanı hatası: {e}")
    finally:
        db.close()

    print(f"✅ Tarama bitti: {total_rev_count} revizyon, {total_sug_count} öneri")

    # Tarama özeti bildirimi gönder
    if total_rev_count > 0 or total_sug_count > 0:
        tarama_ozeti_bildir(total_rev_count, total_sug_count)

    return total_rev_count + total_sug_count