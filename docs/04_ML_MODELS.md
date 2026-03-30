# 🤖 Guide — Modèles de Prédiction de Prix

## Vue d'ensemble

Le notebook `notebooks/03_Model_Training.ipynb` entraîne et compare **6 modèles de régression** pour prédire le prix des biens immobiliers en MAD.

---

## 🧠 Modèles Entraînés

| Modèle | Type | Paramètres clés | Avantages |
|--------|------|-----------------|-----------|
| **Linear Regression** | Linéaire | — | Baseline, interprétable |
| **Ridge (α=1.0)** | Linéaire régularisé L2 | `alpha=1.0` | Réduit overfitting |
| **Lasso (α=100)** | Linéaire régularisé L1 | `alpha=100` | Sélection automatique de features |
| **Random Forest** | Ensemble (bagging) | `n_estimators=200, max_depth=10` | Robuste, non-linéaire |
| **Gradient Boosting** | Ensemble (boosting) | `n_estimators=200, lr=0.1` | Haute précision |
| **XGBoost** | Ensemble (boosting XGB) | `n_estimators=200, lr=0.1` | Meilleur rapport précision/vitesse |

---

## 📊 Métriques d'Évaluation

| Métrique | Formule | Interprétation |
|----------|---------|----------------|
| **R²** | `1 - SS_res/SS_tot` | 1.0 = parfait, 0 = modèle nul |
| **MAE** | `mean(|y - ŷ|)` | Erreur absolue moyenne en MAD |
| **RMSE** | `√mean((y - ŷ)²)` | Pénalise les grandes erreurs |
| **MAPE** | `mean(|y - ŷ|/y) × 100` | Erreur relative en % |
| **CV R²** | Validation croisée 5-fold | Généralisation sur le jeu d'entraînement |

---

## 🏆 Sélection du Meilleur Modèle

Le modèle avec le **R² Test le plus élevé** est automatiquement sélectionné et sauvegardé.

```python
# data/final/best_model.pkl
with open('data/final/best_model.pkl', 'rb') as f:
    best_model = pickle.load(f)

# Prédiction sur nouvelles données
y_pred = best_model.predict(X_new)
```

---

## 📂 Fichiers Générés

```
data/final/
├── best_model.pkl        ← Meilleur modèle sérialisé
└── model_results.json    ← Métriques de tous les modèles
```

---

## 🔍 Feature Importance

Les modèles basés sur des arbres (Random Forest, GBM, XGBoost) fournissent des importances de variables. Typiquement :

1. **`prix_m2`** — Le prix au m² est le plus prédictif du prix total
2. **`surface_m2`** — Surface du bien
3. **`ville_enc`** — La ville a un impact majeur (Casablanca > Marrakech > Asilah)
4. **`type_bien_enc`** — Type de bien
5. **`score_equipements`** — Nombre d'équipements

---

## 🎯 Comment Prédire un Nouveau Bien

```python
import pickle, pandas as pd, numpy as np

# Charger les artefacts
with open('data/final/best_model.pkl', 'rb') as f:
    model = pickle.load(f)
with open('data/final/scaler.pkl', 'rb') as f:
    scaler = pickle.load(f)
with open('data/final/encoders.pkl', 'rb') as f:
    encoders = pickle.load(f)

# Nouveau bien
bien = {
    'surface_m2':        90,
    'parking':           1,
    'ascenseur':         1,
    'balcon':            0,
    'piscine':           0,
    'jardin':            0,
    'score_equipements': 2,
    'chambres_num':      3,
    'etage_num':         2,
    'salles_bain_num':   1,
    'type_bien':         'Appartement',   # sera encodé
    'ville':             'Marrakech',     # sera encodé
    'source':            'Avito',         # sera encodé
}

# Encoder les colonnes catégorielles
for col in ['type_bien', 'ville', 'source']:
    bien[f'{col}_enc'] = encoders[col].transform([bien[col]])[0]
    del bien[col]

# Créer DataFrame
X_new = pd.DataFrame([bien])
# Scaler les colonnes numériques appropriées
scale_cols = ['surface_m2', 'prix_m2', 'chambres_num', 'etage_num', 'salles_bain_num']
X_new['prix_m2'] = 0  # placeholder si pas connu
X_new[scale_cols] = scaler.transform(X_new[scale_cols])

# Prédire
prix_predit = model.predict(X_new)[0]
print(f"Prix estimé : {prix_predit:,.0f} MAD")
```

---

## ⚠️ Limites avec le Dataset Actuel

> Avec seulement **70 enregistrements** (test batch), les performances sont indicatives.
> - Pour un modèle production fiable : minimum **500-1000 annonces**
> - Lancer le scraping complet (50 pages × 2 sources × multi-villes)
> - Re-exécuter `ml_pipeline.py` puis `03_Model_Training.ipynb`
