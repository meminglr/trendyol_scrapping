"""
Trendyol Scraping Sistemi — Ana Giriş Noktası
=============================================
Komut satırından kullanım ve örnek scriptler.

Kullanım:
    python main.py search "laptop çantası" --pages 3 --csv output/laptoplar.csv
    python main.py product https://www.trendyol.com/.../p-123456789
    python main.py category "https://www.trendyol.com/kadin-elbise" --excel
    python main.py track --add "URL" --target-price 299.90
    python main.py track --run --interval 60
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from scraper import TrendyolScraper
from config import ScraperConfig, SearchFilters
from exporter import save_csv, save_json, save_excel, TrendyolDB
from price_tracker import PriceTracker

# ------------------------------------------------------------------ #
#  Loglama kurulumu                                                    #
# ------------------------------------------------------------------ #

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("scraper.log", encoding="utf-8"),
        ],
    )

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  Yardımcı fonksiyonlar                                               #
# ------------------------------------------------------------------ #

def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _output_path(directory: str, prefix: str, ext: str) -> str:
    Path(directory).mkdir(parents=True, exist_ok=True)
    return f"{directory}/{prefix}_{timestamp()}.{ext}"


# ------------------------------------------------------------------ #
#  Komut: search (arama)                                               #
# ------------------------------------------------------------------ #

def cmd_search(args, scraper: TrendyolScraper):
    """Trendyol'da arama yapar ve sonuçları kaydeder."""
    # --page ve --pages aynı anda kullanılamaz
    if getattr(args, 'page', None) and getattr(args, 'pages', None) != 3:
        logger.error("Hata: --page ve --pages aynı anda kullanılamaz.")
        sys.exit(1)

    filters = SearchFilters(
        min_price=args.min_price,
        max_price=args.max_price,
        only_free_shipping=args.free_shipping,
        sort_by=args.sort,
    ).to_params()

    single_page = getattr(args, 'page', None) is not None
    page_num = args.page if single_page else args.pages

    if single_page:
        logger.info(f"Aranıyor: '{args.query}' → yalnızca {page_num}. sayfa")
    else:
        logger.info(f"Aranıyor: '{args.query}' → 1-{page_num}. sayfalar (birikimli)")

    result = scraper.search(
        query=args.query,
        max_pages=page_num,
        filters=filters,
        single_page=single_page,
    )

    logger.info(result.summary())
    prefix = f"search_{args.query.replace(' ','_')[:20]}"
    if single_page:
        prefix += f"_p{page_num}"
    _save_results(result.products, args, prefix=prefix)
    return result


# ------------------------------------------------------------------ #
#  Komut: category (kategori)                                          #
# ------------------------------------------------------------------ #

def cmd_category(args, scraper: TrendyolScraper):
    """Kategori sayfasından ürün çeker."""
    filters = SearchFilters(
        min_price=args.min_price,
        max_price=args.max_price,
        sort_by=args.sort,
    ).to_params()

    single_page = getattr(args, 'page', None) is not None
    page_num = args.page if single_page else args.pages

    if single_page:
        logger.info(f"Kategori çekiliyor: {args.url} → yalnızca {page_num}. sayfa")
    else:
        logger.info(f"Kategori çekiliyor: {args.url} → 1-{page_num}. sayfalar (birikimli)")

    result = scraper.search(
        category_url=args.url,
        max_pages=page_num,
        filters=filters,
        single_page=single_page,
    )

    logger.info(result.summary())
    prefix = "category_p" + str(page_num) if single_page else "category"
    _save_results(result.products, args, prefix=prefix)
    return result


# ------------------------------------------------------------------ #
#  Komut: product (tek ürün)                                           #
# ------------------------------------------------------------------ #

