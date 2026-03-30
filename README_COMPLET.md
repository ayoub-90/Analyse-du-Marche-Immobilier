# 🏠 Analyse du Marché Immobilier Marocain — Guide Complet

> **Projet** : Pipeline de scraping, traitement, ML et visualisation du marché immobilier marocain  
> **Sources** : Avito.ma + Mubawab.ma  
> **Stack** : Python · Selenium · Pandas · Scikit-learn · XGBoost · Streamlit · Apache Airflow · Docker · PostgreSQL

---

## 📁 Structure du Projet

```
Analyse-du-Marche-Immobilier/
│
├── 📂 src/
│   ├── scrappers/
│   │   ├── avito_scraper.py        ← Scraper Avito
│   │   ├── mubawab_scraper.py      ← Scraper Mubawab
│   │   └── Run-scrapers.py         ← Orchestrateur parallèle
│   ├── processing/
│   │   └── data_combiner.py        ← Fusion + nettoyage
│   └── cleaning/
│       └── ml_pipeline.py          ← Pipeline ML 7 étapes
│
├── 📂 notebooks/
│   ├── 01_EDA_Immobilier.ipynb     ← Analyse exploratoire
│   ├── 02_ML_Pipeline.ipynb        ← Pipeline pas-à-pas
│   └── 03_Model_Training.ipynb     ← Entraînement modèles
│
├── 📂 data/
│   ├── raw/avito/                  ← CSV bruts Avito
│   ├── raw/mubawab/                ← CSV bruts Mubawab
│   ├── processed/                  ← CSV combinés
│   └── final/                      ← Datasets ML + modèles
│
├── 📂 sql/
│   ├── schema/create_tables.sql    ← Schéma PostgreSQL
│   └── queries/analytics.sql      ← Requêtes analytiques
│
├── 📂 reports/
│   └── dashboard.py                ← Dashboard Streamlit
│
├── 📂 airflow/dags/
│   └── immobilier_scraping_dag.py  ← DAG quotidien Airflow
│
├── 📂 docs/
│   ├── 01_SCRAPING.md
│   ├── 02_DATA_COMBINER.md
│   ├── 03_ML_PIPELINE.md
│   ├── 04_ML_MODELS.md
│   └── 05_AIRFLOW.md
│
├── docker-compose.yml              ← Infrastructure Docker
├── requirements.txt                ← Dépendances Python
└── .env                            ← Variables d'environnement
```

---

## ⚡ Démarrage Rapide (Mode Test)

### Prérequis
```bash
# Python 3.12+
python --version

# Installer les dépendances
pip install -r requirements.txt

# Google Chrome doit être installé
```

### Étape 1 — Scraping test (2 pages)
```bash
python src/scrappers/avito_scraper.py
python src/scrappers/mubawab_scraper.py
```

### Étape 2 — Combiner les données
```bash
python src/processing/data_combiner.py
```

### Étape 3 — Pipeline ML
```bash
python src/cleaning/ml_pipeline.py
```

### Étape 4 — Dashboard
```bash
pip install streamlit plotly
streamlit run reports/dashboard.py
# Ouvre automatiquement : http://localhost:8501
```

### Étape 5 — Notebooks (optionnel)
```bash
jupyter notebook
# Exécuter dans l'ordre : 01_EDA → 02_ML_Pipeline → 03_Model_Training
```

---

## 🔁 Lancer TOUT Automatiquement (Script)

```bash
# Windows — Tout lancer en séquence
python src/scrappers/avito_scraper.py && ^
python src/scrappers/mubawab_scraper.py && ^
python src/processing/data_combiner.py && ^
python src/cleaning/ml_pipeline.py && ^
streamlit run reports/dashboard.py
```

```bash
# Ou via Makefile
make scrape-all    # Scraping parallèle Avito + Mubawab
make combine       # Combinaison des données
make pipeline      # Pipeline ML
make dashboard     # Lance le dashboard
```

---

## 🚀 Mode Production (Automatisation Airflow)

### Lancer l'infrastructure complète
```bash
# Démarrer Docker (Airflow + PostgreSQL)
docker compose up -d

# Vérifier les services
docker compose ps
```

### Interface Airflow
```
URL      : http://localhost:8080
Login    : airflow / airflow
```

**Activer le DAG** `immobilier_scraping_dag` → s'exécute automatiquement tous les jours à 02h00

### Base de données PostgreSQL
```
Host     : localhost
Port     : 5433
Database : immobilier_maroc
User     : immobilier
Password : immobilier123
```

---

## 🗃️ SQL — Connexion Power BI / Tableau

### Option A : Via CSV (plus simple)
1. Ouvrir Power BI Desktop
2. **Obtenir des données** → Texte/CSV
3. Sélectionner `data/processed/immobilier_maroc_*.csv`
4. Charger → créer les visuels

### Option B : Via PostgreSQL (production)
1. **Obtenir des données** → Base de données → PostgreSQL
2. Serveur : `localhost:5433`
3. Base de données : `immobilier_maroc`
4. Utiliser les vues de `sql/queries/analytics.sql`

---

## 🤖 Modèles ML Disponibles

| Modèle | Fichier | Description |
|--------|---------|-------------|
| Meilleur modèle | `data/final/best_model.pkl` | Auto-sélectionné (R² max) |
| Scaler | `data/final/scaler.pkl` | Pour normaliser nouvelles données |
| Encoders | `data/final/encoders.pkl` | Pour encoder categorielles |
| Métriques | `data/final/model_results.json` | R², MAE, RMSE de tous les modèles |

---

## 📚 Documentation Détaillée

| Doc | Contenu |
|-----|---------|
| [`docs/01_SCRAPING.md`](docs/01_SCRAPING.md) | Architecture, configuration, troubleshooting scrapers |
| [`docs/02_DATA_COMBINER.md`](docs/02_DATA_COMBINER.md) | Flux de combinaison, schéma unifié |
| [`docs/03_ML_PIPELINE.md`](docs/03_ML_PIPELINE.md) | 7 étapes du pipeline, features, output |
| [`docs/04_ML_MODELS.md`](docs/04_ML_MODELS.md) | Modèles, métriques, feature importance, prédiction |
| [`docs/05_AIRFLOW.md`](docs/05_AIRFLOW.md) | Docker, DAG, monitoring, PostgreSQL |

---

## 🔧 Configuration des Pages Scrapées

| Paramètre | Fichier | Valeur Test | Valeur Production |
|-----------|---------|-------------|------------------|
| Pages Avito | `avito_scraper.py` → `main()` | `max_pages=2` | `max_pages=50` |
| Pages Mubawab | `mubawab_scraper.py` → `main()` | `max_pages=2` | `max_pages=50` |
| Chrome version | Tous scrapers | `version_main=145` | Adapter à votre Chrome |

---

## ⚠️ Notes Importantes

> 1. **Dataset taille** : Avec 70 records (test batch), les modèles ML sont indicatifs. Pour la production, scraper minimum 500-1000 annonces.
> 2. **Chrome version** : `version_main=145` est fixé pour Chrome v145. Adapter si vous avez une autre version.
> 3. **Airflow et Docker** sont uniquement nécessaires pour l'automatisation quotidienne — pas pour le mode manuel.
> 4. **Power BI / Tableau** peuvent se connecter soit aux CSV dans `data/processed/` soit à PostgreSQL via `sql/queries/analytics.sql`.
