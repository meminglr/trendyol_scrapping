# 🛍️ Trendyol Scraping Sistemi

Trendyol'un iç JSON API'lerini kullanarak ürün verisi, kategori listeleri, yorumlar ve fiyat takibi yapan tam teşekküllü Python sistemi.

> **Not:** Selenium'a gerek yoktur. Trendyol'un `public.trendyol.com` domain'indeki JSON endpoint'leri doğrudan `requests` ile sorgulanmaktadır.

---

## 📁 Dosya Yapısı

```
trendyol_scraper/
├── main.py           # CLI giriş noktası
├── scraper.py        # Ana scraper sınıfı (TrendyolScraper)
├── models.py         # Veri modelleri (Product, Review, SearchResult)
├── config.py         # Konfigürasyon ve filtreler
├── exporter.py       # CSV / JSON / Excel / SQLite çıktı
├── price_tracker.py  # Fiyat takip ve alarm sistemi
└── requirements.txt
```

---

## 🚀 Kurulum

```bash
pip install -r requirements.txt
```

---

## ⌨️ CLI Kullanımı

### 1. Arama

```bash
# Basit arama (3 sayfa, JSON çıktı)
python main.py search "laptop çantası"

# Fiyat filtreli, Excel çıktı
python main.py search "bluetooth kulaklık" --pages 5 --max-price 500 --excel

# Ücretsiz kargolu, ucuzdan pahalıya sıralı, CSV
python main.py search "spor ayakkabı" --free-shipping --sort PRICE_BY_ASC --csv

# Fiyat aralığı + belirli dosyaya kaydet
python main.py search "kol saati" --min-price 200 --max-price 1000 --csv output/saatler.csv
```

### 2. Kategori Çekme

```bash
# Kadın elbise kategorisi — 10 sayfa
python main.py category "https://www.trendyol.com/kadin-elbise-x-g1-c1" --pages 10 --excel

# Elektronik kategorisi, sadece ucuzlar
python main.py category "https://www.trendyol.com/elektronik" --sort PRICE_BY_ASC --pages 3 --csv
```

### 3. Tek Ürün Detayı

```bash
# Ürün detayı + 2 sayfa yorum + Excel çıktı
python main.py product "https://www.trendyol.com/apple/iphone-15-p-123456789" --reviews 2 --excel

# Sadece ürün (yorum yok)
python main.py product "https://www.trendyol.com/marka/urun-adi-p-987654321"
```

### 4. Fiyat Takibi

```bash
# URL'den takibe ekle
python main.py track --add "https://www.trendyol.com/..." --target-price 299.90

# İndirim oranı hedefle
python main.py track --add "https://www.trendyol.com/..." --target-price 999 --target-discount 30

# Mevcut alertleri listele
python main.py track --list

# Manuel tek seferlik kontrol
python main.py track --check

# Sürekli takip (her 2 saatte bir)
python main.py track --run --interval 120

# Fiyat geçmişini gör
python main.py track --history 123456789
```

---

## 🐍 Python API Kullanımı

### Arama

```python
from scraper import TrendyolScraper
from config import ScraperConfig, SearchFilters
from exporter import save_csv, save_excel

config = ScraperConfig(min_delay=2.0, max_delay=5.0)
scraper = TrendyolScraper(config=config)

# Arama
result = scraper.search("bluetooth kulaklık", max_pages=3)
print(result.summary())

# Filtreli arama
filters = SearchFilters(
    min_price=100,
    max_price=800,
    sort_by="PRICE_BY_ASC",
    only_free_shipping=True,
).to_params()
result = scraper.search("kulaklık", max_pages=5, filters=filters)

save_csv(result.products, "output/kulaklıklar.csv")
save_excel(result.products, "output/kulaklıklar.xlsx")
```

### Tekil Ürün + Yorumlar

```python
product = scraper.get_product_from_url(
    "https://www.trendyol.com/apple/airpods-pro-p-123456789"
)
print(f"{product.name}: {product.price} TRY")

reviews = scraper.get_reviews(product.id, max_pages=5)
for r in reviews[:3]:
    print(f"  ⭐ {r.rating}/5 — {r.comment[:80]}")
```

### Fiyat Takibi (Kod)

```python
from exporter import TrendyolDB
from price_tracker import PriceTracker

db = TrendyolDB()
tracker = PriceTracker(scraper, db)

# Alert ekle
tracker.add_alert_from_url(
    url="https://www.trendyol.com/...",
    target_price=350.0,
    target_discount_pct=20.0,
)

# E-posta destekli custom handler
def my_handler(info):
    PriceTracker.send_email_alert(
        info,
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        smtp_user="benim@gmail.com",
        smtp_pass="uygulama_sifresi",
        to_email="ben@ornek.com",
    )

tracker.on_alert = my_handler
tracker.run(interval_minutes=60)
```

### Veritabanı Sorguları

```python
from exporter import TrendyolDB

db = TrendyolDB()

# 300 TRY altındaki ürünler
ucuzlar = db.get_products_below_price(300)

# Fiyat geçmişi
gecmis = db.get_price_history("123456789")
for kayit in gecmis:
    print(kayit["recorded_at"], kayit["price"])
```

---

## ⚙️ Konfigürasyon

```python
from config import ScraperConfig

config = ScraperConfig(
    min_delay=2.0,       # İstekler arası minimum bekleme
    max_delay=5.0,       # Maksimum bekleme
    max_retries=3,       # Hata durumunda tekrar sayısı
    retry_wait=10.0,     # 429 sonrası bekleme
    timeout=20,          # HTTP timeout
    proxy="http://user:pass@host:port",  # Opsiyonel proxy
    db_path="trendyol.db",  # SQLite dosyası
)
```

---

## 📊 Çıktı Formatları

| Format | Açıklama |
|--------|----------|
| JSON   | Tüm alanlar, iç içe objeler dahil |
| CSV    | Excel uyumlu (UTF-8 BOM), düz tablo |
| Excel  | Biçimlendirilmiş, Trendyol turuncu header, Ürünler + Yorumlar sekmeleri |
| SQLite | Fiyat geçmişi, tekrarlanan çekim, sorgulama için |

---

## ⚠️ Önemli Notlar

- Trendyol'un Hizmet Şartları'na uygun kullanın.
- Aşırı istek göndermekten kaçının (`min_delay ≥ 1.5` saniye tutun).
- Ticari amaçlı büyük ölçekli kullanımda proxy rotasyonu önerilir.
- API endpoint'leri zaman zaman değişebilir; `scraper.py` içindeki `BASE_URL` sabitleri güncellenebilir.

---

## 🔧 Sorun Giderme

**403 Hatası:** Header'lar otomatik rotasyona girer. `min_delay` değerini artırın.

**429 (Rate Limit):** `retry_wait` ve `min_delay` değerlerini artırın. Proxy kullanmayı deneyin.

**Boş ürün listesi:** Trendyol API endpoint'i değişmiş olabilir. `SEARCH_API` URL'ini güncelleyin.

**Excel açılmıyor:** `pip install openpyxl` çalıştırın.
# trendyol_scrapping
