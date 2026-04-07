# 🤖 Guide — Modèles de Prédiction & Metrics

## Vue d'ensemble

Le projet utilise l'apprentissage supervisé pour estimer le prix des biens immobiliers. L'objectif n'est pas seulement de prédire, mais de **suivre la fiabilité de l'IA dans le temps** pour informer les décisions BI.

---

## 🔬 Modèle de Référence : RandomForest

Le modèle actuel est un **RandomForestRegressor** (Forêt d'Arbres de Décision).
*   **Avantages** : Gère nativement les corrélations non-linéaires, robuste aux valeurs aberrantes, et fournit une importance des caractéristiques (Feature Importance).
*   **Localisation** : Le modèle entraîné est stocké dans `data/models/rf_model.pkl`.

### Features utilisées (Top X)
1.  **Surface (m²)** : Le facteur le plus corrélé au prix.
2.  **Localisation (Ville)** : Impact majeur sur la valeur du foncier.
3.  **Score Équipements** : Reflète le standing du bien.

---

## 📉 Tracking de Performance (KPIs)

Chaque cycle d'entraînement (toutes les 15 minutes) génère des métriques de validation stockées dans la table SQL `model_metrics`.

| Métrique | Utilité | Seuil de Qualité |
|----------|---------|------------------|
| **R² Score** | Précision globale du modèle | > 0.85 (Excellent) |
| **MAE** | Erreur moyenne en MAD | < 150 000 MAD |
| **RMSE** | Sensibilité aux grosses erreurs | - |

---

## 📊 Visualisation Power BI

Les analystes peuvent consulter l'onglet **"Performance IA"** du dashboard pour :
*   Voir si le modèle s'améliore à mesure que nous récoltons plus de données.
*   Identifier des périodes où le marché devient imprévisible (baisse du R²).

---

## 🛠️ Entraînement manuel
```bash
python src/cleaning/ml_pipeline.py
```
*Le script ré-entraînera le RandomForest, sauvegardera le nouveau `.pkl` et injectera une nouvelle ligne de performance dans PostgreSQL.*
