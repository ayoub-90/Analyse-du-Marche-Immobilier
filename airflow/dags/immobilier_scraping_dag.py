"""
DAG Apache Airflow - Pipeline Scraping Immobilier Maroc
Orchestre: Scraping (Avito + Mubawab) → Nettoyage → Combinaison → ML → Stats
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys
import os

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, '/opt/airflow/src')

# =============================================================================
# CONFIGURATION
# =============================================================================

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email': ['elharemayoub1@gmail.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'immobilier_maroc_pipeline',
    default_args=default_args,
    description='Pipeline continu scraping immobilier Maroc (Micro-batch)',
    schedule_interval='*/15 * * * *',   # Toutes les 15 minutes
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    concurrency=2,
    tags=['scraping', 'immobilier', 'production', 'micro-batch'],
)


# =============================================================================
# TÂCHES
# =============================================================================

def scrape_avito_task(**context):
    """Tâche 1: Scraper Avito"""
    from scrappers.avito_scraper import AvitoScraper
    import glob

    print("🔵 Démarrage scraping Avito...")
    scraper = AvitoScraper(target_count=20)
    df      = scraper.scrape()

    avito_files = glob.glob("data/raw/avito/avito_*.csv")
    latest      = max(avito_files, key=os.path.getctime)

    context['task_instance'].xcom_push(key='avito_file',  value=latest)
    context['task_instance'].xcom_push(key='avito_count', value=len(df))
    print(f"✅ Avito terminé: {len(df)} annonces → {latest}")
    return latest


def scrape_mubawab_task(**context):
    """Tâche 2: Scraper Mubawab"""
    from scrappers.mubawab_scraper import MubawabScraper
    import glob

    print("🔴 Démarrage scraping Mubawab...")
    scraper = MubawabScraper(target_count=20)
    df      = scraper.scrape()

    mubawab_files = glob.glob("data/raw/mubawab/mubawab_*.csv")
    latest        = max(mubawab_files, key=os.path.getctime)

    context['task_instance'].xcom_push(key='mubawab_file',  value=latest)
    context['task_instance'].xcom_push(key='mubawab_count', value=len(df))
    print(f"✅ Mubawab terminé: {len(df)} annonces → {latest}")
    return latest


def validate_data_task(**context):
    """Tâche 3: Valider les données scrapées"""
    import pandas as pd

    ti           = context['task_instance']
    avito_file   = ti.xcom_pull(key='avito_file',   task_ids='scrape_avito')
    mubawab_file = ti.xcom_pull(key='mubawab_file', task_ids='scrape_mubawab')

    print("✅ Validation des données...")
    errors = []

    for name, filepath in [('Avito', avito_file), ('Mubawab', mubawab_file)]:
        if filepath and os.path.exists(filepath):
            df = pd.read_csv(filepath)
            print(f"  {name}: {len(df)} annonces")
            if len(df) < 10:
                errors.append(f"{name}: seulement {len(df)} annonces")
            pct = df['prix'].notna().sum() / len(df) * 100
            if pct < 50:
                errors.append(f"{name}: {pct:.1f}% annonces avec prix")
        else:
            errors.append(f"{name}: fichier manquant")

    if errors:
        print("⚠️ AVERTISSEMENTS:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("✅ Validation OK")

    return {'avito': avito_file, 'mubawab': mubawab_file, 'errors': errors}


def combine_data_task(**context):
    """Tâche 4: Combiner les données"""
    from processing.data_combiner import DataCombiner
    import glob

    print("🔄 Combinaison des données...")
    combiner = DataCombiner()
    df       = combiner.combine()

    combined_files = glob.glob("data/processed/immobilier_maroc_*.csv")
    latest         = max(combined_files, key=os.path.getctime)

    context['task_instance'].xcom_push(key='combined_file',  value=latest)
    context['task_instance'].xcom_push(key='combined_count', value=len(df))
    print(f"✅ Combinaison terminée: {len(df)} annonces → {latest}")
    return latest


def generate_stats_task(**context):
    """Tâche 5: Générer statistiques"""
    import pandas as pd
    import json

    ti            = context['task_instance']
    combined_file = ti.xcom_pull(key='combined_file', task_ids='combine_data')
    df            = pd.read_csv(combined_file)

    stats = {
        'date':            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total_annonces':  int(len(df)),
        'avito':           int(len(df[df['source'] == 'Avito'])),
        'mubawab':         int(len(df[df['source'] == 'Mubawab'])),
        'types_biens':     df['type_bien'].value_counts().to_dict(),
        'villes_top5':     df['ville'].value_counts().head(5).to_dict(),
    }
    if 'prix' in df.columns:
        stats['prix_moyen']  = float(df['prix'].mean())
        stats['prix_median'] = float(df['prix'].median())

    print("\n📊 STATISTIQUES:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    os.makedirs("data/stats", exist_ok=True)
    stats_file = f"data/stats/stats_{datetime.now().strftime('%Y%m%d')}.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    return stats


def send_notification_task(**context):
    """Tâche 6: Envoyer notification"""
    ti             = context['task_instance']
    avito_count    = ti.xcom_pull(key='avito_count',    task_ids='scrape_avito')
    mubawab_count  = ti.xcom_pull(key='mubawab_count',  task_ids='scrape_mubawab')
    combined_count = ti.xcom_pull(key='combined_count', task_ids='combine_data')

    # Pull ML metrics pushed by the ML task
    ml_report = ti.xcom_pull(key='ml_report', task_ids='ml_pipeline') or {}
    ml_step   = ml_report.get('steps', {}).get('step8_model', {})
    r2        = ml_step.get('r2_score', 'N/A')
    rmse      = ml_step.get('rmse',     'N/A')
    epochs    = ml_step.get('n_epochs', 'N/A')

    message = f"""
