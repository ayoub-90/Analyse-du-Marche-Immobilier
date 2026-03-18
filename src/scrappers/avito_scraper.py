#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Avito Scraper - Production Ready
Extraction simplifiée: ville, type bien, caractéristiques essentielles
"""

import os
import sys
import time
import random
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import logging

# Configuration logging
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
        
        # Mapping types de biens
        self.type_mapping = {
            "appartement": "Appartement",
            "villa": "Villa",
            "maison": "Maison",
            "riad": "Riad",
            "duplex": "Duplex",
            "studio": "Studio",
            "bureau": "Bureau",
            "local": "Local Commercial"
        }
    
    def setup_driver(self):
        """Initialise le driver Chrome"""
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        try:
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            logger.info("✅ Driver Chrome initialisé")
        except Exception as e:
            logger.error(f"❌ Erreur driver: {e}")
            raise
    
    def extract_type_bien(self, titre: str, description: str) -> str:
        """Extrait le type de bien depuis titre/description"""
        text = (titre + " " + description).lower()
        
        for keyword, type_bien in self.type_mapping.items():
            if keyword in text:
                return type_bien
        
        return "Appartement"  # Par défaut
    
    def extract_ville(self, location_text: str) -> str:
        """Extrait UNIQUEMENT la ville (pas de région)"""
        if not location_text:
            return ""
        
        # Format Avito: "Quartier, Ville" ou "Ville"
        parts = location_text.split(",")
        ville = parts[-1].strip() if parts else location_text.strip()
        
        # Nettoyer
        ville = ville.replace("Grand ", "").strip()
        
        return ville
    
    def clean_price(self, price_text: str) -> Optional[float]:
        """Nettoie et convertit le prix"""
        if not price_text:
            return None
        
        try:
            cleaned = price_text.replace(" ", "").replace("DH", "").replace(",", "")
            return float(cleaned) if cleaned.replace(".", "").isdigit() else None
        except:
            return None
    
    def clean_surface(self, surface_text: str) -> Optional[int]:
        """Nettoie et convertit la surface"""
        if not surface_text:
            return None
        
        try:
            cleaned = surface_text.replace("m²", "").replace(" ", "").strip()
            return int(float(cleaned)) if cleaned.replace(".", "").isdigit() else None
        except:
            return None
    
    def scrape_listing_page(self, page_num: int) -> List[str]:
        """Collecte les URLs d'une page de résultats"""
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
        
        # Extraire URLs
        urls = []
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/fr/'][href*='/appartement']")
            for card in cards:
                href = card.get_attribute("href")
                if href and "avito.ma" in href:
                    urls.append(href)
        except Exception as e:
            logger.error(f"❌ Erreur extraction URLs: {e}")
        
        logger.info(f"✓ {len(urls)} URLs collectées")
        return list(set(urls))  # Déduplication
    
    def scrape_detail_page(self, url: str) -> Optional[Dict]:
        """Scrape une page détail d'annonce"""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            )
            time.sleep(random.uniform(1.5, 2.5))
        except Exception as e:
            logger.warning(f"⚠️ Timeout: {url}")
            return None
        
        data = {
            "id_annonce": url.split("/")[-1].split(".")[0][:50],
            "url": url,
            "source": "Avito",
            "date_scraping": datetime.now().strftime("%Y-%m-%d")
        }
        
        try:
            # TITRE
            titre = self.driver.find_element(By.TAG_NAME, "h1").text.strip()
            data["titre"] = titre
            
            # PRIX
            try:
                prix_el = self.driver.find_element(By.CSS_SELECTOR, "p.sc-1x0vz2r-0[font-weight='bold']")
                data["prix"] = self.clean_price(prix_el.text)
            except:
                data["prix"] = None
            
            # LOCALISATION (VILLE UNIQUEMENT)
            try:
                loc_el = self.driver.find_element(By.CSS_SELECTOR, "span.sc-16573058-17")
                data["ville"] = self.extract_ville(loc_el.text)
            except:
                data["ville"] = ""
            
            # CARACTÉRISTIQUES
            caracteristiques = {}
            try:
                carac_divs = self.driver.find_elements(By.CSS_SELECTOR, "div.sc-cd1c365e-1")
                for div in carac_divs:
                    try:
                        content = div.find_element(By.CSS_SELECTOR, "div.sc-cd1c365e-2")
                        spans = content.find_elements(By.TAG_NAME, "span")
                        if len(spans) >= 2:
                            valeur = spans[0].text.strip()
                            label = spans[1].text.strip()
                            caracteristiques[label] = valeur
                    except:
                        continue
            except:
                pass
            
            # Mapper les caractéristiques essentielles
            data["surface_m2"] = self.clean_surface(
                caracteristiques.get("Surface totale", 
                caracteristiques.get("Surface habitable", ""))
            )
            data["nb_chambres"] = caracteristiques.get("Chambres", "")
            data["nb_salles_bain"] = caracteristiques.get("Salle de bain", "")
            data["etage"] = caracteristiques.get("Étage", "")
            
            # DESCRIPTION
            try:
                desc_el = self.driver.find_element(By.CSS_SELECTOR, "div.sc-9bb253d7-0")
                description = desc_el.text.strip()
                data["description"] = description[:500]  # Limiter à 500 chars
            except:
                description = ""
                data["description"] = ""
            
            # TYPE DE BIEN (extrait du titre + description)
            data["type_bien"] = self.extract_type_bien(titre, description)
            
            # ÉQUIPEMENTS (booléens)
            text_search = (titre + " " + description + " " + str(caracteristiques)).lower()
            data["parking"] = 1 if "parking" in text_search or "garage" in text_search else 0
            data["ascenseur"] = 1 if "ascenseur" in text_search else 0
            data["balcon"] = 1 if "balcon" in text_search or "terrasse" in text_search else 0
            data["piscine"] = 1 if "piscine" in text_search else 0
            data["jardin"] = 1 if "jardin" in text_search else 0
            
            logger.info(f"✅ {data['type_bien']} | {data['ville']} | {data['prix']} MAD")
            return data
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction: {e}")
            return None
    
    def scrape(self) -> pd.DataFrame:
        """Lance le scraping complet"""
        logger.info("🚀 Démarrage scraping Avito")
        logger.info(f"Pages max: {self.max_pages}")
        
        self.setup_driver()
        
        try:
            # Phase 1: Collecter URLs
            all_urls = []
            for page in range(1, self.max_pages + 1):
                urls = self.scrape_listing_page(page)
                all_urls.extend(urls)
                time.sleep(random.uniform(2, 4))
            
            logger.info(f"📊 Total URLs: {len(all_urls)}")
            
            # Phase 2: Scraper détails
            for idx, url in enumerate(all_urls, 1):
                logger.info(f"[{idx}/{len(all_urls)}] Extraction...")
                data = self.scrape_detail_page(url)
                if data:
                    self.data.append(data)
                time.sleep(random.uniform(3, 5))
            
            # Sauvegarder
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


def main():
    """Point d'entrée"""
    scraper = AvitoScraper(max_pages=5)  # Test avec 5 pages
    df = scraper.scrape()
    
    # Stats rapides
    print("\n" + "="*60)
    print("STATISTIQUES AVITO")
    print("="*60)
    print(f"Total annonces: {len(df)}")
    print(f"\nTypes de biens:")
    print(df['type_bien'].value_counts())
    print(f"\nVilles:")
    print(df['ville'].value_counts())
    print(f"\nPrix moyen: {df['prix'].mean():,.0f} MAD")
    print("="*60)


if __name__ == "__main__":
    main()