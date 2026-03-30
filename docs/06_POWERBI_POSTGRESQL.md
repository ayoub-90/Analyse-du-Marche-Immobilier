# 📊 Guide Power BI — Connexion PostgreSQL & Analyse Immobilier

**Document type :** Guide technique  
**Public cible :** Data Analysts, Développeurs BI  
**Outil :** Power BI Desktop  
**Source de données :** PostgreSQL 14 (Docker)

---

## 1. Prérequis

### 1.1 Pilote PostgreSQL pour Power BI

Power BI se connecte à PostgreSQL via le pilote **Npgsql**. Installez-le si ce n'est pas déjà fait :

1. Télécharger : [https://github.com/npgsql/npgsql/releases](https://github.com/npgsql/npgsql/releases) → choisir `Npgsql-x.x.x.msi`
2. Installer (redémarrer Power BI après)

### 1.2 Docker doit être actif

```powershell
# Vérifier que le container PostgreSQL est en cours d'exécution
docker compose up postgres-data -d
docker compose ps postgres-data
# STATUS doit afficher : Up (healthy)
```

---

## 2. Connexion Power BI → PostgreSQL

### 2.1 Paramètres de connexion

| Paramètre | Valeur |
|-----------|--------|
| Serveur | `localhost` |
| Port | `5433` |
| Base de données | `immobilier_maroc` |
| Utilisateur | `immobilier` |
| Mot de passe | `immobilier123` |
| SSL | Désactivé (localhost) |

### 2.2 Étapes dans Power BI Desktop

```
1. Ouvrir Power BI Desktop
2. Accueil → Obtenir des données → Plus...
3. Rechercher "PostgreSQL" → Connecter
4. Serveur   : localhost:5433
   Base      : immobilier_maroc
5. Cliquer "OK"
6. Saisir identifiants :
   Utilisateur : immobilier
   Mot de passe: immobilier123
7. "Se connecter"
```

### 2.3 Sélectionner les tables/vues

Dans le **Navigateur**, sélectionner :

| Objet SQL | Usage dans Power BI |
|-----------|---------------------|
| `annonces` | Table principale — toutes les annonces brutes |
| `v_dashboard_kpis` | Vue calculée — inclut `prix_m2` et `score_equipements` |

> **Recommandation** : Chargez `v_dashboard_kpis` pour le dashboard principal — elle est déjà optimisée avec les calculs.

---

## 3. Modèle de Données

### 3.1 Table `annonces`

```sql
-- Colonnes principales utilisées dans Power BI
SELECT
    id,                  -- Clé primaire (INT)
    source,              -- 'Avito' ou 'Mubawab' (VARCHAR)
    ville,               -- Ville du bien (VARCHAR)
    type_bien,           -- 'Appartement', 'Villa', 'Duplex'... (VARCHAR)
    prix,                -- Prix en MAD (NUMERIC)
    surface_m2,          -- Surface en m² (NUMERIC)
    nb_chambres,         -- Nombre de chambres (VARCHAR)
    parking,             -- 1 = Oui, 0 = Non (SMALLINT)
    ascenseur,           -- 1 = Oui, 0 = Non (SMALLINT)
    balcon,              -- 1 = Oui, 0 = Non (SMALLINT)
    piscine,             -- 1 = Oui, 0 = Non (SMALLINT)
    jardin,              -- 1 = Oui, 0 = Non (SMALLINT)
    date_scraping,       -- Date de collecte (DATE)
    created_at           -- Date d'insertion en base (TIMESTAMP)
FROM annonces;
```

### 3.2 Vue `v_dashboard_kpis` (recommandée pour Power BI)

```sql
-- Définition de la vue
CREATE OR REPLACE VIEW v_dashboard_kpis AS
SELECT
    a.ville,
    a.type_bien,
    a.source,
    a.prix,
    a.surface_m2,
    ROUND((a.prix / NULLIF(a.surface_m2, 0))::numeric, 0)  AS prix_m2,      -- Prix/m² calculé
    a.parking,
    a.ascenseur,
    a.balcon,
    a.piscine,
    a.jardin,
    (a.parking + a.ascenseur + a.balcon + a.piscine + a.jardin) AS score_equipements,  -- Score 0-5
    a.date_scraping,
    a.created_at
FROM annonces a
WHERE a.prix IS NOT NULL AND a.prix > 0;
```

---

## 4. Mesures DAX Recommandées

Après chargement dans Power BI, créez ces mesures DAX :

### 4.1 KPIs de Base

```dax
-- Prix moyen
Prix Moyen = AVERAGE('v_dashboard_kpis'[prix])

-- Prix médian
Prix Médian = MEDIAN('v_dashboard_kpis'[prix])

-- Nombre d'annonces
Nb Annonces = COUNTROWS('v_dashboard_kpis')

-- Prix moyen au m²
Prix Moy m2 = AVERAGE('v_dashboard_kpis'[prix_m2])

-- Surface moyenne
Surface Moyenne = AVERAGE('v_dashboard_kpis'[surface_m2])
```

### 4.2 Taux d'Équipements

```dax
-- Taux de parking (%)
Taux Parking =
    DIVIDE(
        CALCULATE(COUNTROWS('v_dashboard_kpis'), 'v_dashboard_kpis'[parking] = 1),
        COUNTROWS('v_dashboard_kpis')
    ) * 100

-- Taux ascenseur (%)
Taux Ascenseur =
    DIVIDE(
        CALCULATE(COUNTROWS('v_dashboard_kpis'), 'v_dashboard_kpis'[ascenseur] = 1),
        COUNTROWS('v_dashboard_kpis')
    ) * 100
```

### 4.3 Analyse Comparative

```dax
-- Prix moyen par Source
Prix Moy par Source =
    CALCULATE(
        AVERAGE('v_dashboard_kpis'[prix]),
        ALLEXCEPT('v_dashboard_kpis', 'v_dashboard_kpis'[source])
    )

-- % du prix par rapport à la moyenne générale
Indice Prix =
    DIVIDE([Prix Moyen], CALCULATE([Prix Moyen], ALL('v_dashboard_kpis'))) * 100
```

---

## 5. Visuels Recommandés (Pages du Rapport)

### Page 1 — Vue d'Ensemble du Marché

| Visuel | Champ X | Champ Y / Valeur | Filtre |
|--------|---------|-----------------|--------|
| Carte KPI | — | `Nb Annonces` | — |
| Carte KPI | — | `Prix Moyen` | — |
| Carte KPI | — | `Prix Médian` | — |
| Graphique barres | `ville` | `Prix Moyen` | — |
| Graphique secteurs | `type_bien` | `Nb Annonces` | — |
| Histogramme | `prix` (bins) | `Nb Annonces` | — |
| Nuage de points | `surface_m2` | `prix` | couleur = `type_bien` |

### Page 2 — Analyse par Ville & Type

| Visuel | Configuration |
|--------|--------------|
| Matrice | Lignes=`ville`, Colonnes=`type_bien`, Valeurs=`Prix Moyen`, `Nb Annonces` |
| Graphique barres groupées | `ville` × `source` → `Prix Moyen` |
| Carte choroplèthique | `ville` → `Prix Moyen` (si données géo disponibles) |

### Page 3 — Équipements

| Visuel | Configuration |
|--------|--------------|
| Graphique barres | `parking/ascenseur/balcon/piscine/jardin` → Taux (%) |
| Boîte à moustaches | `parking` → `prix` (avec/sans) |
| Tableau | Toutes colonnes équipements + `Prix Moyen` |

---

## 6. Actualisation Automatique

### 6.1 Actualisation manuelle (test)
Dans Power BI Desktop :
```
Accueil → Actualiser
```

### 6.2 Actualisation planifiée (Power BI Service)

Pour publier et planifier l'actualisation automatique :

```
1. Power BI Desktop → Fichier → Publier → Power BI Service
2. Dans Power BI Service → Dataset → Paramètres
3. Connexion à la passerelle de données
4. Actualisation planifiée → Définir la fréquence (ex: Quotidien 06h00)
```

> **Note :** Une **passerelle de données locale** est nécessaire car PostgreSQL est en localhost. Installer : [https://powerbi.microsoft.com/en-us/gateway/](https://powerbi.microsoft.com/en-us/gateway/)

---

## 7. Requêtes SQL Utiles dans Power BI

Vous pouvez aussi utiliser **"Requête native"** dans Power BI (Options avancées lors de la connexion) :

### Marché global
```sql
SELECT
    COUNT(*)                                              AS nb_annonces,
    ROUND(AVG(prix)::numeric, 0)                          AS prix_moyen,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP
          (ORDER BY prix)::numeric, 0)                    AS prix_median,
    ROUND(AVG(surface_m2)::numeric, 1)                    AS surface_moy,
    ROUND(AVG(prix / NULLIF(surface_m2,0))::numeric, 0)   AS prix_m2_moy
FROM annonces
WHERE prix IS NOT NULL;
```

### Prix par ville
```sql
SELECT
    ville,
    COUNT(*)                                    AS nb,
    ROUND(AVG(prix)::numeric, 0)                AS prix_moy,
    ROUND(MIN(prix)::numeric, 0)                AS prix_min,
    ROUND(MAX(prix)::numeric, 0)                AS prix_max
FROM annonces
WHERE prix IS NOT NULL AND ville IS NOT NULL
GROUP BY ville
ORDER BY prix_moy DESC;
```

### Distribution par tranche de prix
```sql
SELECT
    CASE
        WHEN prix < 500000   THEN '< 500k MAD'
        WHEN prix < 1000000  THEN '500k–1M MAD'
        WHEN prix < 2000000  THEN '1M–2M MAD'
        WHEN prix < 3000000  THEN '2M–3M MAD'
        ELSE '> 3M MAD'
    END                       AS tranche,
    COUNT(*)                  AS nb_annonces
FROM annonces
WHERE prix IS NOT NULL
GROUP BY tranche
ORDER BY MIN(prix);
```

---

## 8. Dépannage

| Problème | Solution |
|----------|----------|
| `"Npgsql not found"` | Installer le pilote Npgsql et redémarrer Power BI |
| `"Connection refused :5433"` | Vérifier `docker compose up postgres-data -d` |
| `"Authentication failed"` | User=`immobilier` / Password=`immobilier123` |
| Données vides | Lancer `python src/processing/load_to_sql.py --load` |
| `v_dashboard_kpis` introuvable | Lancer `docker compose exec postgres-data psql -U immobilier -d immobilier_maroc -f /sql/queries/analytics.sql` |
