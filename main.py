import datetime
import re
from contextlib import asynccontextmanager
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (
    Mevzuat,
    MevzuatOnerisi,
    MevzuatRevizyon,
    SessionLocal,
    TakipKelimesi,
)
from diff_engine import generate_text_diff
from gazete_scraper import check_daily_revisions_against_library, fetch_content_from_url
from mevzuat_scraper import fetch_and_save_mevzuat

# --- OTOMATİK ZAMANLAYICI (SCHEDULER) VE LIFESPAN KURULUMU ---
scheduler = BackgroundScheduler()
scheduler.add_job(
    lambda: check_daily_revisions_against_library(), "interval", hours=2
)


def scheduled_daily_check():
    """Arka planda otomatik çalışacak Resmî Gazete tarama görevi."""
    print(
        f"⏰ [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Otomatik Resmî Gazete taraması başlatıldı..."
    )
    count = check_daily_revisions_against_library()
    print(
        f"✅ Otomatik tarama tamamlandı. Toplam tespit edilen yeni içerik: {count}"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Modern Yaşam Döngüsü Yöneticisi."""
    scheduler.start()
    print("🚀 Otomatik Görev Zamanlayıcı (APScheduler) başlatıldı.")

    import threading

    threading.Thread(target=scheduled_daily_check, daemon=True).start()

    yield
    scheduler.shutdown()
    print("🛑 Otomatik Görev Zamanlayıcı durduruldu.")


app = FastAPI(
    title="Mevzuat Kütüphanesi & Tam Otomatik Takip API",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- PYDANTIC MODELLERİ ---
class MevzuatEkleRequest(BaseModel):
    mevzuat_url: str
    mevzuat_no: str
    baslik: str
    tur: str


class MevzuatGuncelleRequest(BaseModel):
    mevzuat_url: Optional[str] = None
    mevzuat_no: Optional[str] = None
    baslik: Optional[str] = None
    tur: Optional[str] = None


class KelimeRequest(BaseModel):
    kelime: str


# --- MEVZUAT KÜTÜPHANESİ UÇ NOKTALARI ---


@app.post("/api/mevzuat/ekle")
def add_mevzuat_to_library(req: MevzuatEkleRequest):
    success = fetch_and_save_mevzuat(
        mevzuat_url=req.mevzuat_url,
        mevzuat_no=req.mevzuat_no,
        baslik=req.baslik,
        tur=req.tur,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Mevzuat eklenemedi.")
    return {"status": "success", "message": f"'{req.baslik}' kütüphaneye eklendi."}


@app.get("/api/mevzuat/liste")
def list_library_mevzuat(
    tur: Optional[str] = None, db: Session = Depends(get_db)
):
    query = db.query(Mevzuat)
    if tur:
        query = query.filter(Mevzuat.tur == tur)

    mevzuatlar = query.order_by(Mevzuat.son_guncelleme.desc()).all()

    return {
        "total": len(mevzuatlar),
        "data": [
            {
                "id": m.id,
                "mevzuat_no": m.mevzuat_no,
                "baslik": m.baslik,
                "tur": m.tur,
                "mevzuat_url": m.mevzuat_url,
                "son_guncelleme": (
                    m.son_guncelleme.strftime("%Y-%m-%d %H:%M")
                    if m.son_guncelleme
                    else "-"
                ),
                "revizyon_sayisi": len(m.revizyonlar),
            }
            for m in mevzuatlar
        ],
    }


# --- ARAMA UÇ NOKTASI (mevzuat/{id} ile çakışmasın diye /api/arama) ---


@app.get("/api/arama")
def search_mevzuat(
    q: str,
    tur: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Kütüphanedeki mevzuatlarda başlık ve içerik araması yapar."""
    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Arama terimi en az 2 karakter olmalıdır.",
        )

    query_str = q.strip().lower()

    query = db.query(Mevzuat).filter(
        (Mevzuat.baslik.ilike(f"%{query_str}%"))
        | (Mevzuat.icerik_html.ilike(f"%{query_str}%"))
    )

    if tur:
        query = query.filter(Mevzuat.tur == tur)

    mevzuatlar = query.limit(limit).all()

    results = []
    for m in mevzuatlar:
        baslik_eslesme = query_str in m.baslik.lower()

        snippet = ""
        if m.icerik_html:
            icerik_lower = m.icerik_html.lower()
            idx = icerik_lower.find(query_str)
            if idx != -1:
                start = max(0, idx - 100)
                end = min(len(m.icerik_html), idx + 200)
                snippet = m.icerik_html[start:end]
                snippet = re.sub(r"<[^>]+>", " ", snippet)
                snippet = re.sub(r"\s+", " ", snippet).strip()
                snippet = f"...{snippet}..."

        results.append(
            {
                "id": m.id,
                "mevzuat_no": m.mevzuat_no,
                "baslik": m.baslik,
                "tur": m.tur,
                "mevzuat_url": m.mevzuat_url,
                "son_guncelleme": (
                    m.son_guncelleme.strftime("%Y-%m-%d %H:%M")
                    if m.son_guncelleme
                    else "-"
                ),
                "baslik_eslesme": baslik_eslesme,
                "snippet": snippet,
            }
        )

    results.sort(key=lambda x: (not x["baslik_eslesme"], x["baslik"]))

    return {
        "query": q,
        "total": len(results),
        "results": results,
    }


