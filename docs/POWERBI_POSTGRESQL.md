# 📊 Guide — Power BI & Architecture Star Schema

## Vue d'ensemble

Le système de reporting est optimisé pour la performance et la clarté analytique. Il repose sur un **Schéma en Étoile** (Star Schema) qui sépare les mesures (faits) des axes d'analyse (dimensions).

---

## 🗄️ Architecture de la Base de Données

### 1. Table de Faits (`fact_annonces`)
Contient les données quantitatives et les clés étrangères :
*   `prix`, `surface_m2`, `nb_chambres`, `nb_salles_bain`
*   `id_loc` (FK -> dim_localisation)
*   `id_type` (FK -> dim_type_bien)
*   `id_source` (FK -> dim_source)

### 2. Tables de Dimensions
*   `dim_localisation` : Ville, Quartier.
*   `dim_type_bien` : Appartement, Villa, Maison, etc.
*   `dim_source` : Avito, Mubawab.

### 3. Tracking ML (`model_metrics`)
Table spéciale utilisée par Power BI pour suivre la performance de l'IA :
*   `r2_score` : Précision du modèle (ex: 0.85).
*   `mae` : Erreur moyenne en MAD.
*   `date_entrainement` : Horodatage.

---

## 🔗 Connexion Power BI

### Paramètres recommandés
*   **Serveur** : `localhost:5433`
*   **Base de données** : `immobilier_maroc`
*   **Utilisateur** : `immobilier` / `immobilier123`

### 💡 Best Practice : Utiliser la vue `v_dashboard_kpis`
Pour éviter de refaire les jointures manuellement dans Power BI, utilisez la vue SQL pré-calculée. Elle inclut déjà :
*   Toutes les dimensions associées.
*   Le calcul du `prix_m2`.
*   Le `score_equipements`.

---

## 📈 Mesures DAX Essentielles

Voici les mesures à créer pour votre premier dashboard :

| Nom | Formule DAX |
|-----|-------------|
| **Total Annonces** | `COUNTROWS('fact_annonces')` |
| **Prix M2 Moyen** | `AVERAGE('v_dashboard_kpis'[prix_m2])` |
| **Précision IA** | `MAX('model_metrics'[r2_score])` |
| **Nouvelles (7j)** | `CALCULATE([Total Annonces], 'fact_annonces'[date_scraping] >= TODAY()-7)` |

---

## ⚠️ Optimisation (Mémoire Insuffisante)
Si vous rencontrez une erreur de mémoire lors du rafraîchissement :
1.  Allez dans **Options** -> **Confidentialité**.
2.  Cochez **"Toujours ignorer les paramètres de niveau de confidentialité"**.
3.  Videz le cache dans **Chargement des données**.

> Ce guide conclut la documentation technique du pipeline. ✨
