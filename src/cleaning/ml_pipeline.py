#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML Pipeline - Preprocessing Immobilier Maroc
=============================================
Pipeline complet en 7 étapes pour préparer les données aux modèles ML.

Étapes:
  1. Chargement & Validation du schéma
  2. Feature Engineering
  3. Suppression des Outliers (IQR)
  4. Imputation des valeurs manquantes
  5. Encodage des variables catégorielles
  6. Normalisation / Scaling
  7. Split Train / Test

Output: data/final/ → X_train, X_test, y_train, y_test + scaler/encoders
"""

import os
import re
import glob
import json
import pickle
import logging
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# Paths — resolved from THIS file so they work
# whether run directly or imported from a notebook
# ─────────────────────────────────────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))   # src/cleaning/
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))  # project root
_LOGS_DIR    = os.path.join(_PROJECT_ROOT, 'logs')
_FINAL_DIR   = os.path.join(_PROJECT_ROOT, 'data', 'final')

# Create directories BEFORE logging setup (FileHandler needs the dir to exist)
os.makedirs(_LOGS_DIR,  exist_ok=True)
os.makedirs(_FINAL_DIR, exist_ok=True)

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
TARGET       = 'prix'
TEST_SIZE    = 0.20
RANDOM_STATE = 42
IQR_FACTOR   = 3.0          # outliers au-delà de 3×IQR
PRIX_MIN     = 100_000       # MAD — filtre absolu en bas
PRIX_MAX     = 20_000_000    # MAD — filtre absolu en haut

CATEGORICAL_COLS = ['type_bien', 'ville', 'source']
BOOLEAN_COLS     = ['parking', 'ascenseur', 'balcon', 'piscine', 'jardin']
DROP_COLS        = ['id_annonce', 'titre', 'description', 'url',
                    'date_scraping', 'nb_chambres', 'nb_salles_bain', 'etage']


# ═══════════════════════════════════════════════════════
# PIPELINE CLASS
# ═══════════════════════════════════════════════════════

class MLPipeline:
    """
    Pipeline séquentiel de preprocessing pour modèles ML immobilier.

    Usage:
        pipeline = MLPipeline()
        pipeline.run()
    """

    def __init__(self, data_dir: str = 'data/processed', output_dir: str = 'data/final'):
        # Resolve to absolute paths so this works when imported from any working directory
        self.data_dir   = os.path.abspath(data_dir)
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.df         = None
        self.report     = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'steps': {}
        }
        self.scaler   = StandardScaler()
        self.encoders = {}    # col → LabelEncoder
        self.scaled_cols = [] # colonnes normalisées

    # ─── Utilitaires ──────────────────────────────────────────
    def _log_step(self, step: str, before: int, after: int, details: dict = None):
        dropped = before - after
        pct     = (dropped / before * 100) if before > 0 else 0
        logger.info(f"  {'↳'} {before} → {after} lignes  ({dropped} supprimées, {pct:.1f}%)")
        self.report['steps'][step] = {
            'rows_before': before,
            'rows_after':  after,
            'dropped':     dropped,
            **(details or {})
        }

    def _extract_numeric(self, series: pd.Series) -> pd.Series:
        """Extrait le premier nombre d'une chaîne (ex: '3 pièces' → 3)."""
        return series.astype(str).str.extract(r'(\d+)')[0].astype(float)

    # ─── ÉTAPE 1 : Chargement & Schéma ────────────────────────
    def step1_load_and_validate(self) -> None:
        logger.info("═" * 55)
        logger.info("ÉTAPE 1 │ Chargement & Validation du schéma")
        logger.info("═" * 55)

        files = glob.glob(os.path.join(self.data_dir, 'immobilier_maroc_*.csv'))
        if not files:
            raise FileNotFoundError(f"Aucun fichier combiné trouvé dans {self.data_dir}")

        latest = max(files, key=os.path.getctime)
        logger.info(f"  Fichier chargé : {latest}")
        self.df = pd.read_csv(latest)

        before = len(self.df)
        logger.info(f"  Colonnes : {list(self.df.columns)}")

        # Forcer les booleans en int
        for col in BOOLEAN_COLS:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0).astype(int)

        # Forcer prix en float
        self.df['prix'] = pd.to_numeric(self.df['prix'], errors='coerce')

        # Forcer surface en float
        if 'surface_m2' in self.df.columns:
            self.df['surface_m2'] = pd.to_numeric(self.df['surface_m2'], errors='coerce')

        # Standardiser les chaînes catégorielles
        for col in CATEGORICAL_COLS:
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(str).str.strip().str.title()

        # Supprimer lignes sans prix (target variable)
        self.df = self.df[self.df['prix'].notna()]

        self._log_step('step1_load', before, len(self.df), {'file': latest})
        logger.info(f"  ✅ Schéma validé — {len(self.df)} lignes\n")

    # ─── ÉTAPE 2 : Feature Engineering ───────────────────────
    def step2_feature_engineering(self) -> None:
        logger.info("═" * 55)
        logger.info("ÉTAPE 2 │ Feature Engineering")
        logger.info("═" * 55)

        before = len(self.df)

        # prix_m2 (recalculé proprement)
        mask = self.df['surface_m2'].notna() & (self.df['surface_m2'] > 0)
        self.df['prix_m2'] = np.nan
        self.df.loc[mask, 'prix_m2'] = (
            self.df.loc[mask, 'prix'] / self.df.loc[mask, 'surface_m2']
        ).round(2)

        # Score équipements (0-5)
        equip = [c for c in BOOLEAN_COLS if c in self.df.columns]
        self.df['score_equipements'] = self.df[equip].sum(axis=1)

        # Binaires individuels (déjà 0/1 mais on assure)
        for col in equip:
            self.df[col] = self.df[col].astype(int)

        # Features derived from nb_chambres / etage (parse text → int)
        if 'nb_chambres' in self.df.columns:
            self.df['chambres_num'] = self._extract_numeric(self.df['nb_chambres'])
            logger.info(f"  nb_chambres → chambres_num : {self.df['chambres_num'].notna().sum()} valides")

        if 'etage' in self.df.columns:
            self.df['etage_num'] = self._extract_numeric(self.df['etage'])
            logger.info(f"  etage → etage_num : {self.df['etage_num'].notna().sum()} valides")

        if 'nb_salles_bain' in self.df.columns:
            self.df['salles_bain_num'] = self._extract_numeric(self.df['nb_salles_bain'])
            logger.info(f"  nb_salles_bain → salles_bain_num : {self.df['salles_bain_num'].notna().sum()} valides")

        logger.info(f"  Nouvelles colonnes créées : prix_m2, score_equipements, chambres_num, etage_num, salles_bain_num")

        # Supprimer colonnes non exploitables par les modèles
        cols_to_drop = [c for c in DROP_COLS if c in self.df.columns]
        self.df.drop(columns=cols_to_drop, inplace=True)
        logger.info(f"  Colonnes supprimées : {cols_to_drop}")

        self._log_step('step2_features', before, len(self.df))
        logger.info(f"  ✅ Features engineerées — colonnes restantes : {list(self.df.columns)}\n")

    # ─── ÉTAPE 3 : Suppression des Outliers ───────────────────
    def step3_remove_outliers(self) -> None:
        logger.info("═" * 55)
        logger.info("ÉTAPE 3 │ Suppression des Outliers")
        logger.info("═" * 55)

        before = len(self.df)
        details = {}

        for col in ['prix', 'surface_m2', 'prix_m2']:
            if col not in self.df.columns:
                continue
            series = self.df[col].dropna()
            Q1, Q3 = series.quantile(0.25), series.quantile(0.75)
            IQR    = Q3 - Q1
            lo     = Q1 - IQR_FACTOR * IQR
            hi     = Q3 + IQR_FACTOR * IQR
            before_col = len(self.df)
            mask = (self.df[col].isna()) | ((self.df[col] >= lo) & (self.df[col] <= hi))
            self.df = self.df[mask]
            removed = before_col - len(self.df)
            logger.info(f"  {col:<12} │ [{lo:,.0f}, {hi:,.0f}] │ {removed} outliers supprimés")
            details[col] = {'lo': round(lo, 2), 'hi': round(hi, 2), 'removed': removed}

        # Filtre absolu prix
        before_abs = len(self.df)
        self.df = self.df[
            self.df['prix'].isna() |
            ((self.df['prix'] >= PRIX_MIN) & (self.df['prix'] <= PRIX_MAX))
        ]
        logger.info(f"  prix absolu [{PRIX_MIN:,}, {PRIX_MAX:,}] │ {before_abs - len(self.df)} supprimés")

        self._log_step('step3_outliers', before, len(self.df), details)
        logger.info(f"  ✅ Outliers supprimés — {len(self.df)} lignes restantes\n")

    # ─── ÉTAPE 4 : Imputation ─────────────────────────────────
    def step4_impute(self) -> None:
        logger.info("═" * 55)
        logger.info("ÉTAPE 4 │ Imputation des valeurs manquantes")
        logger.info("═" * 55)

        before = len(self.df)
        imputed = {}

        # Numériques → médiane
        num_cols = ['surface_m2', 'prix_m2', 'chambres_num', 'etage_num', 'salles_bain_num']
        for col in num_cols:
            if col not in self.df.columns:
                continue
            missing = self.df[col].isna().sum()
            if missing > 0:
                median_val = self.df[col].median()
                self.df[col] = self.df[col].fillna(median_val)
                imputed[col] = {'strategy': 'median', 'value': round(median_val, 2), 'filled': int(missing)}
                logger.info(f"  {col:<20} │ médiane={median_val:.2f} │ {missing} imputés")

        # Catégorielles → mode
        for col in CATEGORICAL_COLS:
            if col not in self.df.columns:
                continue
            missing = self.df[col].isna().sum() + (self.df[col] == 'Nan').sum()
            if missing > 0:
                mode_val = self.df[col][self.df[col] != 'Nan'].mode().iloc[0]
                self.df[col] = self.df[col].replace('Nan', mode_val).fillna(mode_val)
                imputed[col] = {'strategy': 'mode', 'value': mode_val, 'filled': int(missing)}
                logger.info(f"  {col:<20} │ mode='{mode_val}' │ {missing} imputés")

        # Score équipements → 0 si manquant
        if 'score_equipements' in self.df.columns:
            self.df['score_equipements'] = self.df['score_equipements'].fillna(0).astype(int)

        self._log_step('step4_imputation', before, len(self.df), imputed)

        # Vérification finale
        remaining = self.df.select_dtypes(include=[np.number]).isnull().sum()
        remaining = remaining[remaining > 0]
        if len(remaining) > 0:
            logger.warning(f"  ⚠️ NaN restants après imputation : {remaining.to_dict()}")
        else:
            logger.info("  ✅ Aucune valeur manquante dans les colonnes numériques\n")

    # ─── ÉTAPE 5 : Encodage ───────────────────────────────────
    def step5_encode(self) -> None:
        logger.info("═" * 55)
        logger.info("ÉTAPE 5 │ Encodage des variables catégorielles")
        logger.info("═" * 55)

        before = len(self.df)

        for col in CATEGORICAL_COLS:
            if col not in self.df.columns:
                continue
            le = LabelEncoder()
            self.df[f'{col}_enc'] = le.fit_transform(self.df[col].astype(str))
            self.encoders[col] = le
            classes = list(le.classes_)
            logger.info(f"  {col:<12} → {col}_enc │ {len(classes)} classes : {classes[:8]}{'...' if len(classes)>8 else ''}")

        # Supprimer les colonnes originales (remplacées par _enc)
        cols_to_drop = [c for c in CATEGORICAL_COLS if c in self.df.columns]
        self.df.drop(columns=cols_to_drop, inplace=True)

        self._log_step('step5_encoding', before, len(self.df))
        logger.info(f"  ✅ Encodage terminé — colonnes numériques : {list(self.df.columns)}\n")

    # ─── ÉTAPE 6 : Scaling ────────────────────────────────────
    def step6_scale(self) -> None:
        logger.info("═" * 55)
        logger.info("ÉTAPE 6 │ Normalisation (StandardScaler)")
        logger.info("═" * 55)

        before = len(self.df)

        # Colonnes candidates au scaling (exclure target et booléens)
        exclude = [TARGET, 'score_equipements'] + BOOLEAN_COLS + \
                  [f'{c}_enc' for c in CATEGORICAL_COLS]

        self.scaled_cols = [
            c for c in self.df.select_dtypes(include=[np.number]).columns
            if c not in exclude and c in self.df.columns
        ]

        logger.info(f"  Colonnes normalisées : {self.scaled_cols}")

        self.df[self.scaled_cols] = self.scaler.fit_transform(self.df[self.scaled_cols])

        self._log_step('step6_scaling', before, len(self.df),
                       {'scaled_cols': self.scaled_cols})
        logger.info("  ✅ Scaling terminé\n")

    # ─── ÉTAPE 7 : Train / Test Split ─────────────────────────
    def step7_split_and_save(self) -> None:
        logger.info("═" * 55)
        logger.info("ÉTAPE 7 │ Split Train/Test & Sauvegarde")
        logger.info("═" * 55)

        # Supprimer les NaN restants (sécurité finale)
        before = len(self.df)
        self.df = self.df.dropna()
        logger.info(f"  Nettoyage final : {before} → {len(self.df)} lignes")

        if len(self.df) < 10:
            raise ValueError(f"Dataset trop petit après pipeline : {len(self.df)} lignes")

        # Séparer features et target
        X = self.df.drop(columns=[TARGET])
        y = self.df[[TARGET]]

        logger.info(f"  Features (X) : {X.shape[1]} colonnes")
        logger.info(f"  Target  (y)  : {TARGET}")

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size    = TEST_SIZE,
            random_state = RANDOM_STATE
        )

        logger.info(f"  Train : {len(X_train)} lignes ({(1-TEST_SIZE)*100:.0f}%)")
        logger.info(f"  Test  : {len(X_test)}  lignes ({TEST_SIZE*100:.0f}%)")

        # Sauvegarder les CSV
        X_train.to_csv(f'{self.output_dir}/X_train.csv', index=False)
        X_test.to_csv( f'{self.output_dir}/X_test.csv',  index=False)
        y_train.to_csv(f'{self.output_dir}/y_train.csv', index=False)
        y_test.to_csv( f'{self.output_dir}/y_test.csv',  index=False)
        logger.info(f"  💾 CSV sauvegardés dans {self.output_dir}/")

        # Sauvegarder les artefacts sklearn
        with open(f'{self.output_dir}/scaler.pkl', 'wb') as f:
            pickle.dump(self.scaler, f)
        with open(f'{self.output_dir}/encoders.pkl', 'wb') as f:
            pickle.dump(self.encoders, f)
        logger.info("  💾 scaler.pkl, encoders.pkl sauvegardés")

        # Rapport final
        self.report['steps']['step7_split'] = {
            'total_rows':    len(self.df),
            'n_features':    X.shape[1],
            'features':      list(X.columns),
            'target':        TARGET,
            'train_rows':    len(X_train),
            'test_rows':     len(X_test),
            'test_size':     TEST_SIZE,
            'random_state':  RANDOM_STATE
        }
        self.report['status'] = 'SUCCESS'
        self.report['output_dir'] = self.output_dir

        report_path = f'{self.output_dir}/pipeline_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
        logger.info(f"  📄 Rapport : {report_path}\n")

        # Résumé console
        logger.info("═" * 55)
        logger.info("✅ PIPELINE TERMINÉ")
        logger.info("═" * 55)
        logger.info(f"  Dataset final  : {len(self.df)} lignes × {X.shape[1]+1} colonnes")
        logger.info(f"  X_train shape  : {X_train.shape}")
        logger.info(f"  X_test  shape  : {X_test.shape}")
        logger.info(f"  y_train shape  : {y_train.shape}")
        logger.info(f"  y_test  shape  : {y_test.shape}")
        logger.info(f"  Colonnes X     : {list(X.columns)}")
        logger.info("═" * 55)

    # ─── RUN ──────────────────────────────────────────────────
    def run(self) -> None:
        """Exécute le pipeline séquentiel complet."""
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
        except Exception as e:
            logger.error(f"❌ PIPELINE ÉCHOUÉ à l'étape : {e}")
            self.report['status'] = 'FAILED'
            self.report['error'] = str(e)
            raise

        elapsed = (datetime.now() - start).seconds
        logger.info(f"\n  ⏱️  Temps total : {elapsed}s")


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

if __name__ == '__main__':
    pipeline = MLPipeline(
        data_dir   = 'data/processed',
        output_dir = 'data/final'
    )
    pipeline.run()
