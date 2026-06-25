# Project Atlas

Project Atlas; gelir, gider, kredi kartı borcu, nakit, hedef ve ETF planını
takip etmek için geliştirilmiş Türkçe bir Streamlit kişisel finans panelidir.

## Özellikler

- Gelir ve kategori bazlı gider kaydı
- Kredi kartı borç merkezi ve kapatma önceliği
- Aylık finansal karar motoru
- Finansal skor ve hedef ilerlemeleri
- VOO %60, QQQM %20, SCHD %20 ETF dağılımı
- Plotly raporları
- Yerel SQLite veritabanı
- Streamlit Secrets ile isteğe bağlı parola koruması

## Yerel çalıştırma

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud

Uygulama dosyası: `app.py`

Bulut uygulamasını korumak için Streamlit Secrets alanına şunu ekleyin:

```toml
APP_PASSWORD = "guclu-bir-parola"
```

`atlas.db` GitHub'a gönderilmez. İlk açılışta örnek veriler otomatik oluşturulur.

> Not: Streamlit Community Cloud dosya sistemi kalıcı depolama garantisi vermez.
> Uzun süreli gerçek kullanımda SQLite yerine yönetilen bir veritabanına geçilmelidir.

