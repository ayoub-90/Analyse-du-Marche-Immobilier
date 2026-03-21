"""
DAG Apache Airflow - Pipeline Scraping Immobilier Maroc
Orchestre: Scraping (Avito + Mubawab) → Nettoyage → Combinaison → Stats
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import sys
import os

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# =============================================================================
# CONFIGURATION
# =============================================================================

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email': ['elharemayoub1@gmail.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'immobilier_maroc_pipeline',
    default_args=default_args,
    description='Pipeline complet scraping immobilier Maroc',
    schedule_interval='0 2 * * *',  # Tous les jours à 2h du matin
    start_date=days_ago(1),
    catchup=False,
    tags=['scraping', 'immobilier', 'production'],
)


# =============================================================================
# TÂCHES
# =============================================================================

def scrape_avito_task(**context):
    """Tâche 1: Scraper Avito"""
    from scrapers.avito_scraper import AvitoScraper
    
    print("🔵 Démarrage scraping Avito...")
    
    scraper = AvitoScraper(max_pages=20)  # Production: 20 pages
    df = scraper.scrape()
    
    # Passer le chemin du fichier à la prochaine tâche
    import glob
    avito_files = glob.glob("data/raw/avito/avito_*.csv")
    latest = max(avito_files, key=os.path.getctime)
    
    context['task_instance'].xcom_push(key='avito_file', value=latest)
    context['task_instance'].xcom_push(key='avito_count', value=len(df))
    
    print(f"✅ Avito terminé: {len(df)} annonces → {latest}")
    return latest


def scrape_mubawab_task(**context):
    """Tâche 2: Scraper Mubawab"""
    from scrapers.mubawab_scraper import MubawabScraper
    
    print("🔴 Démarrage scraping Mubawab...")
    
    scraper = MubawabScraper(max_pages=20)
    df = scraper.scrape()
    
    import glob
    mubawab_files = glob.glob("data/raw/mubawab/mubawab_*.csv")
    latest = max(mubawab_files, key=os.path.getctime)
    
    context['task_instance'].xcom_push(key='mubawab_file', value=latest)
    context['task_instance'].xcom_push(key='mubawab_count', value=len(df))
    
    print(f"✅ Mubawab terminé: {len(df)} annonces → {latest}")
    return latest


def validate_data_task(**context):
    """Tâche 3: Valider les données scrapées"""
    import pandas as pd
    
    ti = context['task_instance']
    avito_file = ti.xcom_pull(key='avito_file', task_ids='scrape_avito')
    mubawab_file = ti.xcom_pull(key='mubawab_file', task_ids='scrape_mubawab')
    
    print("✅ Validation des données...")
    
    errors = []
    
    # Vérifier Avito
    if avito_file and os.path.exists(avito_file):
        df = pd.read_csv(avito_file)
        print(f"  Avito: {len(df)} annonces")
        
        if len(df) < 10:
            errors.append(f"Avito: seulement {len(df)} annonces")
        
        prix_valides = df['prix'].notna().sum()
        pct = (prix_valides / len(df)) * 100
        if pct < 50:
            errors.append(f"Avito: {pct:.1f}% annonces avec prix")
    else:
        errors.append("Avito: fichier manquant")
    
    # Vérifier Mubawab
    if mubawab_file and os.path.exists(mubawab_file):
        df = pd.read_csv(mubawab_file)
        print(f"  Mubawab: {len(df)} annonces")
        
        if len(df) < 10:
            errors.append(f"Mubawab: seulement {len(df)} annonces")
        
        prix_valides = df['prix'].notna().sum()
        pct = (prix_valides / len(df)) * 100
        if pct < 50:
            errors.append(f"Mubawab: {pct:.1f}% annonces avec prix")
    else:
        errors.append("Mubawab: fichier manquant")
    
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
    
    print("🔄 Combinaison des données...")
    
    combiner = DataCombiner()
    df = combiner.combine()
    
    # Passer le chemin du fichier combiné
    import glob
    combined_files = glob.glob("data/processed/immobilier_maroc_*.csv")
    latest = max(combined_files, key=os.path.getctime)
    
    context['task_instance'].xcom_push(key='combined_file', value=latest)
    context['task_instance'].xcom_push(key='combined_count', value=len(df))
    
    print(f"✅ Combinaison terminée: {len(df)} annonces → {latest}")
    return latest


def generate_stats_task(**context):
    """Tâche 5: Générer statistiques"""
    import pandas as pd
    import json
    
    ti = context['task_instance']
    combined_file = ti.xcom_pull(key='combined_file', task_ids='combine_data')
    
    df = pd.read_csv(combined_file)
    
    stats = {
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total_annonces': int(len(df)),
        'avito': int(len(df[df['source'] == 'Avito'])),
        'mubawab': int(len(df[df['source'] == 'Mubawab'])),
        'types_biens': df['type_bien'].value_counts().to_dict(),
        'villes_top5': df['ville'].value_counts().head(5).to_dict(),
    }
    
    if 'prix' in df.columns:
        stats['prix_moyen'] = float(df['prix'].mean())
        stats['prix_median'] = float(df['prix'].median())
    
    print("\n📊 STATISTIQUES:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    # Sauvegarder
    os.makedirs("data/stats", exist_ok=True)
    stats_file = f"data/stats/stats_{datetime.now().strftime('%Y%m%d')}.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    return stats


def send_notification_task(**context):
    """Tâche 6: Envoyer notification"""
    ti = context['task_instance']
    
    avito_count = ti.xcom_pull(key='avito_count', task_ids='scrape_avito')
    mubawab_count = ti.xcom_pull(key='mubawab_count', task_ids='scrape_mubawab')
    combined_count = ti.xcom_pull(key='combined_count', task_ids='combine_data')
    
    message = f"""
    ✅ Pipeline Immobilier Maroc - Terminé avec succès
    
    📊 Résultats:
    - Avito: {avito_count} annonces
    - Mubawab: {mubawab_count} annonces
    - Total après nettoyage: {combined_count} annonces
    
    Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    print(message)
    
    # Ici, vous pouvez ajouter l'envoi d'email ou Slack
    # send_email(message)
    # send_slack(message)
    
    return message

