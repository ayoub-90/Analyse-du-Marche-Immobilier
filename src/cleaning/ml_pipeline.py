#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML Pipeline - Immobilier Maroc
==============================
Pipeline complet 7 étapes + entraînement RandomForest incrémental.

Fonctionnalités :
  - RandomForestRegressor avec suivi par epoch (batch d'arbres)
  - Accuracy (R²) + Loss (RMSE) enregistrés par epoch => PostgreSQL
  - Métriques finales + prédictions => PostgreSQL
  - Export modèle (.pkl + .joblib)
  - Apprentissage incrémental sur les nouvelles lignes collectées
"""

import os
import glob
import json
import pickle
import logging
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
import psycopg2

from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
_HERE         = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
_LOGS_DIR     = os.path.join(_PROJECT_ROOT, 'logs')
_FINAL_DIR    = os.path.join(_PROJECT_ROOT, 'data', 'final')
_MODEL_DIR    = os.path.join(_PROJECT_ROOT, 'data', 'models')

for d in [_LOGS_DIR, _FINAL_DIR, _MODEL_DIR]:
    os.makedirs(d, exist_ok=True)

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s │ %(levelname)s │ %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(_LOGS_DIR, 'ml_pipeline.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
TARGET           = 'prix'
TEST_SIZE        = 0.20
RANDOM_STATE     = 42
IQR_FACTOR       = 3.0
PRIX_MIN         = 100_000
PRIX_MAX         = 20_000_000
CATEGORICAL_COLS = ['type_bien', 'ville', 'source']
BOOLEAN_COLS     = ['parking', 'ascenseur', 'balcon', 'piscine', 'jardin']
DROP_COLS        = ['id_annonce', 'titre', 'description', 'url',
                    'date_scraping', 'nb_chambres', 'nb_salles_bain', 'etage']

# RandomForest epoch config
# 1 epoch = TREES_PER_EPOCH trees added via warm_start
TOTAL_TREES      = 100   # total estimators at end of training
TREES_PER_EPOCH  = 10    # trees added per epoch  →  10 epochs total

# Model file paths
MODEL_PKL  = os.path.join(_MODEL_DIR, 'rf_model.pkl')
MODEL_JL   = os.path.join(_MODEL_DIR, 'rf_model.joblib')
SEEN_FILE  = os.path.join(_MODEL_DIR, 'seen_indices.json')


# ═══════════════════════════════════════════════════════
# PostgreSQL helpers
# ═══════════════════════════════════════════════════════

def get_pg_conn():
    return psycopg2.connect(
        host    =os.getenv("PG_HOST",     "localhost"),
        port    =int(os.getenv("PG_PORT", "5433")),
        dbname  =os.getenv("PG_DB",       "immobilier_maroc"),
        user    =os.getenv("PG_USER",     "immobilier"),
        password=os.getenv("PG_PASSWORD", "immobilier123")
    )


def pg_ensure_tables(conn):
    """Create all required tables if they don't exist."""
    with conn.cursor() as cur:

        # Final model metrics (one row per full run)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                id                  SERIAL PRIMARY KEY,
                run_at              TIMESTAMP DEFAULT NOW(),
                modele              TEXT,
                r2_score            FLOAT,
                rmse                FLOAT,
                mae                 FLOAT,
                lignes_entrainement INTEGER,
                mode_entrainement   TEXT
            );
        """)

        # Per-epoch training curve: accuracy (R²) + loss (RMSE)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS model_epochs (
                id         SERIAL PRIMARY KEY,
                run_at     TIMESTAMP DEFAULT NOW(),
                modele     TEXT,
                run_mode   TEXT,
                epoch      INTEGER,
                n_trees    INTEGER,
                accuracy   FLOAT,   -- R² on test set at this epoch
                loss       FLOAT    -- RMSE on test set at this epoch
            );
        """)

        # Sample predictions (up to 500 rows per run)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id           SERIAL PRIMARY KEY,
                predicted_at TIMESTAMP DEFAULT NOW(),
                surface_m2   FLOAT,
                ville        TEXT,
                type_bien    TEXT,
                prix_reel    FLOAT,
                prix_predit  FLOAT,
                erreur_abs   FLOAT
            );
        """)
    conn.commit()


def pg_insert_metrics(conn, model_name, r2, rmse, mae, n_train, mode):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO model_metrics
                (modele, r2_score, rmse, mae, lignes_entrainement, mode_entrainement)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (model_name, float(r2), float(rmse), float(mae), int(n_train), mode))
    conn.commit()


def pg_insert_epoch(conn, model_name, run_mode, epoch, n_trees, accuracy, loss):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO model_epochs
                (modele, run_mode, epoch, n_trees, accuracy, loss)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (model_name, run_mode, epoch, n_trees, float(accuracy), float(loss)))
    conn.commit()


def pg_insert_predictions(conn, df_pred):
    with conn.cursor() as cur:
        rows = [
            (
                row.get('surface_m2'),
                row.get('ville'),
                row.get('type_bien'),
                float(row['prix_reel']),
                float(row['prix_predit']),
                float(row['erreur_abs'])
            )
            for _, row in df_pred.iterrows()
        ]
        cur.executemany("""
            INSERT INTO predictions
                (surface_m2, ville, type_bien, prix_reel, prix_predit, erreur_abs)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, rows)
    conn.commit()


