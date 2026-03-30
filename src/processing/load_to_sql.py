#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
load_to_sql.py — Pipeline de Chargement en Étoile (Star Schema)
================================================================
Gère l'injection micro-batch :
1. Upsert des Dimensions (Source, Type, Localisation)
2. Mapping des IDs
3. Upsert de la Table de Faits (fact_annonces)
"""

import os
import glob
import logging
import argparse
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    "host":     os.getenv("PG_HOST",     "localhost"),
    "port":     int(os.getenv("PG_PORT", "5433")),
    "dbname":   os.getenv("PG_DB",       "immobilier_maroc"),
    "user":     os.getenv("PG_USER",     "immobilier"),
    "password": os.getenv("PG_PASSWORD", "immobilier123")
}

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PROCESSED = os.path.join(ROOT, "data", "processed")

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(message)s")
logger = logging.getLogger(__name__)

def get_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        raise ConnectionError(f"❌ Connexion PostgreSQL impossible: {e}")

def get_dim_map(conn, table, key_cols, val_col):
    with conn.cursor() as cur:
        cur.execute(f"SELECT {','.join(key_cols)}, {val_col} FROM {table}")
        rows = cur.fetchall()
        if len(key_cols) == 1:
            return {row[0]: row[1] for row in rows}
        else:
            return {tuple(row[:-1]): row[-1] for row in rows}

def load_csv_to_sql(filepath: str = None):
    if filepath and os.path.exists(filepath):
        latest = filepath
        logger.info(f"📄 Fichier explicite : {latest}")
    else:
        # fallback to glob if no path provided
        files = glob.glob(os.path.join(DATA_PROCESSED, "immobilier_maroc_*.csv"))
        if not files:
            logger.warning("⚠️ Aucun CSV trouvé.")
            return
        latest = max(files, key=os.path.getctime)
        logger.info(f"📄 Dernier fichier (glob) : {latest}")
    df = pd.read_csv(latest)

    if df.empty:
        logger.warning("Le CSV est vide.")
        return

    # Nettoyage de base
    df["prix"] = pd.to_numeric(df["prix"].replace(r'[^\d.]', '', regex=True), errors="coerce")
    if "surface_m2" in df.columns:
        df["surface_m2"] = pd.to_numeric(df["surface_m2"], errors="coerce")
        df.loc[df["surface_m2"] > 50000, "surface_m2"] = None

    for col in ["parking", "ascenseur", "balcon", "piscine", "jardin"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    if 'quartier' not in df.columns:
        df['quartier'] = 'Inconnu'
        
    df['quartier'] = df['quartier'].fillna('Inconnu')
    df['ville'] = df['ville'].fillna('Inconnu')
    df['source'] = df['source'].fillna('Inconnu')
    df['type_bien'] = df['type_bien'].fillna('Appartement')

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1. DIMENSION SOURCE
            sources = df['source'].unique()
            execute_values(cur, "INSERT INTO dim_source (site_source) VALUES %s ON CONFLICT (site_source) DO NOTHING", [(x,) for x in sources])
            conn.commit()
            dim_source_map = get_dim_map(conn, 'dim_source', ['site_source'], 'id_source')

            # 2. DIMENSION TYPE DE BIEN
            types = df['type_bien'].unique()
            execute_values(cur, "INSERT INTO dim_type_bien (type_bien) VALUES %s ON CONFLICT (type_bien) DO NOTHING", [(x,) for x in types])
            conn.commit()
            dim_type_map = get_dim_map(conn, 'dim_type_bien', ['type_bien'], 'id_type')

            # 3. DIMENSION LOCALISATION
            locs = df[['ville', 'quartier']].drop_duplicates().values.tolist()
            execute_values(cur, "INSERT INTO dim_localisation (ville, quartier) VALUES %s ON CONFLICT (ville, quartier) DO NOTHING", locs)
            conn.commit()
            dim_loc_map = get_dim_map(conn, 'dim_localisation', ['ville', 'quartier'], 'id_loc')

            # Mapping des Foreign Keys
            df['id_source'] = df['source'].map(dim_source_map)
            df['id_type'] = df['type_bien'].map(dim_type_map)
            df['id_loc'] = df.apply(lambda row: dim_loc_map.get((row['ville'], row['quartier'])), axis=1)

            # 4. TABLE DE FAITS
            fact_cols = [
                'id_annonce', 'url', 'titre', 'prix', 'surface_m2', 
                'nb_chambres', 'nb_salles_bain', 'etage', 'parking', 
                'ascenseur', 'balcon', 'piscine', 'jardin', 'description', 
                'date_scraping', 'id_loc', 'id_type', 'id_source'
            ]
            final_cols = [c for c in fact_cols if c in df.columns]

            df_facts = df[final_cols].where(pd.notnull(df), None)
            records = df_facts.values.tolist()

            insert_query = f"""
                INSERT INTO fact_annonces ({','.join(final_cols)})
                VALUES %s
                ON CONFLICT (url) DO UPDATE SET
                    prix = EXCLUDED.prix,
                    surface_m2 = EXCLUDED.surface_m2,
                    updated_at = CURRENT_TIMESTAMP
            """
            execute_values(cur, insert_query, records)
            conn.commit()
            
            logger.info(f"✅ {len(records)} lignes injectées dans la table des faits (fact_annonces)")

            # Stats
            cur.execute("SELECT COUNT(*) FROM fact_annonces")
            logger.info(f"📊 Total base de données : {cur.fetchone()[0]} annonces")

    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", action="store_true", help="Forcer le chargement", default=True)
    args = parser.parse_args()
    if args.load:
        load_csv_to_sql()