✅ Pipeline Immobilier Maroc - Terminé avec succès

📊 Scraping:
  - Avito        : {avito_count} annonces
  - Mubawab      : {mubawab_count} annonces
  - Total nettoyé: {combined_count} annonces

🤖 Modèle ML (RandomForest):
  - Epochs       : {epochs}
  - R² (accuracy): {r2}
  - RMSE (loss)  : {rmse}

📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    print(message)
    # Uncomment to enable:
    # send_email(message)
    # send_slack(message)
    return message


def load_to_postgres_task(**context):
    """Tâche 7: Charger les données dans PostgreSQL (Schéma en Étoile)"""
    from processing.load_to_sql import load_csv_to_sql

    print("🐘 Démarrage de l'insertion dans PostgreSQL (Star Schema)...")
    ti            = context['task_instance']
    combined_file = ti.xcom_pull(key='combined_file', task_ids='combine_data')
    try:
        load_csv_to_sql(filepath=combined_file)
        print("✅ Insertion réussie !")
    except Exception as e:
        print(f"❌ Erreur lors de l'insertion PostgreSQL : {e}")
        raise


def ml_pipeline_task(**context):
    """
    Tâche ML: Lance le pipeline RandomForest avec tracking par epoch.

    - Premier run         → entraînement complet (incremental=False)
    - Runs suivants       → apprentissage incrémental sur les nouvelles lignes
    - Métriques par epoch → table model_epochs (PostgreSQL)
    - Métriques finales   → table model_metrics (PostgreSQL)
    - Prédictions sample  → table predictions (PostgreSQL)
    - Modèle exporté      → data/models/rf_model.pkl + .joblib
    """
    from cleaning.ml_pipeline import MLPipeline
    import os

    MODEL_JL    = os.path.join('data', 'models', 'rf_model.joblib')
    incremental = os.path.exists(MODEL_JL)   # incremental if a trained model exists

    mode = "INCRÉMENTAL" if incremental else "COMPLET"
    print(f"🤖 Démarrage du pipeline ML — mode {mode}...")

    pipeline = MLPipeline()
    report   = pipeline.run(incremental=incremental)

    # Push the full report so notification task can read it
    context['task_instance'].xcom_push(key='ml_report', value=report)

    total_rows = report.get('steps', {}).get('step7_split', {}).get('total_rows', 'N/A')
    r2         = report.get('steps', {}).get('step8_model', {}).get('r2_score',   'N/A')
    rmse       = report.get('steps', {}).get('step8_model', {}).get('rmse',       'N/A')
    n_epochs   = report.get('steps', {}).get('step8_model', {}).get('n_epochs',   'N/A')

    print(f"✅ ML terminé: {total_rows} lignes — R²={r2} — RMSE={rmse} — {n_epochs} epochs")
    return report


