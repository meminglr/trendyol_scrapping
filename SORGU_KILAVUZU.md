# Trendyol Scraper API — Örnek sorgu kılavuzu

**Taban adres:** `https://trendyolapi.emniva.com`

Tüm yanıtlar JSON formatındadır. İnteraktif deneme ve şema için tarayıcıda şu adresi açın:

- [https://trendyolapi.emniva.com/docs](https://trendyolapi.emniva.com/docs)

---

## Linke / tarayıcıdan nasıl sorgu atılır?

### Önce kısa mantık

- **Adres çubuğuna yapıştırdığınız link** tarayıcıda yalnızca **GET** isteği tetikler; **JSON gövdesi gönderemezsiniz.**
- **Arama** için **`GET /v1/search?q=...`** ile link kullanılabilir (aşağıda). **Kategori** (`/v1/category`) hâlâ **POST + JSON** ister (uzun URL, gövde).
- **GET ile linkten** kullanabileceğiniz uçlar: **`/health`**, **`/v1/search`**, **`/v1/product`**.

### 1) En kolayı: sadece adres çubuğu

Aşağıdakileri kopyalayıp tarayıcıya yapıştırmanız yeterli (sunucu JSON döner):

**Sağlık kontrolü**

```text
https://trendyolapi.emniva.com/health
```

### 2) GET ile ürün: linkte “query string” kullanımı

Format şöyledir: önce sabit adres, sonra **`?`**, sonra parametreler **`ad=değer`** şeklinde; birden fazlaysa araya **`&`** konur.

```text
https://trendyolapi.emniva.com/v1/product?url=...&review_pages=1
```

- **`url`**: Trendyol ürün sayfasının **tam adresi** olmalı; içinde `?`, `&`, `=` gibi karakterler olduğu için **ham haliyle yazılamaz** — **URL kodlaması** (encode) gerekir.
- **`review_pages`**: İsteğe bağlı; yorum çekmek istemezseniz hiç yazmayın.

**Kodlanmış örnek** (ürün URL’si basit tutulmuş bir örnek):

```text
https://trendyolapi.emniva.com/v1/product?url=https%3A%2F%2Fwww.trendyol.com%2Fornek%2Furun-p-123456789
```

Gerçek bir ürün linkiniz için:

1. [Swagger arayüzünü](https://trendyolapi.emniva.com/docs) açın → **`GET /v1/product`** → parametreleri doldurup **Execute** deyin; sistem doğru linki sizin için kurar.
2. Ya da herhangi bir “URL encode” aracında ürün adresinizi kodlayıp `url=` sonrasına yapıştırın.
3. Ya da terminalde (otomatik kodlar):

```bash
curl -sS -G 'https://trendyolapi.emniva.com/v1/product' \
  --data-urlencode 'url=https://www.trendyol.com/marka/urun-adi-p-123456789'
```

### 3) Arama / kategori: link değil, gövde gerekir

Bunlar **POST** olduğu için “tek satır link” yerine şunlardan birini kullanın:

| Yöntem | Ne yaparsınız? |
|--------|----------------|
| **Swagger** | `https://trendyolapi.emniva.com/docs` → ilgili **POST** satırı → **Try it out** → JSON girin → **Execute** |
| **curl** | Kılavuzdaki `curl -X POST ... -d '{...}'` örnekleri |
| **Kod** | JavaScript `fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({...}) })` |

### 4) API anahtarı açıksa tarayıcı linki

`TRENDYOL_API_KEY` tanımlıysa, adres çubuğundan tıklarken **header gönderemezsiniz**; bu yüzden:

- **`/docs`** içinde **Authorize** ile anahtarı girin, oradan deneyin; veya  
- **curl** / Postman / kendi uygulamanızda `X-API-Key` kullanın.

---

## Kimlik doğrulama (isteğe bağlı)

Sunucuda `TRENDYOL_API_KEY` tanımlıysa, aşağıdaki uç noktalara istek atarken **bir** yöntem kullanın:

| Yöntem | Header |
|--------|--------|
| API anahtarı | `X-API-Key: <anahtarınız>` |
| Bearer | `Authorization: Bearer <anahtarınız>` |

Anahtar yoksa bu header’lar gerekmez. `/health` her zaman anahtarsızdır.

---

## Sağlık kontrolü

```http
GET https://trendyolapi.emniva.com/health
```

**Örnek (curl):**

```bash
curl -sS https://trendyolapi.emniva.com/health
```

**Örnek yanıt:**

```json
{"status":"ok"}
```

---

## 1. Arama (`POST /v1/search` ve `GET /v1/search`)

Trendyol’da kelime ile arama yapar; ürün listesi döner. Aynı mantık **POST (JSON)** veya **GET (link, `q` parametresi)** ile kullanılabilir.

### İstek gövdesi (JSON)

| Alan | Tip | Zorunlu | Varsayılan | Açıklama |
|------|-----|---------|------------|----------|
| `query` | string | evet | — | Arama metni |
| `pages` | int | hayır | `3` | Birikimli mod: 1’den bu sayfaya kadar tüm sayfalar birleştirilir (1–50) |
| `page` | int | hayır | `null` | Tek sayfa modu: sadece bu sayfa çekilir (1–500). Verilirse `pages` yok sayılır |
| `min_price` | float | hayır | — | Minimum fiyat filtresi |
| `max_price` | float | hayır | — | Maksimum fiyat filtresi |
| `free_shipping` | bool | hayır | `false` | Yalnızca ücretsiz kargo |
| `sort` | string | hayır | `BEST_SELLER` | Sıralama (aşağıdaki değerlerden biri) |

**`sort` değerleri:** `BEST_SELLER`, `PRICE_BY_ASC`, `PRICE_BY_DESC`, `MOST_RATED`, `NEWEST`

### Link ile arama (`GET /v1/search`)

Tarayıcı adres çubuğuna yapıştırılabilir. Arama metni parametre adı **`q`**. Boşluk için **`%20`** veya **`+`** kullanın.

| Parametre | Zorunlu | Varsayılan | Açıklama |
|-----------|---------|------------|----------|
| `q` | evet | — | Arama kelimesi |
| `pages` | hayır | `3` | Kaç sayfa (birikimli), 1–50 |
| `page` | hayır | — | Tek sayfa modu; verilirse yalnızca o sayfa |
| `min_price` | hayır | — | Min fiyat |
| `max_price` | hayır | — | Max fiyat |
| `free_shipping` | hayır | `false` | `true` / `false` |
| `sort` | hayır | `BEST_SELLER` | Yukarıdaki sıralama değerleri |

**Örnek linkler**

```text
https://trendyolapi.emniva.com/v1/search?q=mouse&pages=1
https://trendyolapi.emniva.com/v1/search?q=laptop%20cantasi&pages=2&sort=PRICE_BY_ASC
https://trendyolapi.emniva.com/v1/search?q=kulaklik&page=2&min_price=100&max_price=2000
```

`TRENDYOL_API_KEY` aktifse tarayıcıdan bu linkler **401** verir (header eklenemez); o zaman `curl` veya `/docs` kullanın.

### Örnek: basit arama (ilk 2 sayfa birikimli)

```bash
curl -sS -X POST 'https://trendyolapi.emniva.com/v1/search' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: ANAHTARINIZ' \
  -d '{
    "query": "laptop çantası",
    "pages": 2
  }'
```

### Örnek: fiyat aralığı + en düşük fiyat sıralaması

```bash
curl -sS -X POST 'https://trendyolapi.emniva.com/v1/search' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "kulaklık",
    "pages": 1,
    "min_price": 200,
    "max_price": 1500,
    "sort": "PRICE_BY_ASC"
  }'
```

### Örnek: sadece 3. sayfa

```bash
curl -sS -X POST 'https://trendyolapi.emniva.com/v1/search' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "mouse",
    "page": 3
  }'
```

### Örnek yanıt (özet)

```json
{
  "query": "laptop çantası",
  "total_count": 12345,
  "pages_fetched": 2,
  "count": 48,
  "products": [
    {
      "id": "...",
      "name": "...",
      "brand": "...",
      "price": 299.99,
      "url": "https://www.trendyol.com/...",
      "rating": 4.5,
      "review_count": 120,
      "in_stock": true,
      "free_shipping": true
    }
  ]
}
```

`products` içindeki alanların tam listesi için `/docs` şemasına bakın.

---

## 2. Kategori (`POST /v1/category`)

Verilen Trendyol kategori URL’sinden ürün listesi çeker.

### İstek gövdesi (JSON)

| Alan | Tip | Zorunlu | Varsayılan | Açıklama |
|------|-----|---------|------------|----------|
| `url` | string | evet | — | Tam kategori adresi (`https://www.trendyol.com/...`) |
| `pages` | int | hayır | `5` | Birikimli sayfa sayısı (1–50) |
| `page` | int | hayır | — | Tek sayfa modu; verilirse `pages` yok sayılır |
| `min_price` | float | hayır | — | Minimum fiyat |
| `max_price` | float | hayır | — | Maksimum fiyat |
| `sort` | string | hayır | `BEST_SELLER` | Arama ile aynı `sort` değerleri |

### Örnek

```bash
curl -sS -X POST 'https://trendyolapi.emniva.com/v1/category' \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://www.trendyol.com/sr?qt=kulaklik&os=1",
    "pages": 2,
    "sort": "MOST_RATED"
  }'
```

### Örnek yanıt (özet)

```json
{
  "category_url": "https://www.trendyol.com/sr?qt=kulaklik&os=1",
  "total_count": 5000,
  "pages_fetched": 2,
  "count": 48,
  "products": [ ]
}
```

---

## 3. Ürün detayı

### 3a. `POST /v1/product` (önerilen; uzun URL’ler için uygun)

| Alan | Tip | Zorunlu | Açıklama |
|------|-----|---------|----------|
| `url` | string | evet | Ürün sayfası URL’si |
| `review_pages` | int | hayır | Yorum için çekilecek sayfa sayısı (0–50); `0` veya gönderilmezse yorum yok |

```bash
curl -sS -X POST 'https://trendyolapi.emniva.com/v1/product' \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://www.trendyol.com/marka/urun-adi-p-123456789",
    "review_pages": 2
  }'
```

### 3b. `GET /v1/product` (hızlı test)

Sorgu parametreleri: `url` (zorunlu), `review_pages` (isteğe bağlı).

```bash
curl -sS -G 'https://trendyolapi.emniva.com/v1/product' \
  --data-urlencode 'url=https://www.trendyol.com/marka/urun-adi-p-123456789' \
  --data-urlencode 'review_pages=1'
```

**Not:** URL’de `&`, `?` gibi karakterler olduğunda `GET` yerine `POST` kullanmak daha güvenlidir.

### Örnek yanıt (özet)

```json
{
  "product": {
    "id": "123456789",
    "name": "...",
    "brand": "...",
    "price": 199.0,
    "url": "https://www.trendyol.com/...",
    "images": ["https://..."],
    "in_stock": true,
    "seller": "...",
    "free_shipping": false
  },
  "reviews": []
}
```

Ürün bulunamazsa HTTP **404** ve gövdede `Ürün bulunamadı veya sayfa çekilemedi` mesajı döner. Bu, linkin yanlış olduğu anlamına gelmeyebilir; aşağıdaki **sorun giderme** bölümüne bakın.

---

## Sorun giderme: Link doğru, yine de “ürün bulunamadı”

Tarayıcıdaki adres veya `curl` ile gönderdiğiniz `url` parametresi doğru olsa bile sunucu Trendyol sayfasını veya API’yi **bot koruması** yüzünden çekemeyebilir (özellikle bulut / VPS IP’lerinde). Yerelde çalışıp sunucuda 404 görmenizin tipik nedeni budur.

**Yapmanız gerekenler:**

1. **`requirements.txt` içinde `curl-cffi` olduğundan emin olun** ve Coolify’da **yeniden deploy** edin. Scraper, bu paket varken tarayıcıya benzer TLS ile istek atar; Docker imajında yoksa sadece düz `requests` kullanılır ve Trendyol sık sık engeller.
2. Hâlâ olmazsa **`SCRAPER_PROXY`** ile residential/datacenter proxy deneyin (Coolify ortam değişkeni).
3. Aynı isteği **`POST /v1/product`** ile JSON gövdede deneyin; sonuç aynıysa sorun parametre biçiminde değil, sunucunun Trendyol’a erişimindedir.

---

## HTTP kodları

| Kod | Anlamı |
|-----|--------|
| 200 | Başarılı |
| 401 | Geçersiz veya eksik API anahtarı (`TRENDYOL_API_KEY` aktifken) |
| 404 | Ürün çözümlenemedi veya Trendyol sayfası çekilemedi (`/v1/product`) — bkz. sorun giderme |
| 422 | Gövde veya parametre doğrulama hatası (FastAPI/Pydantic) |
| 5xx | Sunucu veya upstream hatası |

---

## İpuçları

- Çok sayfa çekmek süreyi ve Trendyol tarafında kısıt riskini artırır; mümkünse düşük `pages` ile başlayın.
- Sunucu dağıtımında **`curl-cffi` kurulu** olmalı (`requirements.txt`); aksi halde Trendyol çoğu zaman HTML/API’yi vermez. Gerekirse `SCRAPER_PROXY` ekleyin.
- Üretimde `TRENDYOL_API_KEY` kullanmanız önerilir.

---

*Son güncelleme: API sürümü `1.0.0` (`api.py`).*
