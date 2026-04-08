"""
Trendyol Veri Modelleri
========================
API yanıtlarını temiz Python nesnelerine dönüştürür.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


# ------------------------------------------------------------------ #
#  Product                                                             #
# ------------------------------------------------------------------ #

@dataclass
class Product:
    id: str
    name: str
    brand: str
    brand_id: Optional[int]
    category: str
    category_id: Optional[int]
    price: float
    original_price: float
    discount_pct: float
    currency: str
    rating: float
    review_count: int
    in_stock: bool
    url: str
    images: list[str]
    description: str
    attributes: dict
    seller: str
    seller_id: Optional[str]
    badges: list[str]
    free_shipping: bool
    has_gift: bool
    cargo_days: Optional[int]

    # ---------------------------------------------------------------- #

    @classmethod
    def from_api(cls, data: dict) -> "Product":
        """
        Trendyol ürün detay API yanıtından Product oluşturur.
        Endpoint: /discovery-web-productgw-service/api/product-detail
        """
        result = data.get("result", data)

        # Fiyat hesaplama
        price_info = result.get("price", {})
        price = price_info.get("sellingPrice", 0.0)
        orig  = price_info.get("originalPrice", price)
        disc  = round((1 - price / orig) * 100, 1) if orig and orig > 0 else 0.0

        # Görseller
        images = []
        for img in result.get("images", []):
            url = img if isinstance(img, str) else img.get("url", "")
            if url:
                if not url.startswith("http"):
                    url = f"https://cdn.dsmcdn.com{url}"
                images.append(url)

        # Özellikler
        attrs = {}
        for attr in result.get("attributes", []):
            key = attr.get("key", {}).get("name", "")
            val = attr.get("value", {}).get("name", "")
            if key:
                attrs[key] = val

        # Mağaza bilgisi
        merchant = result.get("merchant", {})
        seller   = merchant.get("name", "")
        seller_id = str(merchant.get("id", "")) if merchant.get("id") else None

        # Kargo
        cargo = result.get("shippingDetails", {})
        cargo_days = cargo.get("deliveryDuration")

        # Badge'ler
        badges = [b.get("text", "") for b in result.get("badges", []) if b.get("text")]

        # URL
        product_url = result.get("url", "")
        if product_url and not product_url.startswith("http"):
            product_url = f"https://www.trendyol.com{product_url}"

        return cls(
            id=str(result.get("id", result.get("contentId", ""))),
            name=result.get("name", ""),
            brand=result.get("brand", {}).get("name", "") if isinstance(result.get("brand"), dict) else str(result.get("brand", "")),
            brand_id=result.get("brand", {}).get("id") if isinstance(result.get("brand"), dict) else None,
            category=result.get("category", {}).get("name", "") if isinstance(result.get("category"), dict) else "",
            category_id=result.get("category", {}).get("id") if isinstance(result.get("category"), dict) else None,
            price=float(price),
            original_price=float(orig),
            discount_pct=disc,
            currency=price_info.get("currency", "TRY"),
            rating=float(result.get("ratingScore", {}).get("averageRating", 0.0) if isinstance(result.get("ratingScore"), dict) else 0.0),
            review_count=int(result.get("ratingScore", {}).get("totalCount", 0) if isinstance(result.get("ratingScore"), dict) else 0),
            in_stock=result.get("stockState", "").upper() != "OUT_OF_STOCK",
            url=product_url,
            images=images,
            description=result.get("description", ""),
            attributes=attrs,
            seller=seller,
            seller_id=seller_id,
            badges=badges,
            free_shipping=result.get("freeShipping", False),
            has_gift=result.get("hasGift", False),
            cargo_days=cargo_days,
        )

    @classmethod
    def from_search(cls, data: dict) -> "Product":
        """
        Trendyol arama API yeni yanıt yapısı (apigw.trendyol.com).
        price.current, ratingScore.averageRating gibi alanlar kullanılır.
        """
        price_obj = data.get("price", {})
        if isinstance(price_obj, dict):
            price = float(price_obj.get("current", price_obj.get("discountedPrice", price_obj.get("sellingPrice", 0.0))))
            orig  = float(price_obj.get("originalPrice", price_obj.get("old", price)) or price)
        else:
            price = float(price_obj or 0.0)
            orig  = price
        disc = round((1 - price / orig) * 100, 1) if orig > 0 and orig > price else 0.0

        # CDN görsel URL'si
        images = []
        for img in data.get("images", []):
            raw = img if isinstance(img, str) else img.get("url", "")
            if raw:
                if not raw.startswith("http"):
                    raw = f"https://cdn.dsmcdn.com{raw}"
                images.append(raw)
        # Tek görsel varsa ekle
        if not images and data.get("image"):
            img_url = data["image"]
            if not img_url.startswith("http"):
                img_url = f"https://cdn.dsmcdn.com{img_url}"
            images.append(img_url)

        # URL
        product_url = data.get("url", "")
        if product_url and not product_url.startswith("http"):
            product_url = f"https://www.trendyol.com{product_url}"

        # Rating
        rating_obj = data.get("ratingScore", {})
        if isinstance(rating_obj, dict):
            rating = float(rating_obj.get("averageRating", 0.0) or 0.0)
            review_count = int(rating_obj.get("totalCount", 0) or 0)
        else:
            rating = float(rating_obj or 0.0)
            review_count = int(data.get("reviewCount", 0) or 0)

        # Stok — yeni API'de stock={} boş sözlük ise var, None ise yok
        stock_obj = data.get("stock", None)
        in_stock = not data.get("soldOut", False)
        if stock_obj is not None and isinstance(stock_obj, dict):
            in_stock = stock_obj.get("available", True)

        return cls(
            id=str(data.get("contentId", data.get("id", ""))),
            name=data.get("name", ""),
            brand=data.get("brand", {}).get("name", "") if isinstance(data.get("brand"), dict) else str(data.get("brand", "")),
            brand_id=data.get("brandId", data.get("brand", {}).get("id") if isinstance(data.get("brand"), dict) else None),
            category=data.get("category", {}).get("name", "") if isinstance(data.get("category"), dict) else "",
            category_id=data.get("category", {}).get("id") if isinstance(data.get("category"), dict) else data.get("categoryId"),
            price=price,
            original_price=orig,
            discount_pct=disc,
            currency=price_obj.get("currency", "TRY") if isinstance(price_obj, dict) else "TRY",
            rating=rating,
            review_count=review_count,
            in_stock=in_stock,
            url=product_url,
            images=images,
            description="",
            attributes={},
            seller=data.get("merchantName", ""),
            seller_id=str(data.get("merchantId", "")) if data.get("merchantId") else None,
            badges=[b.get("text", "") for b in (data.get("badges") or []) if isinstance(b, dict)],
            free_shipping=data.get("freeCargo", data.get("freeShipping", False)),
            has_gift=data.get("hasGift", False),
            cargo_days=None,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __repr__(self) -> str:
        return f"Product(id={self.id}, name={self.name[:40]!r}, price={self.price} TRY)"


# ------------------------------------------------------------------ #
#  Review                                                              #
# ------------------------------------------------------------------ #

@dataclass
class Review:
    id: str
    product_id: str
    author: str
    rating: int
    comment: str
    title: str
    date: str
    likes: int
    dislikes: int
    is_verified: bool
    images: list[str]
    variant: str  # Hangi varyant (beden, renk vb.)
    seller_response: str

    @classmethod
    def from_api(cls, data: dict) -> "Review":
        images = [img.get("url", "") for img in data.get("images", []) if img.get("url")]
        return cls(
            id=str(data.get("id", "")),
            product_id=str(data.get("contentId", "")),
            author=data.get("userFullName", "Anonim"),
            rating=int(data.get("rate", 0)),
            comment=data.get("comment", ""),
            title=data.get("commentTitle", ""),
            date=data.get("lastModifiedDate", ""),
            likes=int(data.get("upVote", 0)),
            dislikes=int(data.get("downVote", 0)),
            is_verified=data.get("isVerifiedBuyer", False),
            images=images,
            variant=data.get("variant", ""),
            seller_response=data.get("sellerComment", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ #
#  SearchResult                                                        #
# ------------------------------------------------------------------ #

@dataclass
class SearchResult:
    products: list[Product]
    total_count: int
    pages_fetched: int
    query: Optional[str] = None
    category_url: Optional[str] = None

    def __len__(self) -> int:
        return len(self.products)

    def to_dicts(self) -> list[dict]:
        return [p.to_dict() for p in self.products]

    def summary(self) -> str:
        return (
            f"Arama: {self.query or self.category_url}\n"
            f"Toplam ürün: {self.total_count} | Çekilen: {len(self.products)} | Sayfa: {self.pages_fetched}"
        )
