#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Avito Scraper - Production Ready
Extraction simplifiée: ville, type bien, caractéristiques essentielles

Prix extraction: 4-strategy cascade inspired by avito-ma open-source scraper
  1. JSON-LD structured data  (most reliable — Avito injects it for SEO)
  2. BeautifulSoup panel-body span  (classic HTML fallback)
  3. og:title meta tag  (already present)
  4. XPath text search  (last resort)
"""

import os
import sys
import time
import json
import random
import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import logging

# ── Dossiers ────────────────────────────────────────────────────────────────
os.makedirs('logs', exist_ok=True)

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/avito_scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class AvitoScraper:
    """Scraper Avito simplifié et robuste"""

    def __init__(self, max_pages: int = 10):
        self.max_pages = max_pages
        self.base_url = "https://www.avito.ma/fr/marrakech/appartements-a_vendre"
        self.data: List[Dict] = []
        self.driver = None

        self.type_mapping = {
            "appartement": "Appartement",
            "villa":       "Villa",
            "maison":      "Maison",
            "riad":        "Riad",
            "duplex":      "Duplex",
            "studio":      "Studio",
            "bureau":      "Bureau",
            "local":       "Local Commercial",
        }

    # ── Driver ───────────────────────────────────────────────────────────────

    def setup_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        try:
            self.driver = uc.Chrome(options=options, use_subprocess=True, version_main=145)
            logger.info("✅ Driver Chrome initialisé")
        except Exception as e:
            logger.error(f"❌ Erreur driver: {e}")
            raise

    # ── Helpers ──────────────────────────────────────────────────────────────

    def extract_type_bien(self, titre: str, description: str) -> str:
        text = (titre + " " + description).lower()
        for keyword, type_bien in self.type_mapping.items():
            if keyword in text:
                return type_bien
        return "Appartement"

    def extract_ville(self, location_text: str) -> str:
        if not location_text:
            return ""
        parts = location_text.split(",")
        ville = parts[-1].strip() if parts else location_text.strip()
        return ville.replace("Grand ", "").strip()

    def clean_price(self, price_text: str) -> Optional[float]:
        """Normalise n'importe quelle chaîne contenant un prix en float."""
        if not price_text:
            return None
        try:
            # Supprime tous les espaces (narrow no-break, nbsp, regular…)
            cleaned = re.sub(r'[\s\u00a0\u202f]+', '', str(price_text))
            cleaned = cleaned.replace("DH", "").replace("MAD", "").replace(",", "").strip()
            value = float(cleaned) if re.fullmatch(r'[\d.]+', cleaned) else None
            # Sanity-check: ignorer les valeurs hors plage réaliste (< 10 000 MAD)
            return value if value and value >= 10_000 else None
        except Exception:
            return None

    def clean_surface(self, surface_text: str) -> Optional[int]:
        if not surface_text:
            return None
        try:
            cleaned = surface_text.replace("m²", "").replace(" ", "").strip()
            return int(float(cleaned)) if re.fullmatch(r'[\d.]+', cleaned) else None
        except Exception:
            return None

    # ── Extraction du prix (cascade 4 stratégies) ────────────────────────────

    def extract_price(self, page_source: str) -> Optional[float]:
        """
        Cascade de 4 stratégies pour extraire le prix.

        Stratégie 1 — JSON-LD (la plus fiable)
        ----------------------------------------
        Avito injecte un bloc <script type="application/ld+json"> pour le SEO.
        Il contient un champ "offers.price" ou "price" avec le prix brut.
        Inspiré du scraper GitHub qui parsait le JavaScript via slimit ;
        ici on utilise directement json.loads() sur le bloc JSON-LD,
        ce qui est plus robuste et ne nécessite pas de dépendance supplémentaire.

        Stratégie 2 — BeautifulSoup panel-body
        ----------------------------------------
        Méthode classique du scraper GitHub :
          html_soup.find("div", class_="panel-body").span.string
        Fonctionne sur l'ancienne version du site.

        Stratégie 3 — og:title meta
        ----------------------------------------
        Format Avito : "Titre - 1 400 000 DH - ..."

        Stratégie 4 — XPath texte brut
        ----------------------------------------
        Parcourt tous les éléments contenant "DH" avec du texte court.
        """
        soup = BeautifulSoup(page_source, "html.parser")

        # ── Stratégie 1 : JSON-LD ────────────────────────────────────────────
        for script_tag in soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script_tag.string or "")
                # Le JSON-LD peut être une liste ou un dict
                items = ld if isinstance(ld, list) else [ld]
                for item in items:
                    # Cherche "offers.price" (Product schema)
                    offers = item.get("offers", {})
                    raw = (
                        offers.get("price")
                        or offers.get("lowPrice")
                        or item.get("price")          # schéma plat
                    )
                    if raw:
                        price = self.clean_price(str(raw))
                        if price:
                            logger.debug(f"💰 JSON-LD price: {price}")
                            return price
            except (json.JSONDecodeError, AttributeError):
                continue

        # ── Stratégie 2 : panel-body span (méthode GitHub) ──────────────────
        try:
            panel = soup.find("div", class_="panel-body")
            if panel:
                span_text = panel.find("span")
                if span_text and span_text.string:
                    price = self.clean_price(span_text.string)
                    if price:
                        logger.debug(f"💰 panel-body price: {price}")
                        return price
        except Exception:
            pass

        # ── Stratégie 3 : og:title ───────────────────────────────────────────
        try:
            og = soup.find("meta", property="og:title")
            if og:
                content = og.get("content", "")
                m = re.search(r'([\d\s\u00a0\u202f]+)\s*DH', content)
                if m:
                    price = self.clean_price(m.group(0))
                    if price:
                        logger.debug(f"💰 og:title price: {price}")
                        return price
        except Exception:
            pass

        # ── Stratégie 4 : XPath via Selenium (dernier recours) ───────────────
        # (appelée séparément depuis scrape_detail_page car nécessite self.driver)
        return None

    def extract_price_selenium_fallback(self) -> Optional[float]:
        """Stratégie 4 : parcours DOM via Selenium — uniquement si les 3 premières ont échoué."""
        try:
            elements = self.driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'DH') "
                "and not(contains(text(), 'DH/')) "
                "and string-length(normalize-space(text())) < 30]"
            )
            for el in elements:
                text = el.text.strip()
                if re.search(r'[\d]', text):
                    price = self.clean_price(text)
                    if price:
                        logger.debug(f"💰 XPath price: {price}")
                        return price
        except Exception:
            pass
        return None

    # ── Pages de résultats ───────────────────────────────────────────────────

    def scrape_listing_page(self, page_num: int) -> List[str]:
        url = f"{self.base_url}?o={page_num}"
        logger.info(f"📄 Page {page_num}: {url}")
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/appartement']"))
            )
            time.sleep(random.uniform(2, 3))
        except Exception as e:
            logger.warning(f"⚠️ Timeout page {page_num}: {e}")
            return []

        urls = []
        try:
            cards = self.driver.find_elements(
                By.CSS_SELECTOR, "a[href*='/fr/'][href*='/appartement']"
            )
            for card in cards:
                href = card.get_attribute("href")
                if href and "avito.ma" in href:
                    urls.append(href)
        except Exception as e:
            logger.error(f"❌ Erreur extraction URLs: {e}")

        logger.info(f"✓ {len(urls)} URLs collectées")
        return list(set(urls))

    # ── Page détail ──────────────────────────────────────────────────────────

    def scrape_detail_page(self, url: str) -> Optional[Dict]:
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            )
            time.sleep(random.uniform(1.5, 2.5))
        except Exception:
            logger.warning(f"⚠️ Timeout: {url}")
            return None

        data = {
            "id_annonce":    url.split("/")[-1].split(".")[0][:50],
            "url":           url,
            "source":        "Avito",
            "date_scraping": datetime.now().strftime("%Y-%m-%d"),
        }

        try:
            # ── Titre ────────────────────────────────────────────────────────
            titre = self.driver.find_element(By.TAG_NAME, "h1").text.strip()
            data["titre"] = titre

            # ── Prix (cascade 4 stratégies) ──────────────────────────────────
            page_source = self.driver.page_source
            prix = self.extract_price(page_source)           # stratégies 1-3
            if prix is None:
                prix = self.extract_price_selenium_fallback()  # stratégie 4
            data["prix"] = prix

            if prix:
                logger.info(f"💰 Prix extrait: {prix:,.0f} MAD")
            else:
                logger.warning(f"⚠️ Prix non trouvé pour: {url}")

            # ── Localisation ─────────────────────────────────────────────────
            try:
                loc_el = self.driver.find_element(By.CSS_SELECTOR, "span.sc-16573058-17")
                data["ville"] = self.extract_ville(loc_el.text)
            except Exception:
                # Fallback: extraire addressLocality depuis JSON-LD
                data["ville"] = self._extract_ville_from_jsonld(page_source)

            # ── Caractéristiques ─────────────────────────────────────────────
            caracteristiques = {}
            try:
                carac_divs = self.driver.find_elements(By.CSS_SELECTOR, "div.sc-cd1c365e-1")
                for div in carac_divs:
                    try:
                        content = div.find_element(By.CSS_SELECTOR, "div.sc-cd1c365e-2")
                        spans = content.find_elements(By.TAG_NAME, "span")
                        if len(spans) >= 2:
                            caracteristiques[spans[1].text.strip()] = spans[0].text.strip()
                    except Exception:
                        continue
            except Exception:
                pass

            data["surface_m2"]      = self.clean_surface(
                caracteristiques.get("Surface totale",
                caracteristiques.get("Surface habitable", ""))
            )
            data["nb_chambres"]     = caracteristiques.get("Chambres", "")
            data["nb_salles_bain"]  = caracteristiques.get("Salle de bain", "")
            data["etage"]           = caracteristiques.get("Étage", "")

            # ── Description ──────────────────────────────────────────────────
            try:
                desc_el = self.driver.find_element(By.CSS_SELECTOR, "div.sc-9bb253d7-0")
                description = desc_el.text.strip()
                data["description"] = description[:500]
            except Exception:
                description = ""
                data["description"] = ""

            # ── Type de bien ─────────────────────────────────────────────────
            data["type_bien"] = self.extract_type_bien(titre, description)

            # ── Équipements (booléens) ────────────────────────────────────────
            text_search = (titre + " " + description + " " + str(caracteristiques)).lower()
            data["parking"]   = 1 if "parking"   in text_search or "garage"   in text_search else 0
            data["ascenseur"] = 1 if "ascenseur" in text_search else 0
            data["balcon"]    = 1 if "balcon"    in text_search or "terrasse" in text_search else 0
            data["piscine"]   = 1 if "piscine"   in text_search else 0
            data["jardin"]    = 1 if "jardin"    in text_search else 0

            logger.info(f"✅ {data['type_bien']} | {data['ville']} | {data['prix']} MAD")
            return data

        except Exception as e:
            logger.error(f"❌ Erreur extraction: {e}")
            return None

    def _extract_ville_from_jsonld(self, page_source: str) -> str:
        """Fallback: extrait addressLocality depuis le JSON-LD (méthode GitHub adaptée)."""
        soup = BeautifulSoup(page_source, "html.parser")
        for script_tag in soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script_tag.string or "")
                items = ld if isinstance(ld, list) else [ld]
                for item in items:
                    loc = item.get("address", {})
                    locality = loc.get("addressLocality", "")
                    if locality:
                        return self.extract_ville(locality)
            except (json.JSONDecodeError, AttributeError):
                continue
        return ""

    # ── Scraping complet ─────────────────────────────────────────────────────

    def scrape(self) -> pd.DataFrame:
        logger.info("🚀 Démarrage scraping Avito")
        logger.info(f"Pages max: {self.max_pages}")

        self.setup_driver()

        try:
            # Phase 1 : collecter URLs
            all_urls = []
            for page in range(1, self.max_pages + 1):
                urls = self.scrape_listing_page(page)
                all_urls.extend(urls)
                time.sleep(random.uniform(2, 4))

            logger.info(f"📊 Total URLs: {len(all_urls)}")

            # Phase 2 : scraper les détails
            for idx, url in enumerate(all_urls, 1):
                logger.info(f"[{idx}/{len(all_urls)}] Extraction...")
                detail = self.scrape_detail_page(url)
                if detail:
                    self.data.append(detail)
                time.sleep(random.uniform(3, 5))

            # Sauvegarde
            df = pd.DataFrame(self.data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"data/raw/avito/avito_{timestamp}.csv"
            os.makedirs("data/raw/avito", exist_ok=True)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')

            logger.info(f"💾 Sauvegardé: {filepath}")
            logger.info(f"📊 {len(df)} annonces extraites")
            return df

        finally:
            if self.driver:
                self.driver.quit()
                logger.info("✅ Driver fermé")


# ── Point d'entrée ───────────────────────────────────────────────────────────

def main():
    scraper = AvitoScraper(max_pages=2)
    df = scraper.scrape()

    print("\n" + "=" * 60)
    print("STATISTIQUES AVITO")
    print("=" * 60)
    print(f"Total annonces : {len(df)}")

    if not df.empty:
        print(f"\nTypes de biens :\n{df['type_bien'].value_counts()}")
        print(f"\nVilles :\n{df['ville'].value_counts()}")
        prix_valides = df['prix'].dropna()
        if not prix_valides.empty:
            print(f"\nPrix moyen  : {prix_valides.mean():,.0f} MAD")
            print(f"Prix médian : {prix_valides.median():,.0f} MAD")
            print(f"Prix min    : {prix_valides.min():,.0f} MAD")
            print(f"Prix max    : {prix_valides.max():,.0f} MAD")
            print(f"Prix trouvés: {len(prix_valides)}/{len(df)} annonces")
        else:
            print("\n⚠️  Aucun prix extrait")
    print("=" * 60)


if __name__ == "__main__":
    main()