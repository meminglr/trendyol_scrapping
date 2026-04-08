"""
Fiyat Takip Modülü
==================
Belirlenen ürünlerin fiyatlarını periyodik olarak izler ve
hedef fiyata ulaşıldığında bildirim gönderir.
"""

import time
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path

from scraper import TrendyolScraper
from exporter import TrendyolDB
from config import ScraperConfig

logger = logging.getLogger(__name__)


@dataclass
class PriceAlert:
    """Fiyat alarmı tanımı."""
    product_id: str
    product_name: str
    product_url: str
    target_price: float           # Hedef fiyat (altına düşünce alarm)
    target_discount_pct: float = 0.0  # Alternatif: % indirim hedefi
    check_in_stock: bool = True   # Sadece stokta olunca alarm


class PriceTracker:
    """
    Ürün fiyatlarını periyodik takip eden sınıf.
    
    Kullanım:
        tracker = PriceTracker(scraper, db)
        tracker.add_alert("123456789", "iPhone 15 Kılıf", 
                          "https://...", target_price=150.0)
        tracker.run(interval_minutes=60)
    """

    def __init__(
        self,
        scraper: TrendyolScraper,
        db: TrendyolDB,
        on_alert: Optional[Callable] = None,
    ):
        self.scraper = scraper
        self.db = db
        self.alerts: list[PriceAlert] = []
        self.on_alert = on_alert or self._default_alert_handler
        self._alerts_file = "price_alerts.json"
        self._load_alerts()

    # ---------------------------------------------------------------- #
    #  Alert yönetimi                                                    #
    # ---------------------------------------------------------------- #

    def add_alert(
        self,
        product_id: str,
        product_name: str,
        product_url: str,
        target_price: float,
        target_discount_pct: float = 0.0,
        check_in_stock: bool = True,
    ):
        alert = PriceAlert(
            product_id=product_id,
            product_name=product_name,
            product_url=product_url,
            target_price=target_price,
            target_discount_pct=target_discount_pct,
            check_in_stock=check_in_stock,
        )
        self.alerts.append(alert)
        self._save_alerts()
        logger.info(f"Alert eklendi: {product_name} → Hedef: {target_price} TRY")

    def add_alert_from_url(self, url: str, target_price: float, **kwargs):
        """URL'den otomatik ürün bilgisi çekip alert ekler."""
        product = self.scraper.get_product_from_url(url)
        if not product:
            logger.error(f"Ürün bilgisi alınamadı: {url}")
            return
        self.add_alert(
            product_id=product.id,
            product_name=product.name,
            product_url=url,
            target_price=target_price,
            **kwargs,
        )
        return product

    def remove_alert(self, product_id: str):
        self.alerts = [a for a in self.alerts if a.product_id != product_id]
        self._save_alerts()

    # ---------------------------------------------------------------- #
    #  Kontrol döngüsü                                                  #
    # ---------------------------------------------------------------- #

    def check_all(self) -> list[dict]:
        """Tüm alertleri bir kez kontrol eder."""
        triggered = []

        for alert in self.alerts:
            try:
                product = self.scraper.get_product(alert.product_id)
                if not product:
                    continue

                # DB'ye kaydet
                self.db.upsert_product(product)
                self.db.record_price(product)

                logger.info(
                    f"{product.name[:40]} → {product.price:.2f} TRY "
                    f"(hedef: {alert.target_price:.2f}) | "
                    f"indirim: %{product.discount_pct:.1f}"
                )

                # Stok kontrolü
                if alert.check_in_stock and not product.in_stock:
                    continue

                # Fiyat veya indirim hedefi
                price_triggered = product.price <= alert.target_price
                discount_triggered = (
                    alert.target_discount_pct > 0
                    and product.discount_pct >= alert.target_discount_pct
                )

                if price_triggered or discount_triggered:
                    info = {
                        "alert": alert,
                        "product": product,
                        "reason": (
                            f"Fiyat hedefi aşıldı ({product.price:.2f} ≤ {alert.target_price:.2f} TRY)"
                            if price_triggered
                            else f"İndirim hedefi aşıldı (%{product.discount_pct:.1f} ≥ %{alert.target_discount_pct:.1f})"
                        ),
                    }
                    triggered.append(info)
                    self.on_alert(info)

            except Exception as e:
                logger.error(f"Alert kontrolü hatası ({alert.product_id}): {e}")

        return triggered

    def run(self, interval_minutes: int = 60):
        """
        Sürekli çalışan takip döngüsü.
        Ctrl+C ile durdurulabilir.
        """
        logger.info(f"Fiyat takibi başladı. Kontrol aralığı: {interval_minutes} dakika")
        logger.info(f"Takip edilen: {len(self.alerts)} ürün")

        while True:
            try:
                logger.info("=== Fiyat kontrolü başlıyor ===")
                triggered = self.check_all()
                if triggered:
                    logger.info(f"⚡ {len(triggered)} alert tetiklendi!")
                else:
                    logger.info("✓ Hedef fiyatlara henüz ulaşılmadı.")

                logger.info(f"Sonraki kontrol {interval_minutes} dakika sonra...")
                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                logger.info("Takip durduruldu.")
                break
            except Exception as e:
                logger.error(f"Döngü hatası: {e}")
                time.sleep(60)

    # ---------------------------------------------------------------- #
    #  Alert handler'ları                                               #
    # ---------------------------------------------------------------- #

    @staticmethod
    def _default_alert_handler(info: dict):
        product = info["product"]
        alert = info["alert"]
        reason = info["reason"]
        print("\n" + "="*60)
        print(f"🔔 FİYAT ALARMI!")
        print(f"   Ürün   : {product.name}")
        print(f"   Fiyat  : {product.price:.2f} TRY (orijinal: {product.original_price:.2f} TRY)")
        print(f"   İndirim: %{product.discount_pct:.1f}")
        print(f"   Neden  : {reason}")
        print(f"   Link   : {alert.product_url}")
        print("="*60 + "\n")

    # ---------------------------------------------------------------- #
    #  E-posta bildirimi                                                #
    # ---------------------------------------------------------------- #

    @staticmethod
    def send_email_alert(
        info: dict,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_pass: str,
        to_email: str,
    ):
        """E-posta bildirimi gönderir."""
        product = info["product"]
        alert = info["alert"]

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔔 Fiyat Alarmı: {product.name[:50]}"
        msg["From"] = smtp_user
        msg["To"] = to_email

        html = f"""
        <html><body>
        <h2 style="color:#FF6000">🛍️ Trendyol Fiyat Alarmı</h2>
        <p><strong>Ürün:</strong> {product.name}</p>
        <p><strong>Güncel Fiyat:</strong> <span style="color:green;font-size:1.3em">{product.price:.2f} TRY</span></p>
        <p><strong>Orijinal Fiyat:</strong> <del>{product.original_price:.2f} TRY</del></p>
        <p><strong>İndirim:</strong> %{product.discount_pct:.1f}</p>
        <p><strong>Marka:</strong> {product.brand}</p>
        <p><strong>Satıcı:</strong> {product.seller}</p>
        <br>
        <a href="{alert.product_url}" style="background:#FF6000;color:white;padding:10px 20px;text-decoration:none;border-radius:5px">
            Ürüne Git →
        </a>
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, to_email, msg.as_string())
            logger.info(f"E-posta gönderildi: {to_email}")
        except Exception as e:
            logger.error(f"E-posta hatası: {e}")

    # ---------------------------------------------------------------- #
    #  Kalıcılık                                                        #
    # ---------------------------------------------------------------- #

    def _save_alerts(self):
        data = [
            {
                "product_id": a.product_id,
                "product_name": a.product_name,
                "product_url": a.product_url,
                "target_price": a.target_price,
                "target_discount_pct": a.target_discount_pct,
                "check_in_stock": a.check_in_stock,
            }
            for a in self.alerts
        ]
        with open(self._alerts_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_alerts(self):
        if not Path(self._alerts_file).exists():
            return
        try:
            with open(self._alerts_file, encoding="utf-8") as f:
                data = json.load(f)
            self.alerts = [PriceAlert(**a) for a in data]
            logger.info(f"{len(self.alerts)} alert yüklendi.")
        except Exception as e:
            logger.warning(f"Alert dosyası yüklenemedi: {e}")