def cmd_product(args, scraper: TrendyolScraper):
    """Tek ürün detayını çeker."""
    logger.info(f"Ürün çekiliyor: {args.url}")

    product = scraper.get_product_from_url(args.url)
    if not product:
        logger.error("Ürün bulunamadı.")
        sys.exit(1)

    print("\n" + "─"*50)
    print(f"  {product.name}")
    print(f"  Marka    : {product.brand}")
    print(f"  Fiyat    : {product.price:.2f} TRY", end="")
    if product.discount_pct > 0:
        print(f" (-%{product.discount_pct:.0f})", end="")
    print()
    print(f"  Puan     : {product.rating:.1f} ({product.review_count} değerlendirme)")
    print(f"  Satıcı   : {product.seller}")
    print(f"  Stok     : {'✓ Var' if product.in_stock else '✗ Yok'}")
    print(f"  Kargo    : {'Ücretsiz' if product.free_shipping else 'Ücretli'}")
    print("─"*50 + "\n")

    # Yorumlar
    if args.reviews:
        reviews = scraper.get_reviews(product.id, max_pages=args.reviews)
        logger.info(f"{len(reviews)} yorum çekildi.")
    else:
        reviews = []

    # Kaydet
    outdir = args.output or "output"
    save_json({
        "product": product.to_dict(),
        "reviews": [r.to_dict() for r in reviews],
    }, f"{outdir}/product_{product.id}.json")

    if args.excel:
        save_excel([product], f"{outdir}/product_{product.id}.xlsx", reviews=reviews)

    return product, reviews


# ------------------------------------------------------------------ #
#  Komut: track (fiyat takibi)                                         #
# ------------------------------------------------------------------ #

def cmd_track(args, scraper: TrendyolScraper, db: TrendyolDB):
    tracker = PriceTracker(scraper, db)

    if args.add:
        # Yeni alert ekle
        if not args.target_price:
            print("Hata: --target-price gerekli.")
            sys.exit(1)
        p = tracker.add_alert_from_url(
            args.add,
            target_price=args.target_price,
            target_discount_pct=args.target_discount or 0.0,
        )
        if p:
            print(f"✓ Alert eklendi: {p.name} → {args.target_price:.2f} TRY")

    elif args.remove:
        tracker.remove_alert(args.remove)
        print(f"✓ Alert silindi: {args.remove}")

    elif args.list:
        if not tracker.alerts:
            print("Takip edilen ürün yok.")
        for a in tracker.alerts:
            print(f"  [{a.product_id}] {a.product_name} → hedef: {a.target_price:.2f} TRY")

    elif args.check:
        triggered = tracker.check_all()
        print(f"{len(triggered)} alert tetiklendi.")

    elif args.run:
        interval = args.interval or 60
        tracker.run(interval_minutes=interval)

    elif args.history:
        rows = db.get_price_history(args.history)
        if not rows:
            print("Fiyat geçmişi bulunamadı.")
        else:
            print(f"\nFiyat Geçmişi ({args.history}):")
            for r in rows:
                stock = "✓" if r["in_stock"] else "✗"
                print(f"  {r['recorded_at'][:16]}  |  {r['price']:.2f} TRY  |  -%{r['discount_pct']:.1f}  |  Stok: {stock}")


# ------------------------------------------------------------------ #
#  Kaydetme yardımcısı                                                 #
# ------------------------------------------------------------------ #

def _save_results(products, args, prefix: str = "results"):
    if not products:
        logger.warning("Kaydedilecek ürün yok.")
        return

    outdir = args.output or "output"

    if hasattr(args, "csv") and args.csv:
        path = args.csv if args.csv != True else _output_path(outdir, prefix, "csv")
        save_csv(products, path)

    if hasattr(args, "json") and args.json:
        path = args.json if args.json != True else _output_path(outdir, prefix, "json")
        save_json(products, path)

    if hasattr(args, "excel") and args.excel:
        path = args.excel if args.excel != True else _output_path(outdir, prefix, "xlsx")
        save_excel(products, path)

    # Varsayılan olarak JSON kaydet
    if not any([
        (hasattr(args, "csv") and args.csv),
        (hasattr(args, "json") and args.json),
        (hasattr(args, "excel") and args.excel),
    ]):
        save_json(products, _output_path(outdir, prefix, "json"))


