#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Combiner - Fusion Avito + Mubawab
Uniformise et nettoie les données pour créer un dataset unique
"""

import pandas as pd
import glob
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataCombiner:
    """Combine et nettoie les données des scrapers"""
    
    # Schéma unifié final
    FINAL_SCHEMA = {
        'id_annonce': str,
        'source': str,
        'type_bien': str,
        'ville': str,
        'prix': float,
        'surface_m2': int,
        'nb_chambres': str,
        'nb_salles_bain': str,
        'etage': str,
        'parking': int,
        'ascenseur': int,
        'balcon': int,
        'piscine': int,
        'jardin': int,
        'titre': str,
        'description': str,
        'url': str,
        'date_scraping': str
    }
    
    def __init__(self):
        self.df_combined = None
    
    def load_latest_files(self):
        """Charge les derniers fichiers Avito et Mubawab"""
        logger.info("📂 Chargement des fichiers...")
        
        # Avito
        avito_files = glob.glob("data/raw/avito/avito_*.csv")
        if not avito_files:
            logger.warning("⚠️ Aucun fichier Avito trouvé")
            df_avito = pd.DataFrame()
        else:
            latest_avito = max(avito_files, key=os.path.getctime)
            df_avito = pd.read_csv(latest_avito)
            logger.info(f"✓ Avito: {len(df_avito)} annonces ({latest_avito})")
        
        # Mubawab
        mubawab_files = glob.glob("data/raw/mubawab/mubawab_*.csv")
        if not mubawab_files:
            logger.warning("⚠️ Aucun fichier Mubawab trouvé")
            df_mubawab = pd.DataFrame()
        else:
            latest_mubawab = max(mubawab_files, key=os.path.getctime)
            df_mubawab = pd.read_csv(latest_mubawab)
            logger.info(f"✓ Mubawab: {len(df_mubawab)} annonces ({latest_mubawab})")
        
        return df_avito, df_mubawab
    
    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalise un DataFrame vers le schéma unifié"""
        if df.empty:
            return pd.DataFrame(columns=self.FINAL_SCHEMA.keys())
        
        # Créer DataFrame avec toutes les colonnes
        df_norm = pd.DataFrame()
        
        for col, dtype in self.FINAL_SCHEMA.items():
            if col in df.columns:
                df_norm[col] = df[col]
            else:
                # Valeur par défaut selon type
                if dtype == int:
                    df_norm[col] = 0
                elif dtype == float:
                    df_norm[col] = None
                else:
                    df_norm[col] = ""
        
        return df_norm
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Nettoie les données"""
        logger.info("🧹 Nettoyage des données...")
        
        initial_count = len(df)
        
        # 1. Supprimer doublons (même titre + ville)
        df = df.drop_duplicates(subset=['titre', 'ville'], keep='first')
        logger.info(f"  Doublons supprimés: {initial_count - len(df)}")
        
        # 2. Supprimer annonces sans prix ET sans surface
        df = df[(df['prix'].notna()) | (df['surface_m2'].notna())]
        logger.info(f"  Annonces incomplètes: {initial_count - len(df)}")
        
        # 3. Nettoyer prix aberrants
        if 'prix' in df.columns:
            df = df[(df['prix'].isna()) | ((df['prix'] >= 50000) & (df['prix'] <= 50000000))]
        
        # 4. Nettoyer surface aberrante
        if 'surface_m2' in df.columns:
            df = df[(df['surface_m2'].isna()) | ((df['surface_m2'] >= 10) & (df['surface_m2'] <= 10000))]
        
        # 5. Nettoyer villes vides
        df = df[df['ville'].str.len() > 0]
        
        # 6. Standardiser type_bien
        type_mapping = {
            'appartement': 'Appartement',
            'villa': 'Villa',
            'maison': 'Maison',
            'riad': 'Riad',
            'duplex': 'Duplex'
        }
        df['type_bien'] = df['type_bien'].str.lower().map(type_mapping).fillna('Appartement')
        
        logger.info(f"✓ {len(df)} annonces après nettoyage")
        return df
    
    def add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ajoute des features calculées"""
        logger.info("➕ Ajout features calculées...")
        
        # Prix par m²
        df['prix_m2'] = None
        mask = (df['prix'].notna()) & (df['surface_m2'].notna()) & (df['surface_m2'] > 0)
        df.loc[mask, 'prix_m2'] = (df.loc[mask, 'prix'] / df.loc[mask, 'surface_m2']).round(2)
        
        # Score équipements (0-5)
        df['score_equipements'] = (
            df['parking'] + df['ascenseur'] + df['balcon'] + df['piscine'] + df['jardin']
        )
        
        return df
    
    def combine(self) -> pd.DataFrame:
        """Processus complet de combinaison"""
        logger.info("="*60)
        logger.info("🔄 COMBINAISON DES DONNÉES")
        logger.info("="*60)
        
        # Charger
        df_avito, df_mubawab = self.load_latest_files()
        
        # Normaliser
        df_avito_norm = self.normalize_dataframe(df_avito)
        df_mubawab_norm = self.normalize_dataframe(df_mubawab)
        
        # Combiner
        self.df_combined = pd.concat([df_avito_norm, df_mubawab_norm], ignore_index=True)
        logger.info(f"📊 Total avant nettoyage: {len(self.df_combined)}")
        
        # Nettoyer
        self.df_combined = self.clean_data(self.df_combined)
        
        # Ajouter features
        self.df_combined = self.add_derived_features(self.df_combined)
        
        # Trier
        self.df_combined = self.df_combined.sort_values(['source', 'ville', 'prix'])
        
        # Sauvegarder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/processed/immobilier_maroc_{timestamp}.csv"
        
        os.makedirs("data/processed", exist_ok=True)
        self.df_combined.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        logger.info(f"\n💾 Fichier combiné: {output_path}")
        logger.info(f"📊 Total final: {len(self.df_combined)} annonces")
        
        # Statistiques
        self.print_stats()
        
        return self.df_combined
    
    def print_stats(self):
        """Affiche statistiques"""
        df = self.df_combined
        
        print("\n" + "="*60)
        print("📊 STATISTIQUES FINALES")
        print("="*60)
        
        print(f"\n🏢 PAR SOURCE:")
        print(df['source'].value_counts())
        
        print(f"\n🏠 PAR TYPE DE BIEN:")
        print(df['type_bien'].value_counts())
        
        print(f"\n📍 TOP 10 VILLES:")
        print(df['ville'].value_counts().head(10))
        
        print(f"\n💰 PRIX:")
        print(f"  Moyenne: {df['prix'].mean():,.0f} MAD")
        print(f"  Médiane: {df['prix'].median():,.0f} MAD")
        print(f"  Min: {df['prix'].min():,.0f} MAD")
        print(f"  Max: {df['prix'].max():,.0f} MAD")
        
        print(f"\n📐 SURFACE:")
        print(f"  Moyenne: {df['surface_m2'].mean():.0f} m²")
        print(f"  Médiane: {df['surface_m2'].median():.0f} m²")
        
        if 'prix_m2' in df.columns:
            print(f"\n💵 PRIX/M²:")
            print(f"  Moyenne: {df['prix_m2'].mean():,.0f} MAD/m²")
            print(f"  Médiane: {df['prix_m2'].median():,.0f} MAD/m²")
        
        print("="*60)


def main():
    """Point d'entrée"""
    combiner = DataCombiner()
    df = combiner.combine()
    
    print(f"\n✅ Dataset final prêt avec {len(df)} annonces")
    print(f"Colonnes: {list(df.columns)}")


if __name__ == "__main__":
    main()