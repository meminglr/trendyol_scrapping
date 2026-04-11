"""
Trendyol Scraping Sistemi - Ana Scraper Modülü
===============================================
Trendyol'un iç JSON API'lerini kullanarak ürün, kategori ve yorum verisi çeker.
Selenium'a gerek yoktur — requests + JSON endpoint yeterlidir.
"""

import time
import random
import json
import re
import logging
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs

import requests
try:
    from curl_cffi import requests as cf_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False
from bs4 import BeautifulSoup

from config import ScraperConfig
from models import Product, Review, SearchResult

logger = logging.getLogger(__name__)


class TrendyolScraper:
    """
    Trendyol ana scraper sınıfı.
    - Ürün detayı çekme (tek ürün)
    - Kategori/arama sayfası çekme (çoklu ürün)
    - Yorum (değerlendirme) çekme
    """

    BASE_URL = "https://www.trendyol.com"
    # Trendyol güncel API gateway (apigw.trendyol.com)
    SEARCH_API  = "https://apigw.trendyol.com/discovery-sfint-search-service/api/search/products"
    PRODUCT_API = "https://apigw.trendyol.com/discovery-web-productgw-service/api/product-detail"
    REVIEW_API  = "https://apigw.trendyol.com/discovery-web-productgw-service/api/review"

    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or ScraperConfig()
        self.session = self._build_session()
        self._request_count = 0

    # ------------------------------------------------------------------ #
    #  Session kurulumu                                                    #
    # ------------------------------------------------------------------ #

    def _build_session(self):
        if _HAS_CURL_CFFI:
            # Chrome TLS parmak izi taklit ederek Cloudflare'i bypass et
            session = cf_requests.Session(impersonate="chrome124")
        else:
            session = requests.Session()
        session.headers.update(self._get_headers())
        if self.config.proxy:
            session.proxies = {"http": self.config.proxy, "https": self.config.proxy}
        return session

    def _get_headers(self) -> dict:
        """Trendyol'un beklediği header setini döndürür."""
        return {
            "User-Agent": random.choice(self.config.user_agents),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.trendyol.com/",
            "Origin": "https://www.trendyol.com",
            "Connection": "keep-alive",
            "x-request-source": "single-search-result",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }

    # ------------------------------------------------------------------ #
    #  HTTP yardımcıları                                                   #
    # ------------------------------------------------------------------ #

    def _request(self, url: str, params: dict = None, retries: int = None) -> Optional[dict]:
        """Rate-limit ve retry destekli GET isteği."""
        retries = retries or self.config.max_retries
        self._request_count += 1

        # Her N istekte bir header rotasyonu
        if self._request_count % 20 == 0:
            self.session.headers.update({"User-Agent": random.choice(self.config.user_agents)})

        for attempt in range(1, retries + 1):
            try:
                self._sleep()
                resp = self.session.get(url, params=params, timeout=self.config.timeout)

                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception:
                        logger.warning(f"JSON parse hatası — yanıt HTML mi? ({url})")
                        return None
                elif resp.status_code == 429:
                    wait = self.config.retry_wait * attempt
                    logger.warning(f"Rate limit (429). {wait}s bekleniyor...")
                    time.sleep(wait)
                elif resp.status_code == 403:
                    logger.warning(f"403 Forbidden — header rotasyonu yapılıyor.")
                    self.session.headers.update(self._get_headers())
                    time.sleep(self.config.retry_wait)
                elif resp.status_code == 400:
                    logger.warning(f"400 Bad Request: {url} — parametreler kontrol edilmeli.")
                    logger.debug(f"Yanıt: {resp.text[:300]}")
                    break  # 400 retry etme
                elif resp.status_code == 556:
                    logger.warning(f"556 Bot bloğu: {url} — API erişimi engellendi, retry yapılmıyor.")
                    break  # 556 retry etme
                else:
                    logger.warning(f"HTTP {resp.status_code}: {url}")

            except Exception as e:
                logger.error(f"Hata (deneme {attempt}/{retries}): {e}")
                time.sleep(self.config.retry_wait * attempt)

        logger.error(f"Tüm denemeler başarısız: {url}")
        return None

    def _sleep(self):
        """İstekler arasında rastgele bekleme süresi."""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        time.sleep(delay)

    # ------------------------------------------------------------------ #
    #  URL ayrıştırıcılar                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def extract_product_id(url: str) -> Optional[str]:
        """Trendyol ürün URL'sinden content_id çıkarır."""
        # Örnek: /marka/urun-adi-p-123456789
        match = re.search(r"-p-(\d+)", url)
        if match:
            return match.group(1)
        # Alternatif: ?boutiqueId=... içindeki ürün
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        return qs.get("productContentId", [None])[0]

    @staticmethod
    def extract_category_path(url: str) -> Optional[str]:
        """Kategori URL'sinden path çıkarır."""
        parsed = urlparse(url)
        # /kadin-elbise-x-g1-c1 → kadin-elbise-x-g1-c1
        path = parsed.path.lstrip("/")
        return path if path else None

    # ------------------------------------------------------------------ #
    #  Ürün Detayı                                                         #
    # ------------------------------------------------------------------ #

    def get_product(self, product_id: str) -> Optional[Product]:
        """
        Tek bir ürünün tüm detaylarını çeker.
        
        Args:
            product_id: Trendyol content ID (URL'deki -p-XXXXX kısmı)
        
        Returns:
            Product nesnesi veya None
        """
        params = {"contentId": product_id}
        data = self._request(self.PRODUCT_API, params=params)
        
        if not data:
            return None

        try:
            return Product.from_api(data)
        except Exception as e:
            logger.error(f"Ürün parse hatası (ID={product_id}): {e}")
            return None

    def get_product_from_url(self, url: str) -> Optional[Product]:
        """
        URL'den ürün verisi çeker.
        Strateji: Önce HTML fallback (hızlı, direkt), başarısız olursa API dene.
        Not: Trendyol ürün detay API'si (apigw) sıklıkla 556 ile bloke
        ettiğinden HTML yöntemi birincil kaynak olarak kullanılır.
        """
        product_id = self.extract_product_id(url)
        if not product_id:
            logger.error(f"URL'den ürün ID çıkarılamadı: {url}")
            return None

        # 1) HTML yöntemi — hızlı ve güvenilir
        product = self._get_product_from_html(url)
        if product:
            return product

        # 2) API yöntemi — fallback
        logger.warning(f"HTML parse başarısız (ID={product_id}), API deneniyor...")
        product = self.get_product(product_id)
        if product is None:
            logger.error(f"API de başarısız oldu: {url}")
        return product

    def _get_product_from_html(self, url: str) -> Optional[Product]:
        """
        HTML sayfasını parse ederek ürün verisi çeker.
        window["__envoy_product-info__PROPS"] gömülü JSON'u kullanır.
        Trendyol API erişimi başarısız olduğunda fallback olarak çalışır.
        """
        html_headers = {
            "User-Agent": random.choice(self.config.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        try:
            self._sleep()
            resp = self.session.get(url, headers=html_headers, timeout=self.config.timeout)
            if resp.status_code != 200:
                logger.warning(
                    f"HTML fallback: Sayfa yüklenemedi ({resp.status_code}): {url}"
                )
                return None

            text = resp.text
            prefix = 'window["__envoy_product-info__PROPS"]='
            start_pos = text.find(prefix)

            if start_pos == -1:
                logger.warning("HTML fallback: Ürün verisi HTML içinde bulunamadı.")
                return None

            start_json = start_pos + len(prefix)
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(text[start_json:])

            return Product.from_html(data)

        except Exception as e:
            logger.error(f"HTML fallback hatası: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Kategori / Arama Sayfaları                                          #
    # ------------------------------------------------------------------ #

    def search(
        self,
        query: str = None,
        category_url: str = None,
        max_pages: int = 5,
        filters: dict = None,
        single_page: bool = False,
    ) -> SearchResult:
        """
        Arama veya kategori sayfasından ürün listesi çeker.

        Args:
            query: Arama kelimesi (örn: "laptop çantası")
            category_url: Trendyol kategori URL'si
            max_pages: Kaç sayfaya kadar çekileceği (birikimli mod) VEYA
                       hangi sayfanın çekileceği (tek sayfa modu)
            filters: Ek filtre parametreleri (brandId, minPrice, maxPrice, ...)
            single_page: True → sadece max_pages numaralı sayfayı çek
                         False → 1'den max_pages'e kadar tüm sayfaları biriktir

        Returns:
            SearchResult nesnesi
        """
        all_products = []
        total_count = 0

        if single_page:
            # ── TEK SAYFA MODU ──────────────────────────────────────────
            # Yalnızca istenen sayfa numarasını çek
            page = max_pages
            params = self._build_search_params(query, category_url, page, filters)
            logger.info(f"Sayfa {page} çekiliyor (tek sayfa modu)...")

            data = self._request(self.SEARCH_API, params=params)
            if data:
                if isinstance(data, list):
                    products_raw = data
                    total_count = len(data)
                else:
                    result = data.get("result", data)
                    products_raw = result.get("products", [])
                    total_count = data.get("total", result.get("totalCount", data.get("totalCount", 0)))

                for p in products_raw:
                    try:
                        all_products.append(Product.from_search(p))
                    except Exception as e:
                        logger.debug(f"Ürün parse hatası: {e}")

                logger.info(f"Sayfa {page}: {len(products_raw)} ürün çekildi")
            pages_fetched = page

        else:
            # ── BİRİKİMLİ MOD ───────────────────────────────────────────
            # 1'den max_pages'e kadar tüm sayfaları birleştir
            pages_fetched = 1
            for page in range(1, max_pages + 1):
                params = self._build_search_params(query, category_url, page, filters)
                logger.info(f"Sayfa {page}/{max_pages} çekiliyor...")

                data = self._request(self.SEARCH_API, params=params)
                if not data:
                    break

                if isinstance(data, list):
                    products_raw = data
                    total_count = len(data)
                else:
                    result = data.get("result", data)
                    products_raw = result.get("products", [])
                    total_count = data.get("total", result.get("totalCount", data.get("totalCount", total_count)))

                if not products_raw:
                    logger.info(f"Sayfa {page}'de ürün yok, durduruluyor.")
                    break

                for p in products_raw:
                    try:
                        all_products.append(Product.from_search(p))
                    except Exception as e:
                        logger.debug(f"Ürün parse hatası: {e}")

                logger.info(f"Sayfa {page}: {len(products_raw)} ürün çekildi (toplam: {len(all_products)})")
                pages_fetched = page

                # Son sayfaya ulaşıldıysa dur
                if len(products_raw) < 24:
                    break

        return SearchResult(
            products=all_products,
            total_count=total_count,
            pages_fetched=pages_fetched,
            query=query,
            category_url=category_url,
        )

    def _build_search_params(
        self, query: str, category_url: str, page: int, filters: dict = None
    ) -> dict:
        """Trendyol yeni arama API parametrelerini oluşturur."""
        params = {
            "pi": page,
            "channelId": 1,
            "storefrontId": 1,
            "culture": "tr-TR",
            "countryCode": "TR",
            "userGenderId": 1,
            "pId": 0,
            "searchStrategyType": "DEFAULT",
            "productStampType": "TypeA",
            "scoringAlgorithmId": 2,
            "isLegalRequirement": False,
        }

        if query:
            params["q"] = query
            params["qt"] = query
            params["st"] = query
            params["os"] = 1

        if category_url:
            path = self.extract_category_path(category_url)
            if path:
                params["pathModel"] = path
            # URL'deki query string parametrelerini aktar
            parsed = urlparse(category_url)
            qs = parse_qs(parsed.query)
            for k, v in qs.items():
                if k not in params:
                    params[k] = v[0] if len(v) == 1 else v

        if filters:
            params.update(filters)

        return params

    # ------------------------------------------------------------------ #
    #  Yorumlar                                                            #
    # ------------------------------------------------------------------ #

    def get_reviews(
        self, product_id: str, max_pages: int = 3, star_filter: int = None
    ) -> list[Review]:
        """
        Ürün yorumlarını çeker.

        Args:
            product_id: Trendyol content ID
            max_pages: Maksimum sayfa
            star_filter: Sadece bu yıldızlı yorumlar (1-5), None=hepsi

        Returns:
            Review listesi
        """
        all_reviews = []

        for page in range(0, max_pages):
            params = {
                "contentId": product_id,
                "pageSize": 20,
                "pageNumber": page,
                "channelId": 1,
            }
            if star_filter:
                params["star"] = star_filter

            data = self._request(self.REVIEW_API, params=params)
            if not data:
                break

            reviews_raw = data.get("result", {}).get("productReviews", {}).get("content", [])
            if not reviews_raw:
                break

            for r in reviews_raw:
                try:
                    all_reviews.append(Review.from_api(r))
                except Exception as e:
                    logger.debug(f"Yorum parse hatası: {e}")

            logger.info(f"Yorum sayfası {page+1}: {len(reviews_raw)} yorum")

        return all_reviews