# =============================================================================
# DÉFINITION DES TÂCHES AIRFLOW
# =============================================================================

task_scrape_avito = PythonOperator(
    task_id='scrape_avito',
    python_callable=scrape_avito_task,
    dag=dag,
)

task_scrape_mubawab = PythonOperator(
    task_id='scrape_mubawab',
    python_callable=scrape_mubawab_task,
    dag=dag,
)

task_validate = PythonOperator(
    task_id='validate_data',
    python_callable=validate_data_task,
    dag=dag,
)

task_combine = PythonOperator(
    task_id='combine_data',
    python_callable=combine_data_task,
    dag=dag,
)

task_stats = PythonOperator(
    task_id='generate_stats',
    python_callable=generate_stats_task,
    dag=dag,
)

task_notify = PythonOperator(
    task_id='send_notification',
    python_callable=send_notification_task,
    dag=dag,
)

task_load_sql = PythonOperator(
    task_id='load_to_postgres',
    python_callable=load_to_postgres_task,
    dag=dag,
)

task_ml_pipeline = PythonOperator(
    task_id='ml_pipeline',
    python_callable=ml_pipeline_task,
    dag=dag,
)

task_cleanup = BashOperator(
    task_id='cleanup_old_files',
    bash_command='''
        find data/raw/avito/   -name "*.csv" -mtime +30 -delete
        find data/raw/mubawab/ -name "*.csv" -mtime +30 -delete
        echo "Nettoyage terminé"
    ''',
    dag=dag,
)


# =============================================================================
# DÉPENDANCES (FLOW DU PIPELINE)
# =============================================================================

[task_scrape_avito, task_scrape_mubawab] >> task_validate
task_validate >> task_combine >> task_ml_pipeline >> task_load_sql
task_load_sql >> task_stats >> task_notify >> task_cleanup


# =============================================================================
# DOCUMENTATION DU DAG
# =============================================================================

dag.doc_md = """
# Pipeline Scraping Immobilier Maroc

## Description
Ce DAG orchestre le scraping micro-batch (toutes les 15 min) des sites Avito
et Mubawab, combine les données, entraîne/met à jour le modèle RandomForest,
puis pousse toutes les métriques vers PostgreSQL.

## Flow
1. **Scraping**       : Avito + Mubawab en parallèle (20 annonces chacun)
2. **Validation**     : Vérification qualité (minimum 10 lignes, >50% prix)
3. **Combinaison**    : Fusion et nettoyage des 2 sources
4. **ML Pipeline**    : RandomForest — 10 epochs × 10 arbres
   - Epoch metrics (R² + RMSE) → table `model_epochs`
   - Métriques finales         → table `model_metrics`
   - Prédictions (500 samples) → table `predictions`
   - Modèle exporté            → `data/models/rf_model.pkl` + `.joblib`
   - 1er run = complet / suivants = incrémental (nouvelles lignes uniquement)
5. **Load SQL**       : Données brutes → schéma en étoile PostgreSQL
6. **Statistiques**   : JSON quotidien dans `data/stats/`
7. **Notification**   : Résumé scraping + métriques ML
8. **Cleanup**        : Suppression fichiers CSV > 30 jours

## Tables PostgreSQL
| Table            | Contenu                                      |
|------------------|----------------------------------------------|
| model_epochs     | R² + RMSE par epoch (courbe d'apprentissage) |
| model_metrics    | Métriques finales par run                    |
| predictions      | 500 prédictions test par run                 |

## Configuration
- **Schedule** : Toutes les 15 minutes
- **Retries**  : 2 tentatives / 5 min entre chaque
- **Epochs**   : 10 (configurable via TREES_PER_EPOCH / TOTAL_TREES)

## Monitoring
Dashboard Airflow : http://localhost:8080
"""