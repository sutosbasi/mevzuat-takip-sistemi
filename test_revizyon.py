# -*- coding: utf-8 -*-
from database import SessionLocal, Mevzuat, MevzuatRevizyon
from gazete_scraper import fetch_content_from_url
import datetime

db = SessionLocal()
teblig = db.query(Mevzuat).filter(Mevzuat.tur == "Tebliğ").first()

if not teblig:
    print("HATA: Tebliğ bulunamadı!")
    db.close()
    exit()

print(f"Tebliğ: {teblig.baslik}")
print(f"Eski içerik uzunluğu: {len(teblig.icerik_html or '')} karakter")

# Mevcut test revizyonlarını sil
db.query(MevzuatRevizyon).delete()
db.commit()

# Gerçek bir HTML URL'si kullan
degisiklik_url = "https://www.resmigazete.gov.tr/eskiler/2026/10/20261024-10.htm"
degisiklik_basligi = "Vergi Usul Kanunu Genel Tebliği (Sıra No: 596)'nda Değişiklik Yapılmasına Dair Tebliğ (Sıra No: 597)"
target_date = datetime.datetime(2026, 10, 24)

# Yeni değişiklik metnini çek
print(f"\nDeğişiklik metni çekiliyor: {degisiklik_url}")
new_content_html = fetch_content_from_url(degisiklik_url)
print(f"Çekilen metin uzunluğu: {len(new_content_html)} karakter")

# Revizyon kaydı ekle
yeni_rev = MevzuatRevizyon(
    mevzuat_id=teblig.id,
    resmi_gazete_tarihi=target_date,
    resmi_gazete_sayi="20261024",
    degisiklik_basligi=degisiklik_basligi,
    degisiklik_url=degisiklik_url,
    aciklama=f"TEST: {target_date.strftime('%d.%m.%Y')} tarihli değişiklik.",
)
db.add(yeni_rev)

# Mevzuat metnini GÜNCELLE
update_header = (
    f"<div style='background-color: #FEF3C7; padding: 10px; "
    f"border-left: 4px solid #D97706; margin-bottom: 12px;'>"
    f"<b>[GÜNCELLEME: {target_date.strftime('%d.%m.%Y')} - {degisiklik_basligi}]</b></div>"
)
teblig.icerik_html = (
    update_header
    + new_content_html
    + "<hr style='margin: 20px 0;'/>"
    + (teblig.icerik_html or "")
)
teblig.son_guncelleme = target_date

db.commit()
db.refresh(teblig)

print(f"\n✅ Revizyon eklendi. ID: {yeni_rev.id}")
print(f"✅ Tebliğ güncellendi.")
print(f"Yeni içerik uzunluğu: {len(teblig.icerik_html or '')} karakter")
print(f"Son güncelleme: {teblig.son_guncelleme}")
print(f"\nİlk 500 karakter:")
print((teblig.icerik_html or '')[:500])

db.close()