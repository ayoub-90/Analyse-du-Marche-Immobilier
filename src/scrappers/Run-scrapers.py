#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORCHESTRATEUR PARALLÈLE - Avito + Mubawab
Exécute les deux scrapers simultanément avec monitoring
"""

import os
import sys
import time
import threading
import subprocess
from datetime import datetime
import logging

# Windows UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/parallel_scraping.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# =============================================================================
# CONFIG
# =============================================================================

SCRAPERS = {
    "avito": {
        "script": "src/scripts/extraction/scrapping-avito.py",
        "name": "Avito",
        "color": "\033[94m",  # Bleu
    },
    "mubawab": {
        "script": "src/scripts/extraction/scraper-mubawab.py",
        "name": "Mubawab",
        "color": "\033[91m",  # Rouge
    }
}

RESET = "\033[0m"


# =============================================================================
# FONCTION EXÉCUTION SCRAPER
# =============================================================================

def run_scraper(scraper_name, script_path):
    """Exécute un scraper dans un subprocess"""
    
    color = SCRAPERS[scraper_name]["color"]
    name = SCRAPERS[scraper_name]["name"]
    
    log.info(f"{color}[{name}] Démarrage...{RESET}")
    
    try:
        # Lancer le script Python
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            bufsize=1
        )
        
        # Lire output en temps réel
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"{color}[{name}] {line.rstrip()}{RESET}")
        
        process.wait()
        
        if process.returncode == 0:
            log.info(f"{color}[{name}] ✅ Terminé avec succès{RESET}")
        else:
            log.warning(f"{color}[{name}] ⚠️ Terminé avec code {process.returncode}{RESET}")
        
        return process.returncode
    
    except Exception as e:
        log.error(f"{color}[{name}] ❌ Erreur: {e}{RESET}")
        return 1


# =============================================================================
# MONITORING
# =============================================================================

def monitor_progress():
    """Affiche la progression des deux scrapers"""
    
    import time
    
    while True:
        time.sleep(30)  # Toutes les 30 secondes
        
        # Lire fichiers CSV partiels
        avito_files = []
        mubawab_files = []
        
        try:
            for f in os.listdir("data/raw"):
                if f.startswith("avito_") and "_partial_" in f:
                    avito_files.append(f)
                elif f.startswith("mubawab_") and "_partial_" in f:
                    mubawab_files.append(f)
        except:
            pass
        
        if avito_files or mubawab_files:
            log.info(f"\n{'='*60}")
            log.info("📊 PROGRESSION")
            log.info(f"{'='*60}")
            
            if avito_files:
                latest = max(avito_files)
                count = latest.split("_partial_")[1].split(".")[0]
                log.info(f"  Avito    : {count} annonces extraites")
            
            if mubawab_files:
                latest = max(mubawab_files)
                count = latest.split("_partial_")[1].split(".")[0]
                log.info(f"  Mubawab  : {count} annonces extraites")
            
            log.info(f"{'='*60}\n")


# =============================================================================
# MAIN PARALLÈLE
# =============================================================================

def scrape_parallel():
    """Lance Avito et Mubawab en parallèle"""
    
    log.info("\n" + "="*70)
    log.info("🚀 SCRAPING PARALLÈLE - Avito + Mubawab")
    log.info("="*70)
    log.info(f"Démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("="*70 + "\n")
    
    # Vérifier que les scripts existent
    for name, config in SCRAPERS.items():
        if not os.path.exists(config["script"]):
            log.error(f"❌ Script manquant: {config['script']}")
            return
    
    # Créer threads
    threads = []
    
    for name, config in SCRAPERS.items():
        thread = threading.Thread(
            target=run_scraper,
            args=(name, config["script"]),
            name=config["name"]
        )
        threads.append(thread)
    
    # Lancer monitoring
    monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
    monitor_thread.start()
    
    # Démarrer tous les scrapers
    for thread in threads:
        thread.start()
        time.sleep(2)  # Décalage 2s entre chaque
    
    # Attendre fin de tous
    for thread in threads:
        thread.join()
    
    log.info("\n" + "="*70)
    log.info("✅ SCRAPING PARALLÈLE TERMINÉ")
    log.info("="*70)
    log.info(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("="*70 + "\n")
    
    # Résumé final
    show_final_summary()


# =============================================================================
# RÉSUMÉ FINAL
# =============================================================================

def show_final_summary():
    """Affiche le résumé des fichiers générés"""
    
    import glob
    
    log.info("\n📁 FICHIERS GÉNÉRÉS:\n")
    
    # Avito
    avito_finals = glob.glob("data/raw/avito_*_FINAL.csv")
    if avito_finals:
        latest = max(avito_finals, key=os.path.getctime)
        import pandas as pd
        try:
            df = pd.read_csv(latest)
            log.info(f"  ✅ Avito    : {latest}")
            log.info(f"     → {len(df)} annonces | {len(df.columns)} colonnes")
        except:
            log.info(f"  ✅ Avito    : {latest}")
    
    # Mubawab
    mubawab_finals = glob.glob("data/raw/mubawab_*_FINAL.csv")
    if mubawab_finals:
        latest = max(mubawab_finals, key=os.path.getctime)
        import pandas as pd
        try:
            df = pd.read_csv(latest)
            log.info(f"  ✅ Mubawab  : {latest}")
            log.info(f"     → {len(df)} annonces | {len(df.columns)} colonnes")
        except:
            log.info(f"  ✅ Mubawab  : {latest}")
    
    log.info("\n")


# =============================================================================
# ALTERNATIVE: EXÉCUTION SÉQUENTIELLE
# =============================================================================

def scrape_sequential():
    """Lance Avito puis Mubawab (l'un après l'autre)"""
    
    log.info("\n" + "="*70)
    log.info("🔄 SCRAPING SÉQUENTIEL - Avito → Mubawab")
    log.info("="*70 + "\n")
    
    for name, config in SCRAPERS.items():
        log.info(f"\n{'='*60}")
        log.info(f"Lancement {config['name']}")
        log.info(f"{'='*60}\n")
        
        returncode = run_scraper(name, config["script"])
        
        if returncode != 0:
            log.warning(f"{config['name']} a rencontré des erreurs")
        
        time.sleep(5)  # Pause entre les deux
    
    log.info("\n" + "="*70)
    log.info("✅ SCRAPING SÉQUENTIEL TERMINÉ")
    log.info("="*70 + "\n")
    
    show_final_summary()


# =============================================================================
# MENU PRINCIPAL
# =============================================================================

def main():
    print("\n" + "="*70)
    print("🏠 ORCHESTRATEUR SCRAPING IMMOBILIER")
    print("="*70)
    print("\nChoisissez le mode d'exécution:")
    print("\n  1. PARALLÈLE   - Avito + Mubawab en même temps (RAPIDE)")
    print("  2. SÉQUENTIEL  - Avito puis Mubawab (PLUS STABLE)")
    print("  3. AVITO SEUL")
    print("  4. MUBAWAB SEUL")
    print("\n  Q. QUITTER")
    print("="*70)
    
    choice = input("\nVotre choix (1-4 ou Q): ").strip().lower()
    
    if choice == "1":
        scrape_parallel()
    elif choice == "2":
        scrape_sequential()
    elif choice == "3":
        log.info("\n🔵 Lancement Avito seul...\n")
        run_scraper("avito", SCRAPERS["avito"]["script"])
        show_final_summary()
    elif choice == "4":
        log.info("\n🔴 Lancement Mubawab seul...\n")
        run_scraper("mubawab", SCRAPERS["mubawab"]["script"])
        show_final_summary()
    elif choice == "q":
        log.info("Annulé par l'utilisateur")
    else:
        log.error("Choix invalide")


# =============================================================================
# LANCEMENT
# =============================================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("\n⏹ Arrêt par Ctrl+C")
    except Exception as e:
        log.error(f"Erreur: {e}")
        import traceback
        traceback.print_exc()