# ═══════════════════════════════════════════════════════
# PIPELINE CLASS
# ═══════════════════════════════════════════════════════

class MLPipeline:
    """
    Pipeline séquentiel preprocessing + RandomForest avec tracking par epoch.

    Usage:
        pipeline = MLPipeline()
        pipeline.run()                    # entraînement complet
        pipeline.run(incremental=True)    # apprentissage sur nouvelles lignes
    """

    def __init__(self, data_dir='data/processed', output_dir='data/final'):
        self.data_dir   = os.path.abspath(data_dir)
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        self.df          = None
        self.scaler      = StandardScaler()
        self.encoders    = {}
        self.scaled_cols = []
        self.report      = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'steps': {}
        }

    # ─── Utilities ───────────────────────────────────────────────

    def _log_step(self, step, before, after, details=None):
        dropped = before - after
        pct     = (dropped / before * 100) if before > 0 else 0
        logger.info(f"  ↳ {before} → {after} lignes  ({dropped} supprimées, {pct:.1f}%)")
        self.report['steps'][step] = {
            'rows_before': before, 'rows_after': after, 'dropped': dropped,
            **(details or {})
        }

    def _extract_numeric(self, series):
        return series.astype(str).str.extract(r'(\d+)')[0].astype(float)

    # ─── STEP 1 : Load & Validate ────────────────────────────────

    def step1_load_and_validate(self):
        logger.info("═" * 55)
        logger.info("ÉTAPE 1 │ Chargement & Validation")
        logger.info("═" * 55)

        files = glob.glob(os.path.join(self.data_dir, 'immobilier_maroc_*.csv'))
        if not files:
            raise FileNotFoundError(f"Aucun fichier trouvé dans {self.data_dir}")

        latest = max(files, key=os.path.getctime)
        logger.info(f"  Fichier : {latest}")
        self.df = pd.read_csv(latest)
        before  = len(self.df)

        for col in BOOLEAN_COLS:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0).astype(int)

        self.df['prix'] = pd.to_numeric(self.df['prix'], errors='coerce')
        if 'surface_m2' in self.df.columns:
            self.df['surface_m2'] = pd.to_numeric(self.df['surface_m2'], errors='coerce')

        for col in CATEGORICAL_COLS:
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(str).str.strip().str.title()

        self.df = self.df[self.df['prix'].notna()]
        self._log_step('step1_load', before, len(self.df), {'file': latest})
        logger.info(f"  ✅ {len(self.df)} lignes chargées\n")

    # ─── STEP 2 : Feature Engineering ────────────────────────────

    def step2_feature_engineering(self):
        logger.info("═" * 55)
        logger.info("ÉTAPE 2 │ Feature Engineering")
        logger.info("═" * 55)
        before = len(self.df)

        mask = self.df['surface_m2'].notna() & (self.df['surface_m2'] > 0)
        self.df['prix_m2'] = np.nan
        self.df.loc[mask, 'prix_m2'] = (
            self.df.loc[mask, 'prix'] / self.df.loc[mask, 'surface_m2']
        ).round(2)

        equip = [c for c in BOOLEAN_COLS if c in self.df.columns]
        self.df['score_equipements'] = self.df[equip].sum(axis=1)

        for src, dst in [('nb_chambres',    'chambres_num'),
                         ('etage',          'etage_num'),
                         ('nb_salles_bain', 'salles_bain_num')]:
            if src in self.df.columns:
                self.df[dst] = self._extract_numeric(self.df[src])

        cols_to_drop = [c for c in DROP_COLS if c in self.df.columns]
        self.df.drop(columns=cols_to_drop, inplace=True)

        self._log_step('step2_features', before, len(self.df))
        logger.info(f"  ✅ Colonnes : {list(self.df.columns)}\n")

    # ─── STEP 3 : Remove Outliers ─────────────────────────────────

    def step3_remove_outliers(self):
        logger.info("═" * 55)
        logger.info(f"ÉTAPE 3 │ Suppression des Outliers (IQR×{IQR_FACTOR})")
        logger.info("═" * 55)
        before  = len(self.df)
        details = {}

        for col in ['prix', 'surface_m2', 'prix_m2']:
            if col not in self.df.columns:
                continue
            Q1, Q3 = self.df[col].quantile([0.25, 0.75])
            IQR    = Q3 - Q1
            lo, hi = Q1 - IQR_FACTOR * IQR, Q3 + IQR_FACTOR * IQR
            prev   = len(self.df)
            self.df = self.df[self.df[col].isna() | self.df[col].between(lo, hi)]
            details[col] = {'removed': prev - len(self.df)}
            logger.info(f"  {col:<12} [{lo:,.0f}, {hi:,.0f}] → {prev - len(self.df)} supprimés")

        prev = len(self.df)
        self.df = self.df[
            self.df['prix'].isna() | self.df['prix'].between(PRIX_MIN, PRIX_MAX)
        ]
        logger.info(f"  prix absolu [{PRIX_MIN:,}, {PRIX_MAX:,}] → {prev - len(self.df)} supprimés")

        self._log_step('step3_outliers', before, len(self.df), details)
        logger.info(f"  ✅ {len(self.df)} lignes restantes\n")

    # ─── STEP 4 : Imputation ──────────────────────────────────────

    def step4_impute(self):
        logger.info("═" * 55)
        logger.info("ÉTAPE 4 │ Imputation")
        logger.info("═" * 55)
        before = len(self.df)

        for col in ['surface_m2', 'prix_m2', 'chambres_num', 'etage_num', 'salles_bain_num']:
            if col not in self.df.columns:
                continue
            missing = self.df[col].isna().sum()
            if missing:
                val = self.df[col].median()
                self.df[col].fillna(val, inplace=True)
                logger.info(f"  {col:<20} médiane={val:.2f}  ({missing} imputés)")

        for col in CATEGORICAL_COLS:
            if col not in self.df.columns:
                continue
            self.df[col] = self.df[col].replace('Nan', np.nan)
            missing = self.df[col].isna().sum()
            if missing:
                val = self.df[col].mode().iloc[0]
                self.df[col].fillna(val, inplace=True)
                logger.info(f"  {col:<20} mode='{val}'  ({missing} imputés)")

        if 'score_equipements' in self.df.columns:
            self.df['score_equipements'].fillna(0, inplace=True)

        self._log_step('step4_imputation', before, len(self.df))
        logger.info("  ✅ Imputation terminée\n")

    # ─── STEP 5 : Encoding ────────────────────────────────────────

    def step5_encode(self):
        logger.info("═" * 55)
        logger.info("ÉTAPE 5 │ Encodage catégoriel")
        logger.info("═" * 55)
        before = len(self.df)

        for col in CATEGORICAL_COLS:
            if col not in self.df.columns:
                continue
            le = LabelEncoder()
            self.df[f'{col}_enc'] = le.fit_transform(self.df[col].astype(str))
            self.encoders[col]    = le
            logger.info(f"  {col} → {col}_enc ({len(le.classes_)} classes)")

        self.df.drop(columns=[c for c in CATEGORICAL_COLS if c in self.df.columns], inplace=True)
        self._log_step('step5_encoding', before, len(self.df))
        logger.info("  ✅ Encodage terminé\n")

    # ─── STEP 6 : Scaling ─────────────────────────────────────────

    def step6_scale(self):
        logger.info("═" * 55)
        logger.info("ÉTAPE 6 │ StandardScaler")
        logger.info("═" * 55)
        before  = len(self.df)
        exclude = [TARGET, 'score_equipements'] + BOOLEAN_COLS + \
                  [f'{c}_enc' for c in CATEGORICAL_COLS]

        self.scaled_cols = [
            c for c in self.df.select_dtypes(include=[np.number]).columns
            if c not in exclude
        ]
        self.df[self.scaled_cols] = self.scaler.fit_transform(self.df[self.scaled_cols])

        self._log_step('step6_scaling', before, len(self.df), {'scaled_cols': self.scaled_cols})
        logger.info("  ✅ Scaling terminé\n")

    # ─── STEP 7 : Train/Test Split & Save ─────────────────────────

    def step7_split_and_save(self):
        logger.info("═" * 55)
        logger.info("ÉTAPE 7 │ Split & Sauvegarde")
        logger.info("═" * 55)

        self.df.dropna(inplace=True)
        if len(self.df) < 10:
            raise ValueError(f"Dataset trop petit : {len(self.df)} lignes")

        X = self.df.drop(columns=[TARGET])
        y = self.df[[TARGET]]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
        )
        logger.info(f"  Train : {len(X_train)}  Test : {len(X_test)}")

        for name, obj in [('X_train', X_train), ('X_test', X_test),
                          ('y_train', y_train), ('y_test',  y_test)]:
            obj.to_csv(f'{self.output_dir}/{name}.csv', index=False)

        joblib.dump(self.scaler,   f'{self.output_dir}/scaler.joblib')
        joblib.dump(self.encoders, f'{self.output_dir}/encoders.joblib')

        self.report['steps']['step7_split'] = {
            'total_rows': len(self.df), 'n_features': X.shape[1],
            'features': list(X.columns), 'train_rows': len(X_train),
            'test_rows': len(X_test)
        }
        logger.info("  ✅ Split & sauvegarde terminés\n")

    # ─── STEP 8 : Train epoch-by-epoch, Evaluate, PostgreSQL, Export ──

    def step8_train_and_evaluate(self, incremental=False):
        """
        Entraîne RandomForest epoch par epoch via warm_start.

        Chaque epoch ajoute TREES_PER_EPOCH arbres et mesure sur X_test :
          - accuracy = R²   (plus c'est haut, mieux c'est)
          - loss     = RMSE (plus c'est bas, mieux c'est)

        Les deux métriques sont loggées console ET insérées dans
        la table model_epochs de PostgreSQL à chaque epoch.

        incremental=True  → charge le modèle existant et continue
                            l'entraînement sur les nouvelles lignes.
        incremental=False → repart de zéro.
        """
        logger.info("═" * 55)
        mode_label = "INCRÉMENTAL" if incremental else "COMPLET"
        logger.info(f"ÉTAPE 8 │ RandomForest {mode_label} — epoch tracking")
        logger.info("═" * 55)

        X_train = pd.read_csv(f'{self.output_dir}/X_train.csv')
        y_train = pd.read_csv(f'{self.output_dir}/y_train.csv')[TARGET]
        X_test  = pd.read_csv(f'{self.output_dir}/X_test.csv')
        y_test  = pd.read_csv(f'{self.output_dir}/y_test.csv')[TARGET]

        # ── Choose training data & model ──────────────────────────
        if incremental and os.path.exists(MODEL_JL):
            model = joblib.load(MODEL_JL)
            logger.info("  🔄 Modèle existant chargé (apprentissage incrémental)")
            seen    = self._load_seen_indices()
            new_idx = [i for i in X_train.index if i not in seen]
            if not new_idx:
                logger.info("  ℹ️ Aucune nouvelle ligne — entraînement ignoré")
                return
            X_fit       = X_train.loc[new_idx]
            y_fit       = y_train.loc[new_idx]
            start_trees = model.n_estimators   # pick up from existing count
            logger.info(f"  Nouvelles lignes : {len(X_fit)}")
        else:
            model = RandomForestRegressor(
                n_estimators = TREES_PER_EPOCH,  # grows each epoch
                warm_start   = True,              # reuse already built trees
                random_state = RANDOM_STATE,
                n_jobs       = -1
            )
            X_fit       = X_train
            y_fit       = y_train
            start_trees = 0

        self._save_seen_indices(list(X_train.index))

        # ── Open PostgreSQL connection once for entire training ───
        try:
            conn = get_pg_conn()
            pg_ensure_tables(conn)
            pg_connected = True
        except Exception as e:
            logger.warning(f"  ⚠️ PostgreSQL non disponible : {e}")
            pg_connected = False
            conn = None

        # ── Epoch loop ────────────────────────────────────────────
        n_epochs  = TOTAL_TREES // TREES_PER_EPOCH
        epoch_log = []

        logger.info(f"  🌲 {n_epochs} epochs × {TREES_PER_EPOCH} arbres = {TOTAL_TREES} arbres total")
        logger.info(f"  {'Epoch':<8} {'N arbres':<12} {'Accuracy (R²)':<20} {'Loss (RMSE)'}")
        logger.info(f"  {'─'*8} {'─'*12} {'─'*20} {'─'*15}")

        for epoch in range(1, n_epochs + 1):
            model.n_estimators = start_trees + epoch * TREES_PER_EPOCH
            model.fit(X_fit, y_fit)

            y_pred_ep = model.predict(X_test)
            accuracy  = r2_score(y_test, y_pred_ep)
            loss      = np.sqrt(mean_squared_error(y_test, y_pred_ep))

            logger.info(
                f"  Epoch {epoch:<4} {model.n_estimators:<12} "
                f"{accuracy * 100:>12.2f} %      {loss:>12,.0f} MAD"
            )

            epoch_log.append({
                'epoch': epoch, 'n_trees': model.n_estimators,
                'accuracy': round(accuracy, 4), 'loss': round(loss, 2)
            })

            if pg_connected:
                try:
                    pg_insert_epoch(
                        conn, "RandomForestRegressor", mode_label,
                        epoch, model.n_estimators, accuracy, loss
                    )
                except Exception as e:
                    logger.warning(f"  ⚠️ Epoch {epoch} insert error : {e}")

        logger.info("  " + "─" * 55)

        # ── Final metrics ─────────────────────────────────────────
        y_pred_final = model.predict(X_test)
        r2   = r2_score(y_test, y_pred_final)
        mae  = mean_absolute_error(y_test, y_pred_final)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred_final))

        logger.info(f"  📊 R² final  : {r2 * 100:.2f} %")
        logger.info(f"  📊 MAE final : {mae:,.0f} MAD")
        logger.info(f"  📊 RMSE final: {rmse:,.0f} MAD")

        # ── Export model ──────────────────────────────────────────
        with open(MODEL_PKL, 'wb') as f:
            pickle.dump(model, f)
        joblib.dump(model, MODEL_JL)
        logger.info(f"  💾 {MODEL_PKL}")
        logger.info(f"  💾 {MODEL_JL}")

        # ── PostgreSQL : final metrics + predictions ──────────────
        if pg_connected:
            try:
                pg_insert_metrics(
                    conn, "RandomForestRegressor",
                    r2, rmse, mae, len(X_fit), mode_label
                )
                logger.info("  ✅ Métriques finales → model_metrics")

                # Build prediction sample with decoded labels
                df_pred = X_test.copy().reset_index(drop=True)
                df_pred['prix_reel']   = y_test.values
                df_pred['prix_predit'] = y_pred_final
                df_pred['erreur_abs']  = np.abs(df_pred['prix_reel'] - df_pred['prix_predit'])

                for col in ['ville', 'type_bien']:
                    enc_col = f'{col}_enc'
                    if col in self.encoders and enc_col in df_pred.columns:
                        df_pred[col] = self.encoders[col].inverse_transform(
                            df_pred[enc_col].astype(int)
                        )

                sample = df_pred.sample(min(500, len(df_pred)), random_state=RANDOM_STATE)
                pg_insert_predictions(conn, sample)
                logger.info(f"  ✅ {len(sample)} prédictions → predictions")

                conn.close()
            except Exception as e:
                logger.error(f"  ❌ PostgreSQL final insert error : {e}")

        # ── Report ────────────────────────────────────────────────
        self.report['steps']['step8_model'] = {
            'r2_score':  round(r2,   4),
            'mae':       round(mae,  2),
            'rmse':      round(rmse, 2),
            'mode':      mode_label,
            'n_epochs':  n_epochs,
            'epoch_log': epoch_log
        }
        logger.info("═" * 55)

    # ─── Seen-indices helpers (incremental learning) ─────────────

    def _load_seen_indices(self):
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE) as f:
                return set(json.load(f))
        return set()

    def _save_seen_indices(self, indices):
        with open(SEEN_FILE, 'w') as f:
            json.dump(list(indices), f)

    # ─── RUN ──────────────────────────────────────────────────────

    def run(self, incremental=False):
        """
        Exécute le pipeline complet.

        incremental=True  → réutilise le modèle existant et apprend
                            uniquement sur les nouvelles lignes collectées.
        """
        start = datetime.now()
        logger.info("\n" + "═" * 55)
        logger.info("🚀  DÉMARRAGE DU PIPELINE ML")
        logger.info(f"    {start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("═" * 55 + "\n")

        try:
            self.step1_load_and_validate()
            self.step2_feature_engineering()
            self.step3_remove_outliers()
            self.step4_impute()
            self.step5_encode()
            self.step6_scale()
            self.step7_split_and_save()
            self.step8_train_and_evaluate(incremental=incremental)
        except Exception as e:
            logger.error(f"❌ PIPELINE ÉCHOUÉ : {e}")
            self.report['status'] = 'FAILED'
            self.report['error']  = str(e)
            raise

        elapsed = (datetime.now() - start).seconds
        self.report['status']   = 'SUCCESS'
        self.report['duration'] = elapsed
        logger.info(f"\n  ⏱️  Temps total : {elapsed}s")

        report_path = f'{self.output_dir}/pipeline_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
        logger.info(f"  📄 Rapport : {report_path}")

        return self.report


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='ML Pipeline Immobilier Maroc')
    parser.add_argument('--incremental', action='store_true',
                        help='Continue learning from new data only')
    args = parser.parse_args()

    pipeline = MLPipeline(
        data_dir   = 'data/processed',
        output_dir = 'data/final'
    )
    pipeline.run(incremental=args.incremental)