def load_to_postgres_task(**context):
    import pandas as pd
    import psycopg2
    from psycopg2.extras import execute_values

    ti = context['task_instance']
    combined_file = ti.xcom_pull(key='combined_file', task_ids='combine_data')

    df = pd.read_csv(combined_file)

    conn = psycopg2.connect(
        host="postgres-data",
        port=5432,
        dbname="immobilier_maroc",
        user="immobilier",
        password="immobilier123"
    )

    columns = [
        'id_annonce','source','url','titre','prix','ville','type_bien',
        'surface_m2','nb_chambres','nb_salles_bain','etage',
        'parking','ascenseur','balcon','piscine','jardin',
        'description','date_scraping'
    ]

    # Only keep columns that exist in the dataframe
    cols = [c for c in columns if c in df.columns]
    records = df[cols].where(pd.notnull(df[cols]), None).values.tolist()

    with conn.cursor() as cur:
        execute_values(cur, f"""
            INSERT INTO annonces ({','.join(cols)})
            VALUES %s
            ON CONFLICT (url) DO UPDATE SET
                prix       = EXCLUDED.prix,
                updated_at = NOW()
        """, records)
    
    conn.commit()
    conn.close()

    print(f"✅ {len(records)} annonces insérées/mises à jour en base")


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

# Tâche de nettoyage (optionnelle)
task_cleanup = BashOperator(
    task_id='cleanup_old_files',
    bash_command='''
        # Supprimer fichiers de plus de 30 jours
        find data/raw/avito/ -name "*.csv" -mtime +30 -delete
        find data/raw/mubawab/ -name "*.csv" -mtime +30 -delete
        echo "Nettoyage terminé"
    ''',
    dag=dag,
)


# =============================================================================
# DÉPENDANCES (FLOW DU PIPELINE)
# =============================================================================

# Phase 1: Scraping en parallèle
[task_scrape_avito, task_scrape_mubawab] >> task_validate

# Phase 2: Traitement séquentiel
task_validate >> task_combine >> task_stats >> task_notify >> task_cleanup


# =============================================================================
# DOCUMENTATION DU DAG
# =============================================================================

dag.doc_md = """
# Pipeline Scraping Immobilier Maroc

## Description
Ce DAG orchestre le scraping quotidien des sites Avito et Mubawab, combine les données,
et génère des statistiques.

## Flow
1. **Scraping** : Avito et Mubawab en parallèle (20 pages chacun)
2. **Validation** : Vérification qualité des données
3. **Combinaison** : Fusion et nettoyage des 2 sources
4. **Statistiques** : Génération des métriques
5. **Notification** : Alerte de fin de pipeline
6. **Cleanup** : Suppression des vieux fichiers

## Configuration
- **Schedule** : Tous les jours à 2h du matin
- **Retries** : 2 tentatives en cas d'échec
- **Timeout** : 5 minutes entre chaque retry

## Outputs
- `data/raw/avito/` : Données brutes Avito
- `data/raw/mubawab/` : Données brutes Mubawab
- `data/processed/` : Dataset combiné final
- `data/stats/` : Statistiques quotidiennes

## Monitoring
Dashboard Airflow: http://localhost:8080
"""