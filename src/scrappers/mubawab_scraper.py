#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mubawab Scraper - Production Ready
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
import json

# Créer dossier logs
os.makedirs('logs', exist_ok=True)

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/mubawab_scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class MubawabScraper:
    """Scraper Mubawab simplifié et robuste avec gestion d'état (Micro-batch)"""
    
    def __init__(self, target_count: int = 20):
        self.target_count = target_count
        self.base_url = "https://www.mubawab.ma/fr/sc/appartements-a-vendre"
        self.data: List[Dict] = []
        self.driver = None
        self.state_file = "data/state/mubawab_state.json"
        
        # Mapping types de biens (identique à Avito pour uniformité)
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
    
    # def setup_driver(self):
    #     """Initialise le driver Chrome"""
    #     options = uc.ChromeOptions()
    #     options.add_argument("--disable-blink-features=AutomationControlled")
    #     options.add_argument("--no-sandbox")
    #     options.add_argument("--disable-dev-shm-usage")
    #     options.add_argument("--window-size=1920,1080")
        
    #     try:
    #         self.driver = uc.Chrome(options=options, use_subprocess=True, version_main=145)
    #         logger.info("✅ Driver Chrome initialisé")
    #     except Exception as e:
    #         logger.error(f"❌ Erreur driver: {e}")
    #         raise
    def setup_driver(self):
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('AIRFLOW_HOME')

        if is_docker:
            from selenium import webdriver as selenium_webdriver
            from selenium.webdriver.chrome.service import Service

            options = selenium_webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.binary_location = "/usr/bin/chromium"

            service = Service("/usr/bin/chromedriver")
            self.driver = selenium_webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            logger.info("✅ Driver Chromium (Docker) initialisé")
        else:
            options = uc.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            self.driver.set_page_load_timeout(30)
            logger.info("✅ Driver Chrome (Local) initialisé")
    def extract_type_bien(self, titre: str, type_from_page: str = "") -> str:
        """Extrait le type de bien"""
        text = (titre + " " + type_from_page).lower()
        
        for keyword, type_bien in self.type_mapping.items():
            if keyword in text:
                return type_bien
        
        return "Appartement"
    
    def extract_ville(self, location_text: str) -> str:
        """Extrait UNIQUEMENT la ville (pas de quartier)"""
        if not location_text:
            return ""
        
        # Format Mubawab: "Quartier à Ville" ou "Ville"
        if " à " in location_text:
            parts = location_text.split(" à ")
            ville = parts[-1].strip()
        else:
            ville = location_text.split(",")[-1].strip()
        
        return ville
    
    def clean_price(self, price_text: str) -> Optional[float]:
        """Nettoie et convertit le prix"""
        if not price_text:
            return None
        
        try:
            cleaned = price_text.replace("\u00a0", "").replace(" ", "").replace("DH", "").replace(",", "")
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
        url = f"{self.base_url}?page={page_num}"
        logger.info(f"📄 Page {page_num}: {url}")
        
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/appartement-']"))
            )
            self.driver.execute_script("window.stop();")
            time.sleep(random.uniform(2, 3))
        except Exception as e:
            logger.warning(f"⚠️ Timeout page {page_num}: {e}")
            return []
        
        # Extraire URLs
        urls = []
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/appartement-']")
            for card in cards:
                href = card.get_attribute("href")
                if href and "mubawab.ma" in href:
                    urls.append(href)
        except Exception as e:
            logger.error(f"❌ Erreur extraction URLs: {e}")
        
        logger.info(f"✓ {len(urls)} URLs collectées")
        return list(set(urls))
    
    def scrape_detail_page(self, url: str) -> Optional[Dict]:
        """Scrape une page détail d'annonce"""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1, h3.orangeTit"))
            )
            time.sleep(random.uniform(2, 3))
        except Exception as e:
            logger.warning(f"⚠️ Timeout: {url}")
            # self.driver.execute_script("window.stop();")
            return None
        
        data = {
            "id_annonce": url.split("/")[-1].split("-")[0][:50],
            "url": url,
            "source": "Mubawab",
            "date_scraping": datetime.now().strftime("%Y-%m-%d")
        }
        
        try:
            # TITRE
            try:
                titre = self.driver.find_element(By.CSS_SELECTOR, "h1.searchTitle").text.strip()
            except:
                titre = ""
            data["titre"] = titre
            
            # PRIX
            try:
                prix_el = self.driver.find_element(By.CSS_SELECTOR, "h3.orangeTit")
                data["prix"] = self.clean_price(prix_el.text)
            except:
                data["prix"] = None
            
            # LOCALISATION (VILLE UNIQUEMENT)
            try:
                loc_el = self.driver.find_element(By.CSS_SELECTOR, "h3.greyTit")
                data["ville"] = self.extract_ville(loc_el.text)
            except:
                data["ville"] = ""
            
            # CARACTÉRISTIQUES (en haut de page)
            caracteristiques = {}
            try:
                detail_features = self.driver.find_elements(By.CSS_SELECTOR, "div.adDetailFeature span")
                for span in detail_features:
                    text = span.text.strip()
                    if "m²" in text:
                        caracteristiques["Surface"] = text
                    elif "chambre" in text.lower():
                        caracteristiques["Chambres"] = text.split()[0]
                    elif "salle" in text.lower() and "bain" in text.lower():
                        caracteristiques["Salles de bain"] = text.split()[0]
                    elif "pièce" in text.lower():
                        caracteristiques["Pièces"] = text.split()[0]
            except:
                pass
            
            # CARACTÉRISTIQUES GÉNÉRALES (bas de page)
            try:
                main_features = self.driver.find_elements(By.CSS_SELECTOR, "div.adMainFeature")
                for feat in main_features:
                    try:
                        label = feat.find_element(By.CSS_SELECTOR, "p.adMainFeatureContentLabel").text.strip()
                        value = feat.find_element(By.CSS_SELECTOR, "p.adMainFeatureContentValue").text.strip()
                        caracteristiques[label] = value
                    except:
                        continue
            except:
                pass
            
            # Mapper les caractéristiques essentielles
            data["surface_m2"] = self.clean_surface(caracteristiques.get("Surface", ""))
            data["nb_chambres"] = caracteristiques.get("Chambres", "")
            data["nb_salles_bain"] = caracteristiques.get("Salles de bain", "")
            data["etage"] = caracteristiques.get("Étage du bien", "")
            
            # TYPE DE BIEN
            type_from_page = caracteristiques.get("Type de bien", "")
            data["type_bien"] = self.extract_type_bien(titre, type_from_page)
            
            # DESCRIPTION
            try:
                desc_el = self.driver.find_element(By.CSS_SELECTOR, "div.blockProp p")
                description = desc_el.text.strip()
                data["description"] = description[:500]
            except:
                description = ""
                data["description"] = ""
            
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
    
    def get_state(self) -> int:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f).get('last_page', 1)
            except Exception:
                pass
        return 1

    def save_state(self, page: int):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump({'last_page': page}, f)

    def scrape(self) -> pd.DataFrame:
        """Lance le scraping complet"""
        logger.info("🚀 Démarrage scraping Mubawab (Micro-batching)")
        logger.info(f"Cible: {self.target_count} annonces")
        
        self.setup_driver()
        
        try:
            current_page = self.get_state()
            logger.info(f"🔄 Reprise depuis la page {current_page}")
            
            while len(self.data) < self.target_count:
                logger.info(f"📄 Scraping Page {current_page}...")
                urls = self.scrape_listing_page(current_page)
                
                if not urls:
                    logger.warning("Fin des pages atteintes ou blocage.")
                    break
                    
                for idx, url in enumerate(urls, 1):
                    if len(self.data) >= self.target_count:
                        break
                    logger.info(f"[{len(self.data)+1}/{self.target_count}] Extraction: {url}")
                    data = self.scrape_detail_page(url)
                    if data:
                        self.data.append(data)
                    time.sleep(random.uniform(2, 4))
                
                current_page += 1
                self.save_state(current_page)
                time.sleep(random.uniform(1, 3))
            
            # Sauvegarder
            df = pd.DataFrame(self.data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"data/raw/mubawab/mubawab_{timestamp}.csv"
            
            os.makedirs("data/raw/mubawab", exist_ok=True)
            if not df.empty:
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            logger.info(f"💾 Sauvegardé: {filepath}")
            logger.info(f"📊 {len(df)} annonces extraites")
            self.driver.execute_script("window.stop();")
            
            return df
            
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("✅ Driver fermé")


def main():
    """Point d'entrée"""
    scraper = MubawabScraper(target_count=10)
    df = scraper.scrape()
    
    # Filtrer uniquement les annonces avec prix
    df_avec_prix = df[df['prix'].notna()].copy()
    
    # Stats rapides
    print("\n" + "="*60)
    print("STATISTIQUES MUBAWAB")
    print("="*60)
    print(f"Total annonces extraites : {len(df)}")
    print(f"Annonces avec prix       : {len(df_avec_prix)}")
    print(f"Annonces sans prix       : {len(df) - len(df_avec_prix)}")
    
    if not df_avec_prix.empty:
        print(f"\nTypes de biens:\n{df_avec_prix['type_bien'].value_counts()}")
        print(f"\nVilles:\n{df_avec_prix['ville'].value_counts()}")
        print(f"\nPrix moyen  : {df_avec_prix['prix'].mean():,.0f} MAD")
        print(f"Prix médian : {df_avec_prix['prix'].median():,.0f} MAD")
        print(f"Prix min    : {df_avec_prix['prix'].min():,.0f} MAD")
        print(f"Prix max    : {df_avec_prix['prix'].max():,.0f} MAD")
    else:
        print("\n⚠️ Aucun prix extrait")
    
    print("="*60)


if __name__ == "__main__":
    main()