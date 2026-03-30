# 🕷️ Guide — Scraping de Données Immobilières

## Vue d'ensemble

Le module de scraping collecte automatiquement les annonces des deux principaux portails immobiliers marocains :

| Portail | URL | Couverture |
|---------|-----|-----------|
| **Avito** | avito.ma | Marrakech (extensible) |
| **Mubawab** | mubawab.ma | Multi-villes nationalement |

---

## 📁 Fichiers Impliqués

```
src/scrappers/
├── avito_scraper.py        ← Scraper Avito principal
├── mubawab_scraper.py      ← Scraper Mubawab principal
└── Run-scrapers.py         ← Orchestrateur (lance les deux en parallèle)
```

---

## 🔧 Fonctionnement Technique

### Technologie
- **`undetected-chromedriver`** — Contourne la détection bot de Chrome
- **`selenium`** — Automatisation du navigateur
- **`version_main=145`** — Fixé pour correspondre à Chrome v145 installé

### Flux de scraping

```
1. Lancement Chrome "furtif" (undetected-chromedriver)
           ↓
2. Navigation page liste (ex: avito.ma/fr/marrakech/appartements-a_vendre)
           ↓
3. Collecte des URLs d'annonces (tous les liens sur la page)
           ↓
4. Pour chaque URL → page détail :
   - Titre (balise h1)
   - Prix  (meta og:title → regex [\d\s]+DH, fallback XPath)
   - Ville (CSS selector)
   - Surface (attributs détail)
   - Chambres, salle de bain, étage
   - Équipements (parking, ascenseur, balcon, piscine, jardin)
   - Description
           ↓
5. Sauvegarde CSV → data/raw/{source}/{source}_{timestamp}.csv
```

---

## ⚙️ Configuration

### Nombre de pages

Dans `avito_scraper.py` et `mubawab_scraper.py`, fonction `main()` :

```python
# TEST (batch limité)
scraper.scrape(max_pages=2)

# PRODUCTION (scraping complet)
scraper.scrape(max_pages=50)
```

### Délai anti-détection

Configuré automatiquement avec `random.uniform(1.5, 2.5)` secondes entre chaque annonce.

---

## ▶️ Exécution

### Scraper individuel (test)
```bash
# Avito uniquement
python src/scrappers/avito_scraper.py

# Mubawab uniquement
python src/scrappers/mubawab_scraper.py
```

### Scraping parallèle (production)
```bash
python src/scrappers/Run-scrapers.py
```
Ou via Makefile :
```bash
make scrape-all
```

---

## 📂 Format de Sortie

**Fichiers générés :** `data/raw/avito/avito_{YYYYMMDD_HHMMSS}.csv`

| Colonne | Type | Description |
|---------|------|-------------|
| `id_annonce` | str | Identifiant unique extrait de l'URL |
| `url` | str | URL complète de l'annonce |
| `source` | str | `"Avito"` ou `"Mubawab"` |
| `date_scraping` | date | Date d'extraction |
| `titre` | str | Titre de l'annonce |
| `prix` | float | Prix en MAD |
| `ville` | str | Ville du bien |
| `surface_m2` | int | Surface en m² |
| `nb_chambres` | str | Nombre de chambres (texte) |
| `nb_salles_bain` | str | Nombre de salles de bain |
| `etage` | str | Étage |
| `type_bien` | str | `Appartement`, `Villa`, `Duplex`, etc. |
| `parking` | int | 0/1 |
| `ascenseur` | int | 0/1 |
| `balcon` | int | 0/1 |
| `piscine` | int | 0/1 |
| `jardin` | int | 0/1 |
| `description` | str | Description complète |

---

## ⚠️ Problèmes Connus et Solutions

| Problème | Cause | Solution |
|----------|-------|----------|
| `SessionNotCreatedException: Chrome version 146 vs 145` | ChromeDriver version mismatch | `version_main=145` ajouté dans `uc.Chrome()` |
| Prix = `None` | Avito utilise `\u202f` (narrow-space) pas l'espace classique | `re.sub(r'\s+', '', price_text)` dans `clean_price()` |
| `FileNotFoundError: logs/` | Dossier `logs/` inexistant | `os.makedirs('logs', exist_ok=True)` avant logging |
| Timeout sur certaines annonces | Page lente / protégée | Annonce ignorée, log WARNING, scraping continue |

---

## 🔄 Intégration Airflow

Le scraping est orchestré automatiquement via `airflow/dags/immobilier_scraping_dag.py` :
- **Schedule** : Tous les jours à 2h00 du matin
- **Tâches** : `scrape_avito` → `scrape_mubawab` (en parallèle) → `combine_data`

> Voir [`05_AIRFLOW.md`](05_AIRFLOW.md) pour la mise en production avec Docker.
