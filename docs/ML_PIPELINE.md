# 🔧 Guide — Pipeline ML & Predictive Engineering

## Vue d'ensemble

Le **ML Pipeline** (`src/cleaning/ml_pipeline.py`) est le cœur intelligent du projet. Il transforme les données brutes en un modèle prédictif de prix et génère des indicateurs de performance pour Power BI.

---

## 🔄 Les 8 Étapes du Pipeline

### 1 à 7 : Nettoyage et Préparation
*   **Engineering** : Création de `prix_m2`, `score_equipements`, et extraction numérique des chambres/étages.
*   **Outliers** : Suppression des annonces aux prix extrêmes (IQR factor 3.0).
*   **Imputation** : Remplacement des valeurs manquantes par les médianes calculées.
*   **Encodage** : Transformation des villes et types de biens en données numériques (LabelEncoding).
*   **Scaling** : Normalisation des échelles avec `StandardScaler`.

### 8 : Entraînement & Logs KPI (Nouveau)
**Action :** Entraîne un modèle **RandomForestRegressor** sur les données fraîches.
*   **Calcul des Métriques** : R² Score, RMSE, MAE.
*   **Persistence SQL** : Les scores sont automatiquement insérés dans la table `model_metrics` de PostgreSQL.
*   **Persistence Modèle** : Le modèle entraîné est sauvegardé dans `data/models/rf_model.pkl`.

---

## 📈 Tracking de Performance

Grâce à l'étape 8, Power BI peut afficher l'évolution de la précision de votre IA :

| Métrique | Description | Cible |
|----------|-------------|-------|
| `r2_score` | Coefficient de détermination | > 0.80 |
| `mae` | Erreur absolue moyenne | < 200k MAD |
| `rmse` | Racine de l'erreur quadratique | - |

---

## 📁 Sorties du Pipeline

```
data/
├── final/
│   ├── X_train.csv / y_train.csv
│   ├── scaler.pkl / encoders.pkl
│   └── pipeline_report.json
└── models/
    └── rf_model.pkl          ← Modèle prêt pour l'inférence
```

---

## ▶️ Exécution manuelle
```bash
python src/cleaning/ml_pipeline.py
```
*Note : Dans le flux de production, cette étape est lancée automatiquement par Airflow toutes les 15 minutes.*