# ------------------------------------------------------------------ #
#  Argüman ayrıştırıcı                                                 #
# ------------------------------------------------------------------ #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Trendyol Scraping Sistemi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verbose", action="store_true", help="Detaylı log")
    parser.add_argument("--proxy", help="Proxy URL (http://user:pass@host:port)")
    parser.add_argument("--delay", type=float, nargs=2, metavar=("MIN", "MAX"),
                        default=[1.5, 4.0], help="İstek gecikme aralığı (saniye)")
    parser.add_argument("--output", default="output", help="Çıktı dizini")

    sub = parser.add_subparsers(dest="command")

    # --- search ---
    s = sub.add_parser("search", help="Arama yaparak ürünleri çek")
    s.add_argument("query", help="Arama kelimesi")
    # Pagination modu seçimi (birlikte kullanılamaz)
    pag = s.add_mutually_exclusive_group()
    pag.add_argument("--pages", type=int, default=3,
                     metavar="N",
                     help="Birikimli mod: 1→N arası sayfaları birleştirerek çek (varsayılan: 3)")
    pag.add_argument("--page", type=int,
                     metavar="N",
                     help="Tek sayfa modu: yalnızca N. sayfayı çek")
    s.add_argument("--min-price", type=float)
    s.add_argument("--max-price", type=float)
    s.add_argument("--free-shipping", action="store_true")
    s.add_argument("--sort", default="BEST_SELLER",
                   choices=["BEST_SELLER", "PRICE_BY_ASC", "PRICE_BY_DESC", "MOST_RATED", "NEWEST"])
    s.add_argument("--csv", nargs="?", const=True, help="CSV olarak kaydet")
    s.add_argument("--json", nargs="?", const=True, help="JSON olarak kaydet")
    s.add_argument("--excel", nargs="?", const=True, help="Excel olarak kaydet")

    # --- category ---
    c = sub.add_parser("category", help="Kategori sayfasından ürünleri çek")
    c.add_argument("url", help="Trendyol kategori URL'si")
    cpag = c.add_mutually_exclusive_group()
    cpag.add_argument("--pages", type=int, default=5,
                      metavar="N",
                      help="Birikimli mod: 1→N arası sayfaları birleştirerek çek (varsayılan: 5)")
    cpag.add_argument("--page", type=int,
                      metavar="N",
                      help="Tek sayfa modu: yalnızca N. sayfayı çek")
    c.add_argument("--min-price", type=float)
    c.add_argument("--max-price", type=float)
    c.add_argument("--sort", default="BEST_SELLER",
                   choices=["BEST_SELLER", "PRICE_BY_ASC", "PRICE_BY_DESC", "MOST_RATED", "NEWEST"])
    c.add_argument("--csv", nargs="?", const=True)
    c.add_argument("--json", nargs="?", const=True)
    c.add_argument("--excel", nargs="?", const=True)

    # --- product ---
    p = sub.add_parser("product", help="Tek ürün detayı çek")
    p.add_argument("url", help="Trendyol ürün URL'si")
    p.add_argument("--reviews", type=int, metavar="PAGES", help="Yorum sayfası sayısı")
    p.add_argument("--excel", action="store_true")

    # --- track ---
    t = sub.add_parser("track", help="Fiyat takibi")
    t.add_argument("--add", metavar="URL", help="Takip listesine URL ekle")
    t.add_argument("--remove", metavar="PRODUCT_ID", help="Alert sil")
    t.add_argument("--list", action="store_true", help="Alertleri listele")
    t.add_argument("--check", action="store_true", help="Tek seferlik kontrol")
    t.add_argument("--run", action="store_true", help="Sürekli takip başlat")
    t.add_argument("--interval", type=int, default=60, help="Kontrol aralığı (dakika)")
    t.add_argument("--target-price", type=float, help="Hedef fiyat (TRY)")
    t.add_argument("--target-discount", type=float, help="Hedef indirim orani (yuzde)")
    t.add_argument("--history", metavar="PRODUCT_ID", help="Fiyat geçmişini göster")

    return parser


# ------------------------------------------------------------------ #
#  Main                                                                #
# ------------------------------------------------------------------ #

def main():
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(getattr(args, "verbose", False))

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Scraper & DB kurulumu
    config = ScraperConfig(
        min_delay=args.delay[0],
        max_delay=args.delay[1],
        proxy=getattr(args, "proxy", None),
    )
    scraper = TrendyolScraper(config=config)
    db = TrendyolDB()

    try:
        if args.command == "search":
            cmd_search(args, scraper)
        elif args.command == "category":
            cmd_category(args, scraper)
        elif args.command == "product":
            cmd_product(args, scraper)
        elif args.command == "track":
            cmd_track(args, scraper, db)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu.")


if __name__ == "__main__":
    main()
