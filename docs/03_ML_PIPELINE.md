# 🔧 Guide — Pipeline ML de Preprocessing

## Vue d'ensemble

Le **ML Pipeline** (`src/cleaning/ml_pipeline.py`) transforme les données combinées en un dataset 100% prêt pour l'entraînement ML : zéro valeur manquante, toutes les colonnes numériques, split train/test effectué.

---

## 📁 Fichier

```
src/cleaning/
└── ml_pipeline.py      ← Pipeline ML complet (7 étapes)
```

**Entrée :** `data/processed/immobilier_maroc_*.csv` (le plus récent)  
**Sorties :** `data/final/` → X_train, X_test, y_train, y_test, scaler.pkl, encoders.pkl

---

## 🔄 Les 7 Étapes

### Étape 1 — Chargement & Validation du Schéma
- Charge le CSV combiné le plus récent
- Force les types : `prix` → `float`, boolean → `int`
- **Supprime les lignes sans prix** (target variable obligatoire)

### Étape 2 — Feature Engineering
| Feature créée | Calcul | Description |
|--------------|--------|-------------|
| `prix_m2` | `prix / surface_m2` | Prix par mètre carré |
| `score_equipements` | `parking + ascenseur + balcon + piscine + jardin` | Score 0-5 |
| `chambres_num` | Extraction regex de `nb_chambres` | "3 pièces" → 3 |
| `etage_num` | Extraction regex de `etage` | "2ème étage" → 2 |
| `salles_bain_num` | Extraction regex de `nb_salles_bain` | Numérique |

**Colonnes supprimées :** `id_annonce`, `titre`, `description`, `url`, `date_scraping`, `nb_chambres`, `nb_salles_bain`, `etage`

### Étape 3 — Suppression des Outliers (IQR × 3)
- Appliqué sur : `prix`, `surface_m2`, `prix_m2`
- Formule : `Q1 - 3×IQR ≤ valeur ≤ Q3 + 3×IQR`
- Filtre absolu prix : entre 100 000 MAD et 20 000 000 MAD

### Étape 4 — Imputation des Valeurs Manquantes
| Colonne | Stratégie | Valeur typique |
|---------|-----------|---------------|
| `surface_m2` | Médiane | 71 m² |
| `prix_m2` | Médiane | 15 302 MAD/m² |
| `chambres_num`, `etage_num` | Médiane | 2-3 |
| `type_bien`, `ville`, `source` | Mode | Appartement |

### Étape 5 — Encodage Catégoriel (LabelEncoder)
| Colonne originale | Colonne encodée | Classes |
|-------------------|-----------------|---------|
| `type_bien` | `type_bien_enc` | Appartement=0, Duplex=1 |
| `ville` | `ville_enc` | Asilah=0, Casablanca=1, Marrakech=2, ... |
| `source` | `source_enc` | Avito=0, Mubawab=1 |

Les encodeurs sont sauvegardés dans `encoders.pkl` pour réutilisation en production.

### Étape 6 — Normalisation (StandardScaler)
Colonnes mises à l'échelle (z-score) : `surface_m2`, `prix_m2`, `chambres_num`, `etage_num`, `salles_bain_num`

**Non normalisées :** `prix` (target), booléens (0/1), encoded categoricals

Le scaler est sauvegardé dans `scaler.pkl`.

### Étape 7 — Split Train / Test
```python
test_size=0.20, random_state=42
# → 80% train (56 lignes), 20% test (14 lignes)
```

---

## 📂 Fichiers Générés

```
data/final/
├── X_train.csv          ← (56 × 14) features d'entraînement
├── X_test.csv           ← (14 × 14) features de test
├── y_train.csv          ← (56 × 1) prix cibles entraînement
├── y_test.csv           ← (14 × 1) prix cibles test
├── scaler.pkl           ← StandardScaler fitted
├── encoders.pkl         ← LabelEncoders fitted
└── pipeline_report.json ← Stats de chaque étape
```

---

## ▶️ Exécution

```bash
python src/cleaning/ml_pipeline.py
```

Un `pipeline_report.json` est généré avec les statistiques de chaque étape.

---

## ⚠️ Note Importante

> Le pipeline résout automatiquement ses chemins depuis `__file__`, donc il fonctionne aussi bien :
> - Lancé directement : `python src/cleaning/ml_pipeline.py`
> - Importé depuis un notebook Jupyter (chemin relatif `../`)
