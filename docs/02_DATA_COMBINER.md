# 🔗 Guide — Combinaison & Nettoyage des Données

## Vue d'ensemble

Le **Data Combiner** (`src/processing/data_combiner.py`) est le pont entre le scraping brut et le pipeline ML. Il fusionne et uniformise les données des deux sources.

---

## 📁 Fichier

```
src/processing/
└── data_combiner.py    ← Script principal de combinaison
```

**Entrées :** `data/raw/avito/*.csv` + `data/raw/mubawab/*.csv`  
**Sortie :** `data/processed/immobilier_maroc_{timestamp}.csv`

---

## ⚙️ Fonctionnement Étape par Étape

```
data/raw/avito/*.csv    ─┐
                          ├─→ [1] Chargement   → 116 annonces brutes
data/raw/mubawab/*.csv  ─┘
                          │
                          ↓
                         [2] Uniformisation du schéma
                         (colonnes identiques, types cohérents)
                          │
                          ↓
                         [3] Déduplication (30 doublons supprimés)
                         clé : url + id_annonce
                          │
                          ↓
                         [4] Suppression annonces incomplètes
                         (sans prix ET sans surface)
                          │
                          ↓
                         [5] Calcul des features dérivées
                         • prix_m2 = prix / surface_m2
                         • score_equipements (0-5)
                          │
                          ↓
                     data/processed/immobilier_maroc_{ts}.csv
                     → 62-75 annonces propres
```

---

## 📊 Schéma Unifié Final

Les deux sources ont des formats légèrement différents. Le combiner les normalise :

| Colonne | Avito | Mubawab | Résultat |
|---------|-------|---------|---------|
| `prix` | "1 400 000 DH" | Numérique | `float` en MAD |
| `ville` | "Marrakech" | "marrakech, Marrakech" | Capitalisé |
| `type_bien` | URL-based | Champ explicite | Normalisé |
| `surface_m2` | Integer | Float | Integer |

---

## ▶️ Exécution

```bash
python src/processing/data_combiner.py
```

Ou via Makefile :
```bash
make combine
```

---

## 📂 Statistiques de Sortie Typiques

```
Total brut        : 116 annonces
- Doublons        : -30
- Incomplètes     : -24
= Dataset propre  : 62–75 annonces

Moyenne prix      : 1 305 679 MAD
Médiane prix      : 1 200 000 MAD
Surface moyenne   : 81 m²
Prix/m² moyen     : 17 013 MAD/m²
```

---

## 🔄 Utilisation dans le Pipeline Complet

```
[Scraping] → [Data Combiner] → [ML Pipeline] → [Modèles]
```

Le combiner est appelé automatiquement par l'Airflow DAG après chaque scraping.
