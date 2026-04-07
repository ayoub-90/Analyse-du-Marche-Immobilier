# 🔗 Guide — Transformation & Nettoyage (Data Combiner)

## Vue d'ensemble

Le **Data Combiner** (`src/processing/data_combiner.py`) est le pont entre l'ingestion brute et le stockage structuré. Il assure que les données provenant de sources hétérogènes (Avito, Mubawab) soient uniformisées avant d'être envoyées au pipeline ML et à la base SQL.

---

## ⚙️ Processus de Transformation

1.  **Chargement Multi-fichiers** : Lit les derniers CSV dans `data/raw/`.
2.  **Harmonisation du Schéma** : Applique un schéma strict de 18 colonnes (types forcés).
3.  **Nettoyage Rigoureux** :
    *   **Déduplication** par URL (clé unique).
    *   **Filtrage métier** : Prix entre 50k et 50M MAD, Surface > 10 m².
    *   **Imputation** : Valeurs par défaut pour les équipements manquants.
4.  **Calcul de Valeur Ajoutée** :
    *   `prix_m2` : Prix total divisé par la surface.
    *   `score_equipements` : Somme pondérée des conforts (parking, piscine, etc.).

---

## 📂 Sorties de l'Étape

**Fichier généré :** `data/processed/immobilier_maroc_{timestamp}.csv`

Ce fichier est le **"Golden Dataset"** utilisé par :
*   Le Pipeline ML pour l'entraînement.
*   Le Loader SQL pour alimenter le **Star Schema**.

---

## ▶️ Exécution et Maintenance

```bash
python src/processing/data_combiner.py
```

*Note : Cette étape est sans état (stateless). Elle traite les fichiers bruts présents et génère un nouvel instantané de la donnée propre.*