# --- TEK MEVZUAT DETAY (arama endpoint'inden SONRA gelmeli) ---


@app.get("/api/mevzuat/{mevzuat_id}")
def get_mevzuat_detail(mevzuat_id: int, db: Session = Depends(get_db)):
    m = db.query(Mevzuat).filter(Mevzuat.id == mevzuat_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mevzuat bulunamadı.")

    return {
        "id": m.id,
        "mevzuat_no": m.mevzuat_no,
        "baslik": m.baslik,
        "tur": m.tur,
        "mevzuat_url": m.mevzuat_url,
        "icerik_html": m.icerik_html,
        "son_guncelleme": (
            m.son_guncelleme.strftime("%Y-%m-%d %H:%M")
            if m.son_guncelleme
            else "-"
        ),
        "revizyonlar": [
            {
                "id": r.id,
                "tarih": (
                    r.resmi_gazete_tarihi.strftime("%Y-%m-%d")
                    if r.resmi_gazete_tarihi
                    else "-"
                ),
                "sayi": r.resmi_gazete_sayi,
                "baslik": r.degisiklik_basligi,
                "url": r.degisiklik_url,
                "aciklama": r.aciklama,
            }
            for r in m.revizyonlar
        ],
    }


@app.put("/api/mevzuat/{mevzuat_id}")
def update_mevzuat(
    mevzuat_id: int, req: MevzuatGuncelleRequest, db: Session = Depends(get_db)
):
    m = db.query(Mevzuat).filter(Mevzuat.id == mevzuat_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mevzuat bulunamadı.")

    if req.baslik:
        m.baslik = req.baslik
    if req.mevzuat_no:
        m.mevzuat_no = req.mevzuat_no
    if req.tur:
        m.tur = req.tur
    if req.mevzuat_url:
        m.mevzuat_url = req.mevzuat_url

    db.commit()
    return {"status": "success", "message": "Mevzuat güncellendi."}


@app.delete("/api/mevzuat/{mevzuat_id}")
def delete_mevzuat(mevzuat_id: int, db: Session = Depends(get_db)):
    m = db.query(Mevzuat).filter(Mevzuat.id == mevzuat_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mevzuat bulunamadı.")

    db.delete(m)
    db.commit()
    return {"status": "success", "message": "Mevzuat silindi."}


# --- MANUEL VE OTOMATİK REVİZYON UÇ NOKTALARI ---


@app.post("/api/revizyon/tara")
def trigger_revision_check(background_tasks: BackgroundTasks):
    background_tasks.add_task(check_daily_revisions_against_library)
    return {
        "status": "success",
        "message": "Resmî Gazete taraması başlatıldı.",
    }


@app.get("/api/revizyon/{revizyon_id}/diff")
def get_revision_diff(revizyon_id: int, db: Session = Depends(get_db)):
    rev = (
        db.query(MevzuatRevizyon)
        .filter(MevzuatRevizyon.id == revizyon_id)
        .first()
    )
    if not rev:
        raise HTTPException(status_code=404, detail="Revizyon bulunamadı.")

    mevzuat = rev.mevzuat

    yeni_metin = (
        fetch_content_from_url(rev.degisiklik_url) if rev.degisiklik_url else ""
    )

    if not yeni_metin or "ayrıştırılamadı" in yeni_metin:
        yeni_metin = (
            f"<p>{rev.degisiklik_basligi}</p>"
            f"<p>{rev.aciklama or ''}</p>"
        )

    eski_metin = mevzuat.icerik_html or "<p>Metin bulunamadı.</p>"
    eski_metin = re.sub(
        r"<div style='background-color: #FEF3C7;.*?</div>",
        "",
        eski_metin,
        flags=re.DOTALL,
    )

    diff_html = generate_text_diff(old_html=eski_metin, new_html=yeni_metin)

    return {
        "revizyon_id": rev.id,
        "mevzuat_baslik": mevzuat.baslik,
        "degisiklik_basligi": rev.degisiklik_basligi,
        "diff_html": diff_html,
    }


# --- TAKİP KELİMELERİ VE ÖNERİ UÇ NOKTALARI ---


@app.get("/api/ayarlar/kelimeler")
def get_keywords(db: Session = Depends(get_db)):
    return db.query(TakipKelimesi).all()


@app.post("/api/ayarlar/kelime-ekle")
def add_keyword(req: KelimeRequest, db: Session = Depends(get_db)):
    word = req.kelime.strip()
    if not word:
        raise HTTPException(
            status_code=400, detail="Kelime boş bırakılamaz."
        )

    exists = (
        db.query(TakipKelimesi).filter(TakipKelimesi.kelime == word).first()
    )
    if not exists:
        new_k = TakipKelimesi(kelime=word)
        db.add(new_k)
        db.commit()
        db.refresh(new_k)
        return {
            "status": "success",
            "data": {"id": new_k.id, "kelime": new_k.kelime},
        }

    return {
        "status": "exists",
        "data": {"id": exists.id, "kelime": exists.kelime},
    }


@app.delete("/api/ayarlar/kelime-sil/{kelime_id}")
def delete_keyword(kelime_id: int, db: Session = Depends(get_db)):
    k = db.query(TakipKelimesi).filter(TakipKelimesi.id == kelime_id).first()
    if k:
        db.delete(k)
        db.commit()
    return {"status": "success"}


@app.get("/api/oneriler")
def get_suggestions(db: Session = Depends(get_db)):
    return (
        db.query(MevzuatOnerisi)
        .filter(MevzuatOnerisi.eklendi_mi == False)
        .all()
    )


@app.post("/api/oneriler/{oneri_id}/kutuphaneye-ekle")
def convert_suggestion_to_mevzuat(
    oneri_id: int, db: Session = Depends(get_db)
):
    sug = (
        db.query(MevzuatOnerisi).filter(MevzuatOnerisi.id == oneri_id).first()
    )
    if not sug:
        raise HTTPException(status_code=404, detail="Öneri bulunamadı.")

    tur = "Yönetmelik"
    if "kanun" in sug.baslik.lower():
        tur = "Kanun"
    elif "tebliğ" in sug.baslik.lower():
        tur = "Tebliğ"
    elif "karar" in sug.baslik.lower():
        tur = "Karar"

    new_m = Mevzuat(
        mevzuat_no="-",
        baslik=sug.baslik,
        tur=tur,
        mevzuat_url=sug.url,
        icerik_html=f"<p>{sug.baslik} - Resmî Gazete'den otomatik aktarıldı.</p>",
    )
    db.add(new_m)
    sug.eklendi_mi = True
    db.commit()
    return {"status": "success", "message": "Mevzuat kütüphaneye eklendi."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)