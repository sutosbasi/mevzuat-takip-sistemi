"""
Bildirim modülü - Masaüstü bildirimleri ve e-posta gönderimi.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


# ============================================================
# MASAÜSTÜ BİLDİRİMİ
# ============================================================

def masaustu_bildirim(baslik: str, mesaj: str, sure: int = 10):
    """Windows masaüstü bildirimi gönderir."""
    try:
        from plyer import notification
        notification.notify(
            title=baslik,
            message=mesaj,
            app_name="Mevzuat Takip Sistemi",
            timeout=sure,
        )
        print(f"🔔 Bildirim gönderildi: {baslik}")
        return True
    except Exception as e:
        print(f"⚠️  Bildirim gönderilemedi: {e}")
        return False


# ============================================================
# E-POSTA BİLDİRİMİ (Opsiyonel)
# ============================================================

# E-posta ayarları (ortam değişkenlerinden okunur)
SMTP_SUNUCU = os.getenv("SMTP_SUNUCU", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_KULLANICI = os.getenv("SMTP_KULLANICI", "")
SMTP_SIFRE = os.getenv("SMTP_SIFRE", "")
ALICI_EMAIL = os.getenv("ALICI_EMAIL", "")


def eposta_bildirim(konu: str, icerik_html: str):
    """E-posta bildirimi gönderir (yapılandırılmışsa)."""
    if not SMTP_KULLANICI or not SMTP_SIFRE or not ALICI_EMAIL:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = konu
        msg["From"] = SMTP_KULLANICI
        msg["To"] = ALICI_EMAIL

        msg.attach(MIMEText(icerik_html, "html", "utf-8"))

        with smtplib.SMTP(SMTP_SUNUCU, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_KULLANICI, SMTP_SIFRE)
            server.send_message(msg)

        print(f"📧 E-posta gönderildi: {konu}")
        return True
    except Exception as e:
        print(f"⚠️  E-posta gönderilemedi: {e}")
        return False


# ============================================================
# YÜKSEK SEVİYE BİLDİRİM FONKSİYONLARI
# ============================================================

def revizyon_bildir(mevzuat_baslik: str, degisiklik_basligi: str, tarih):
    """Revizyon bildirimi gönderir."""
    baslik = "📋 Mevzuat Güncellemesi"
    mesaj = f"{mevzuat_baslik}\n\n{degisiklik_basligi}\nTarih: {tarih}"
    masaustu_bildirim(baslik, mesaj)

    eposta_html = f"""
    <h2>Mevzuat Güncellemesi</h2>
    <p><strong>Mevzuat:</strong> {mevzuat_baslik}</p>
    <p><strong>Değişiklik:</strong> {degisiklik_basligi}</p>
    <p><strong>Tarih:</strong> {tarih}</p>
    """
    eposta_bildirim(f"Mevzuat Güncellemesi: {mevzuat_baslik}", eposta_html)


def oneri_bildir(oneriler: list):
    """Yeni mevzuat önerilerini bildirir."""
    if not oneriler:
        return

    baslik = f"💡 {len(oneriler)} Yeni Mevzuat Önerisi"
    mesaj = "\n".join([f"• {o.baslik[:80]}" for o in oneriler[:5]])
    if len(oneriler) > 5:
        mesaj += f"\n... ve {len(oneriler) - 5} tane daha"

    masaustu_bildirim(baslik, mesaj)

    oneri_html = "<h2>Yeni Mevzuat Önerileri</h2><ul>"
    for o in oneriler[:20]:
        oneri_html += f'<li><strong>{o.baslik}</strong><br/><a href="{o.url}">{o.url}</a></li>'
    oneri_html += "</ul>"
    eposta_bildirim(f"{len(oneriler)} Yeni Mevzuat Önerisi", oneri_html)


def tarama_ozeti_bildir(revizyon_sayisi: int, oneri_sayisi: int):
    """Tarama özeti bildirimi gönderir."""
    if revizyon_sayisi == 0 and oneri_sayisi == 0:
        return  # Değişiklik yoksa bildirim gönderme

    baslik = "🔍 Resmî Gazete Tarama Sonucu"
    mesaj = f"Revizyon: {revizyon_sayisi}\nYeni Öneri: {oneri_sayisi}"
    masaustu_bildirim(baslik, mesaj, sure=15)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("Test bildirimi gönderiliyor...")
    masaustu_bildirim(
        "Mevzuat Takip Sistemi",
        "Bu bir test bildirimidir. Bildirim sistemi çalışıyor!",
        sure=5,
    )
    print("Test tamamlandı.")