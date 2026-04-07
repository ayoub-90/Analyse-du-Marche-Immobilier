# 🌊 Guide — Orchestration Airflow (Micro-Batching)

## Vue d'ensemble

Apache Airflow orchestre l'**exécution continue** du pipeline. Le système ne fonctionne plus par gros "batch" quotidien, mais par petits cycles de 15 minutes pour garantir une donnée toujours fraîche.

**Schedule :** `*/15 * * * *` (Toutes les 15 minutes)

---

## 🏗️ Flux de Données Séquentiel

Pour optimiser les ressources (CPU/RAM) du container Docker, les tâches s'exécutent de manière strictement séquentielle :

```
[Scraper Avito] 
       ↓
[Scraper Mubawab]
       ↓
[Validation & Combiner]
       ↓
[ML Pipeline & Metrics]
       ↓
[Chargement SQL Star Schema]
```

---

## 🐳 Services Docker

| Service | Port | Rôle |
|---------|------|------|
| `airflow-webserver` | 8081 | Interface de monitoring |
| `postgres-data` | 5433 | Base de données métier (Star Schema) |
| `postgres` | 5432 | Base de données interne Airflow |

---

## 🚀 Commandes d'Exploitation

### Gestion des Containers
```bash
# Lancer le pipeline complet
docker compose up -d

# Arrêter proprement
docker compose stop

# Voir les logs du scheduler (pour débugger)
docker compose logs -f airflow-scheduler
```

### Vérification de la Base de Données
Depuis votre terminal, vous pouvez vérifier le remplissage des micro-batches :
```bash
docker compose exec postgres-data psql -U immobilier -d immobilier_maroc -c "SELECT source, count(*) FROM fact_annonces GROUP BY source;"
```

---

## 📋 Détails des Tâches (DAG)

| Tâche | Script Source | Action |
|-------|--------------|--------|
| `scrape_avito` | `avito_scraper.py` | Récupère 20 annonces (Incremental) |
| `scrape_mubawab` | `mubawab_scraper.py` | Récupère 20 annonces (Incremental) |
| `combine_data` | `data_combiner.py` | Fusionne et calcule le prix_m2 |
| `ml_pipeline` | `ml_pipeline.py` | Entraîne l'IA et loggue le R² Score |
| `load_to_postgres`| `load_to_sql.py` | Alimente le Star Schema (Facts/Dims) |

---

## ⚠️ Monitoring & Alertes
*   **Interface Web** : Accès sur [http://localhost:8081](http://localhost:8081).
*   **Retries** : Chaque tâche échouée est retentée 2 fois automatiquement avec un délai de 5 minutes.
*   **State Files** : Si le pipeline s'arrête, il reprendra à la page exacte grâce aux fichiers `data/state/*.json`.

> Suivant : Voir [`06_POWERBI_POSTGRESQL.md`](06_POWERBI_POSTGRESQL.md) pour l'analyse.
