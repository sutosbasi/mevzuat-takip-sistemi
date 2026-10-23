import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = "sqlite:///./mevzuat_kutuphanesi.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Mevzuat(Base):
    """mevzuat.gov.tr'den çekilen ana mevzuat metinleri"""

    __tablename__ = "mevzuatlar"

    id = Column(Integer, primary_key=True, index=True)
    mevzuat_no = Column(String, index=True)
    baslik = Column(String, nullable=False)
    tur = Column(String, index=True)  # Kanun, CBK, Yönetmelik, Tebliğ vb.
    icerik_html = Column(Text)
    mevzuat_url = Column(String, unique=True)
    son_guncelleme = Column(DateTime, default=datetime.datetime.utcnow)

    revizyonlar = relationship(
        "MevzuatRevizyon", back_populates="mevzuat", cascade="all, delete-orphan"
    )


class MevzuatRevizyon(Base):
    """resmigazete.gov.tr'den tespit edilen günlük değişiklikler"""

    __tablename__ = "mevzuat_revizyonlari"

    id = Column(Integer, primary_key=True, index=True)
    mevzuat_id = Column(Integer, ForeignKey("mevzuatlar.id"))
    resmi_gazete_tarihi = Column(DateTime, default=datetime.datetime.utcnow)
    resmi_gazete_sayi = Column(String)
    degisiklik_basligi = Column(String)
    degisiklik_url = Column(String)
    aciklama = Column(Text)

    mevzuat = relationship("Mevzuat", back_populates="revizyonlar")


class TakipKelimesi(Base):
    """Kullanıcının otomatik takip etmek istediği anahtar kelimeler (Örn: Vergi, İhale, Mal Alımı)"""

    __tablename__ = "takip_kelimeleri"

    id = Column(Integer, primary_key=True, index=True)
    kelime = Column(String, unique=True, index=True)


class MevzuatOnerisi(Base):
    """Resmî Gazete'de bulunup henüz kütüphanede olmayan önerilen yeni mevzuatlar"""

    __tablename__ = "mevzuat_onerileri"

    id = Column(Integer, primary_key=True, index=True)
    baslik = Column(String)
    url = Column(String, unique=True)
    eslesen_kelime = Column(String)
    tarih = Column(DateTime, default=datetime.datetime.utcnow)
    eklendi_mi = Column(Boolean, default=False)


Base.metadata.create_all(bind=engine)