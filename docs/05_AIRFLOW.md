# 🌊 Guide — Apache Airflow & Docker

## Vue d'ensemble

Apache Airflow orchestre l'**exécution automatique quotidienne** du pipeline complet :

```
[Scraping Avito] ──┐
                   ├──→ [Combinaison] ──→ [ML Pipeline] ──→ [Notifications]
[Scraping Mubawab]─┘
```

**Schedule :** Tous les jours à **02h00** (heure locale)

---

## 📁 Fichiers

```
airflow/
├── dags/
│   └── immobilier_scraping_dag.py   ← DAG principal Airflow
├── logs/                            ← Logs d'exécution Airflow
└── plugins/                         ← Extensions (vide pour l'instant)

docker-compose.yml                   ← Infrastructure complète
.env                                 ← Variables d'environnement
```

---

## 🐳 Architecture Docker

```yaml
Services déployés :
┌─────────────────────────────────────────────┐
│  postgres          (port 5432)               │  ← Airflow metadata DB
│  postgres-data     (port 5433)               │  ← Données immobilier
│  airflow-webserver (port 8080) ←─────────────│──── Interface Web
│  airflow-scheduler                           │  ← Exécute les DAGs
│  airflow-init                                │  ← Initialisation
└─────────────────────────────────────────────┘
```

---

## 🚀 Démarrage

### 1. Prérequis
```bash
# Vérifier Docker installé
docker --version
docker compose version

# Vérifier le fichier .env
cat .env
# AIRFLOW_UID=50000
```

### 2. Lancer l'infrastructure
```bash
# Démarrer tous les services en arrière-plan
docker compose up -d

# Vérifier que tout tourne
docker compose ps
```

### 3. Initialiser la base de données SQL
```bash
# Se connecter à la base de données immobilier
docker compose exec postgres-data psql -U immobilier -d immobilier_maroc

# Dans psql, exécuter le schéma :
\i /sql/schema/create_tables.sql
\q
```

### 4. Accéder à l'interface Airflow
```
URL      : http://localhost:8080
Username : airflow
Password : airflow
```

### 5. Activer le DAG
Dans l'interface Airflow :
1. Naviguer vers **DAGs** → `immobilier_scraping_dag`
2. Activer le toggle **ON**
3. Le DAG s'exécutera automatiquement à 02h00

---

## 📋 Structure du DAG

```python
# immobilier_scraping_dag.py — Tâches définies :

scrape_avito_task       ─┐
                          ├─→ combine_data_task ─→ run_ml_pipeline_task ─→ notify_task
scrape_mubawab_task     ─┘
```

| Tâche | Fonction Python | Description |
|-------|----------------|-------------|
| `scrape_avito` | `scrape_avito_task()` | Lance avito_scraper.py |
| `scrape_mubawab` | `scrape_mubawab_task()` | Lance mubawab_scraper.py |
| `combine_data` | `combine_data_task()` | Fusionne les CSV bruts |
| `load_to_postgres` | `load_to_postgres_task()` | INSERT dans la base SQL |
| `run_ml_pipeline` | `run_ml_pipeline_task()` | Réentraîne le pipeline ML |
| `notify` | `notify_task()` | Log de fin + stats |

---

## ⚙️ Configuration du DAG

```python
# Dans immobilier_scraping_dag.py
default_args = {
    'owner':            'immobilier',
    'retries':          2,              # 2 tentatives en cas d'échec
    'retry_delay':      timedelta(minutes=5),
    'start_date':       datetime(2024, 1, 1),
}

dag = DAG(
    'immobilier_scraping_dag',
    schedule_interval='0 2 * * *',     # Tous les jours à 02h00
    catchup=False,                     # Pas de retard historique
)
```

---

## 📊 Monitoring

### Logs en temps réel
```bash
# Logs du scheduler
docker compose logs -f airflow-scheduler

# Logs du webserver
docker compose logs -f airflow-webserver
```

### Interface Web
- **DAG Runs** : Historique des exécutions
- **Task Logs** : Logs détaillés par tâche
- **Graph View** : Visualisation du DAG

---

## 🔧 Commandes Utiles

```bash
# Arrêter tous les services
docker compose down

# Arrêter et supprimer les volumes (reset complet)
docker compose down -v

# Déclencher le DAG manuellement
docker compose exec airflow-webserver airflow dags trigger immobilier_scraping_dag

# Lister les dernières exécutions
docker compose exec airflow-webserver airflow dags list-runs -d immobilier_scraping_dag

# Vérifier la base de données
docker compose exec postgres-data psql -U immobilier -d immobilier_maroc \
    -c "SELECT COUNT(*), source FROM annonces GROUP BY source;"
```

---

## 🗄️ Base de Données PostgreSQL

### Connexion depuis l'extérieur
```
Host     : localhost
Port     : 5433
Database : immobilier_maroc
User     : immobilier
Password : immobilier123
```

### Connexion depuis Power BI / Tableau
```
Server   : localhost:5433
Database : immobilier_maroc
Auth     : Username / Password
```

### Requêtes Analytics
Voir `sql/queries/analytics.sql` pour les requêtes prêtes à l'emploi.

---

## ⚠️ Problèmes Courants

| Problème | Solution |
|----------|----------|
| `Port 8080 already in use` | `docker compose down` puis relancer |
| `Airflow scheduler not starting` | Vérifier `AIRFLOW_UID` dans `.env` |
| `Chrome not found in container` | Le DAG lance les scrapers en sous-processus qui trouvent Chrome |
| `DAG not visible` | Attendre 30s, puis actualiser l'interface |
