"""
Scraper Konfigürasyonu
======================
Tüm ayarları merkezi olarak yönetir.
"""

from dataclasses import dataclass, field
from typing import Optional


# Gerçekçi tarayıcı User-Agent listesi
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


@dataclass
class ScraperConfig:
    """Scraper ayarları."""

    # Rate limiting — Trendyol'u rahatsız etmemek için
    min_delay: float = 1.5   # İstekler arası minimum bekleme (saniye)
    max_delay: float = 4.0   # İstekler arası maksimum bekleme (saniye)

    # Hata yönetimi
    max_retries: int = 3
    retry_wait: float = 5.0  # 429/503 sonrası bekleme (saniye)
    timeout: int = 20         # HTTP timeout (saniye)

    # Proxy (isteğe bağlı)
    proxy: Optional[str] = None
    # Örnek: "http://kullanici:sifre@proxy.example.com:8080"

    # User-Agent rotasyonu
    user_agents: list = field(default_factory=lambda: DEFAULT_USER_AGENTS)

    # Çıktı
    output_dir: str = "output"

    # Veritabanı (SQLite — isteğe bağlı)
    db_path: Optional[str] = "trendyol.db"


@dataclass
class SearchFilters:
    """
    Trendyol arama filtresi yardımcısı.
    
    Kullanım:
        f = SearchFilters(min_price=100, max_price=500, brand_ids=[12345])
        result = scraper.search("laptop çantası", filters=f.to_params())
    """
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    brand_ids: list[int] = field(default_factory=list)
    category_id: Optional[int] = None
    sort_by: str = "BEST_SELLER"  # BEST_SELLER, PRICE_BY_ASC, PRICE_BY_DESC, MOST_RATED, NEWEST
    only_in_stock: bool = True
    only_free_shipping: bool = False
    min_rating: Optional[float] = None  # 3.5, 4.0, 4.5

    SORT_OPTIONS = {
        "en_cok_satan": "BEST_SELLER",
        "en_dusuk_fiyat": "PRICE_BY_ASC",
        "en_yuksek_fiyat": "PRICE_BY_DESC",
        "en_cok_degerlendirilen": "MOST_RATED",
        "en_yeni": "NEWEST",
    }

    def to_params(self) -> dict:
        params = {"sst": self.sort_by}
        if self.min_price is not None:
            params["pmin"] = self.min_price
        if self.max_price is not None:
            params["pmax"] = self.max_price
        if self.brand_ids:
            params["brandIds"] = ",".join(str(b) for b in self.brand_ids)
        if self.category_id:
            params["categoryId"] = self.category_id
        if self.only_free_shipping:
            params["freeShipping"] = True
        return params
