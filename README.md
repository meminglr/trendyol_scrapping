# 🛍️ Trendyol Scraping Sistemi

Trendyol'un JSON API'lerini kullanarak ürün verisi, kategori listeleri, yorumlar ve fiyat takibi yapan tam teşekküllü Python sistemi.

> **Selenium'a gerek yoktur.** `curl_cffi` kütüphanesi Chrome TLS parmak izini taklit ederek Cloudflare korumasını atlatır ve `apigw.trendyol.com` API'sine doğrudan erişir.

---

## 📁 Dosya Yapısı

```
trendyol_scrapping/
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
# Sanal ortam oluştur (önerilir)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Bağımlılıkları kur
pip install -r requirements.txt

# Cloudflare bypass için (zorunlu)
pip install curl_cffi
```

> **Not:** `curl_cffi` Cloudflare bot korumasını atlatmak için gereklidir. Bu olmadan `403` veya DNS hatası alırsınız.

---

## ⌨️ CLI Kullanımı

### 1. Arama — İki Farklı Pagination Modu

Sistem iki farklı sayfa çekme modunu destekler:

| Argüman | Mod | Davranış |
|---------|-----|----------|
| `--pages N` | **Birikimli** | 1. sayfadan N. sayfaya kadar tüm ürünleri birleştirir |
| `--page N` | **Tek sayfa** | Yalnızca N. sayfanın ürünlerini çeker |

> `--pages` ve `--page` aynı anda kullanılamaz.

```bash
# Birikimli mod — 1+2+3. sayfaları birleştir (72 ürün)
python main.py search "laptop çantası" --pages 3 --json

# Tek sayfa modu — yalnızca 3. sayfayı çek (24 ürün)
python main.py search "laptop çantası" --page 3 --json

# Fiyat filtreli, Excel çıktı (birikimli, 5 sayfa)
python main.py search "bluetooth kulaklık" --pages 5 --max-price 500 --excel

# Ücretsiz kargolu, ucuzdan pahalıya, CSV
python main.py search "spor ayakkabı" --free-shipping --sort PRICE_BY_ASC --pages 3 --csv

# Belirli dosyaya kaydet
python main.py search "kol saati" --min-price 200 --max-price 1000 --csv output/saatler.csv
```

**Sıralama seçenekleri (`--sort`):**
`BEST_SELLER` · `PRICE_BY_ASC` · `PRICE_BY_DESC` · `MOST_RATED` · `NEWEST`

---

### 2. Kategori Çekme

```bash
# Birikimli mod — ilk 10 sayfayı birleştir
python main.py category "https://www.trendyol.com/kadin-elbise-x-g1-c1" --pages 10 --excel

# Tek sayfa modu — yalnızca 2. kataloğu çek
python main.py category "https://www.trendyol.com/elektronik" --page 2 --csv

# Fiyat filtreli
python main.py category "https://www.trendyol.com/laptop" --sort PRICE_BY_ASC --pages 3 --json
```

---

### 3. Tek Ürün Detayı

```bash
# Ürün detayı + 2 sayfa yorum + Excel
python main.py product "https://www.trendyol.com/apple/iphone-15-p-123456789" --reviews 2 --excel

# Sadece ürün (yorum yok)
python main.py product "https://www.trendyol.com/marka/urun-adi-p-987654321"
```

---

### 4. Fiyat Takibi

```bash
# Takibe ekle (hedef fiyat)
python main.py track --add "https://www.trendyol.com/..." --target-price 299.90

# İndirim oranı hedefle
python main.py track --add "https://www.trendyol.com/..." --target-price 999 --target-discount 30

# Alertleri listele
python main.py track --list

# Tek seferlik kontrol
python main.py track --check

# Sürekli takip (her 2 saatte bir)
python main.py track --run --interval 120

# Fiyat geçmişini gör
python main.py track --history 123456789
```

---

### Genel Parametreler

```bash
python main.py --verbose search "..."    # Detaylı log
python main.py --proxy http://user:pass@host:port search "..."  # Proxy
python main.py --delay 2.0 5.0 search "..."  # Bekleme aralığı (sn)
python main.py --output klasor/ search "..."  # Çıktı dizini
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

# Birikimli mod — 1-3. sayfaları birleştir
result = scraper.search("bluetooth kulaklık", max_pages=3)
print(result.summary())

# Tek sayfa modu — yalnızca 5. sayfayı çek
result = scraper.search("bluetooth kulaklık", max_pages=5, single_page=True)

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

tracker.add_alert_from_url(
    url="https://www.trendyol.com/...",
    target_price=350.0,
    target_discount_pct=20.0,
)

tracker.run(interval_minutes=60)
```

---

## ⚙️ Konfigürasyon

```python
from config import ScraperConfig

config = ScraperConfig(
    min_delay=1.5,       # İstekler arası minimum bekleme (saniye)
    max_delay=4.0,       # Maksimum bekleme
    max_retries=3,       # Hata durumunda tekrar sayısı
    retry_wait=10.0,     # 429 sonrası bekleme süresi
    timeout=20,          # HTTP timeout
    proxy="http://user:pass@host:port",  # Opsiyonel proxy
    db_path="trendyol.db",               # SQLite dosyası
)
```

---

## 📊 Çıktı Formatları

| Format | Açıklama |
|--------|----------|
| JSON   | Tüm alanlar, iç içe objeler dahil |
| CSV    | Excel uyumlu (UTF-8 BOM), düz tablo |
| Excel  | Biçimlendirilmiş header, Ürünler + Yorumlar sekmeleri |
| SQLite | Fiyat geçmişi, tekrarlayan çekim ve filtreleme için |

---

## 🔧 Sorun Giderme

| Hata | Neden | Çözüm |
|------|-------|-------|
| `NameResolutionError` / DNS | `public.trendyol.com` artık yok | `scraper.py` güncel `apigw.trendyol.com` kullanıyor |
| `403 Forbidden` | Cloudflare bot koruması | `pip install curl_cffi` — otomatik bypass |
| `400 Bad Request` | Eksik parametre | `countryCode=TR` parametresi scraper'a eklendi |
| `429 Rate Limit` | Çok hızlı istek | `min_delay` ve `retry_wait` değerlerini artırın |
| Boş ürün listesi | API değişikliği | `scraper.py` içindeki `SEARCH_API` URL'ini kontrol edin |
| Excel açılmıyor | Eksik bağımlılık | `pip install openpyxl` |

---

## ⚠️ Önemli Notlar

- Trendyol'un **Hizmet Şartları**'na uygun kullanın.
- Aşırı istek göndermekten kaçının — `min_delay ≥ 1.5` saniye önerilir.
- Ticari amaçlı büyük ölçekli kullanımda proxy rotasyonu yapılması önerilir.
- API endpoint'leri zaman zaman değişebilir; `scraper.py` içindeki URL sabitleri güncellenebilir.
