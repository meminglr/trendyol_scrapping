"""
Trendyol scraper HTTP API — sunucuda çalıştırmak için.

    uvicorn api:app --host 0.0.0.0 --port 8000

İsteğe bağlı ortam değişkenleri:
    TRENDYOL_API_KEY   — Ayarlanırsa isteklerde header: X-API-Key veya Authorization: Bearer <key>
    SCRAPER_PROXY      — Örn. http://user:pass@host:8080
    SCRAPER_MIN_DELAY  — Varsayılan 1.5
    SCRAPER_MAX_DELAY  — Varsayılan 4.0
"""

from __future__ import annotations

import os
from typing import Annotated, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from config import ScraperConfig, SearchFilters
from scraper import TrendyolScraper

SORT_CHOICES = Literal[
    "BEST_SELLER",
    "PRICE_BY_ASC",
    "PRICE_BY_DESC",
    "MOST_RATED",
    "NEWEST",
]

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer = HTTPBearer(auto_error=False)


def _expected_api_key() -> Optional[str]:
    return os.environ.get("TRENDYOL_API_KEY") or None


async def require_api_key(
    x_api_key: Annotated[Optional[str], Security(api_key_header)] = None,
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Security(bearer)] = None,
) -> None:
    expected = _expected_api_key()
    if not expected:
        return
    token = x_api_key
    if creds and creds.scheme.lower() == "bearer":
        token = creds.credentials
    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik API anahtarı")


def build_scraper() -> TrendyolScraper:
    proxy = os.environ.get("SCRAPER_PROXY") or None
    try:
        min_d = float(os.environ.get("SCRAPER_MIN_DELAY", "1.5"))
        max_d = float(os.environ.get("SCRAPER_MAX_DELAY", "4.0"))
    except ValueError:
        min_d, max_d = 1.5, 4.0
    cfg = ScraperConfig(min_delay=min_d, max_delay=max_d, proxy=proxy)
    return TrendyolScraper(config=cfg)


app = FastAPI(
    title="Trendyol Scraper API",
    description="Arama, kategori ve ürün detayı için HTTP arayüzü.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Arama metni")
    pages: int = Field(3, ge=1, le=50, description="Birikimli mod: 1..N sayfa (page verilmişse yok sayılır)")
    page: Optional[int] = Field(
        None,
        ge=1,
        le=500,
        description="Tek sayfa modu: yalnızca bu sayfa",
    )
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    free_shipping: bool = False
    sort: SORT_CHOICES = "BEST_SELLER"


class CategoryRequest(BaseModel):
    url: str = Field(..., min_length=10, description="Trendyol kategori URL'si")
    pages: int = Field(5, ge=1, le=50, description="Birikimli mod (page verilmişse yok sayılır)")
    page: Optional[int] = Field(None, ge=1, le=500, description="Tek sayfa modu")
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    sort: SORT_CHOICES = "BEST_SELLER"


class ProductRequest(BaseModel):
    url: str = Field(..., min_length=10, description="Trendyol ürün URL'si")
    review_pages: Optional[int] = Field(
        None, ge=0, le=50, description="Çekilecek yorum sayfa sayısı (0 veya None: yok)"
    )


def _filters_from_search_body(body: SearchRequest) -> dict:
    return SearchFilters(
        min_price=body.min_price,
        max_price=body.max_price,
        only_free_shipping=body.free_shipping,
        sort_by=body.sort,
    ).to_params()


def _search_response(body: SearchRequest) -> dict:
    single = body.page is not None
    page_num = body.page if single else body.pages
    filters = _filters_from_search_body(body)
    scraper = build_scraper()
    result = scraper.search(
        query=body.query,
        max_pages=page_num,
        filters=filters,
        single_page=single,
    )
    return {
        "query": result.query,
        "total_count": result.total_count,
        "pages_fetched": result.pages_fetched,
        "count": len(result.products),
        "products": result.to_dicts(),
    }


def _filters_from_category_body(body: CategoryRequest) -> dict:
    return SearchFilters(
        min_price=body.min_price,
        max_price=body.max_price,
        sort_by=body.sort,
    ).to_params()


def _category_response(body: CategoryRequest) -> dict:
    single = body.page is not None
    page_num = body.page if single else body.pages
    filters = _filters_from_category_body(body)
    scraper = build_scraper()
    result = scraper.search(
        category_url=body.url,
        max_pages=page_num,
        filters=filters,
        single_page=single,
    )
    return {
        "category_url": result.category_url,
        "total_count": result.total_count,
        "pages_fetched": result.pages_fetched,
        "count": len(result.products),
        "products": result.to_dicts(),
    }


@app.post("/v1/search", dependencies=[Depends(require_api_key)])
def v1_search_post(body: SearchRequest):
    return _search_response(body)


@app.get("/v1/search", dependencies=[Depends(require_api_key)])
def v1_search_get(
    q: str = Query(
        ...,
        min_length=1,
        description="Arama metni (boşluklar için %20 veya + kullanın)",
    ),
    pages: int = Query(3, ge=1, le=50),
    page: Optional[int] = Query(None, ge=1, le=500),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    free_shipping: bool = Query(False),
    sort: SORT_CHOICES = Query("BEST_SELLER"),
):
    """Tarayıcı veya paylaşılabilir link ile arama (GET)."""
    body = SearchRequest(
        query=q,
        pages=pages,
        page=page,
        min_price=min_price,
        max_price=max_price,
        free_shipping=free_shipping,
        sort=sort,
    )
    return _search_response(body)


@app.post("/v1/category", dependencies=[Depends(require_api_key)])
def v1_category_post(body: CategoryRequest):
    return _category_response(body)


@app.get("/v1/category", dependencies=[Depends(require_api_key)])
def v1_category_get(
    url: str = Query(
        ...,
        min_length=10,
        description="Trendyol kategori veya liste URL'si (tam adres; ? ve & için encode gerekir)",
    ),
    pages: int = Query(5, ge=1, le=50),
    page: Optional[int] = Query(None, ge=1, le=500),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sort: SORT_CHOICES = Query("BEST_SELLER"),
):
    """Tarayıcı veya paylaşılabilir link ile kategori çekme (GET)."""
    body = CategoryRequest(
        url=url,
        pages=pages,
        page=page,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )
    return _category_response(body)


@app.post("/v1/product", dependencies=[Depends(require_api_key)])
def v1_product(body: ProductRequest):
    scraper = build_scraper()
    product = scraper.get_product_from_url(body.url)
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı veya sayfa çekilemedi")
    reviews = []
    if body.review_pages and body.review_pages > 0:
        reviews = scraper.get_reviews(product.id, max_pages=body.review_pages)
    return {
        "product": product.to_dict(),
        "reviews": [r.to_dict() for r in reviews],
    }


@app.get("/v1/product", dependencies=[Depends(require_api_key)])
def v1_product_get(
    url: str = Query(..., min_length=10, description="Trendyol ürün URL'si"),
    review_pages: Optional[int] = Query(None, ge=0, le=50),
):
    return v1_product(ProductRequest(url=url, review_pages=review_pages))
