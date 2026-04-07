# 🕷️ Guide — Ingestion de Données (Micro-Batching)

## Vue d'ensemble

Le projet utilise un système d'ingestion **incrémental et stateful**. Contrairement à un scraping classique, chaque cycle ne récupère qu'un petit volume de données, assurant une fraîcheur continue sans surcharger les serveurs sources.

| Portail | Méthode | Capture par Cycle | Fréquence |
|---------|---------|-------------------|-----------|
| **Avito** | Selenium (Stateful) | 20 annonces | 15 minutes |
| **Mubawab** | Selenium (Stateful) | 20 annonces | 15 minutes |

---

## 🔧 Architecture de Scraping

### 1. Gestion de l'État (State Persistence)
Chaque scraper enregistre la dernière page traitée dans un fichier JSON local :
*   `data/state/avito_state.json`
*   `data/state/mubawab_state.json`

Au prochain lancement, le scraper lit ce fichier et reprend exactement là où il s'est arrêté.

### 2. Algorithme de Micro-Batching
```python
# Logique simplifiée
target = 20
count = 0
while count < target:
    items = scrape_page(current_page)
    for item in items:
        if is_valid(item):
            save(item)
            count += 1
    current_page += 1
save_state(current_page)
```

---

## 📁 Structure du Code

```
src/scrappers/
├── avito_scraper.py      ← Logique Avito (target_count=20)
├── mubawab_scraper.py    ← Logique Mubawab (target_count=20)
└── driver_setup.py       ← Configuration Chrome (Docker vs Local)
```

### Modes de Navigation
*   **Mode Docker** : Utilise `chromium-browser` en mode headless (optimisé pour le serveur).
*   **Mode Local** : Utilise `undetected-chromedriver` pour contourner les protections bots en développement.

---

## 📂 Format de Sortie (Raw Data)

Les fichiers sont stockés dans `data/raw/{source}/`.

| Colonne | Description |
|---------|-------------|
| `url` | Identifiant unique (Clé d'Upsert SQL) |
| `prix` | Prix converti en float (MAD) |
| `surface_m2` | Surface nettoyée |
| `equipements` | Parking, ascenseur, etc. (0/1) |

---

## 🔄 Intégration Pipeline
Le scraping est la première étape du DAG Airflow. Il est exécuté de manière **séquentielle** pour garantir la stabilité des ressources Chrome dans le container Docker.

> Suivant : Voir [`05_AIRFLOW.md`](05_AIRFLOW.md) pour l'orchestration.

