-- ============================================================
-- QUERIES ANALYTIQUES — Marché Immobilier Marocain
-- ============================================================
-- Pour usage avec Power BI / Tableau : connectez l'outil
-- à PostgreSQL (postgres-data:5432, db=immobilier_maroc)
-- ============================================================

-- ─── KPIs Globaux ──────────────────────────────────────────

-- 1. Résumé global du marché
SELECT
    COUNT(*)                                   AS total_annonces,
    COUNT(DISTINCT ville)                      AS nb_villes,
    COUNT(DISTINCT source)                     AS nb_sources,
    ROUND(AVG(prix)::numeric, 0)               AS prix_moyen,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix)::numeric, 0)
                                               AS prix_median,
    ROUND(MIN(prix)::numeric, 0)               AS prix_min,
    ROUND(MAX(prix)::numeric, 0)               AS prix_max,
    ROUND(AVG(surface_m2)::numeric, 1)         AS surface_moy_m2,
    ROUND(AVG(prix / NULLIF(surface_m2, 0))::numeric, 0)
                                               AS prix_moy_par_m2,
    MAX(date_scraping)                         AS derniere_maj
FROM annonces
WHERE prix IS NOT NULL AND prix > 0;


-- ─── Analyse par Ville ──────────────────────────────────────

-- 2. Prix moyen par ville (pour carte / bar chart)
SELECT
    ville,
    COUNT(*)                                   AS nb_annonces,
    ROUND(AVG(prix)::numeric, 0)               AS prix_moyen,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix)::numeric, 0)
                                               AS prix_median,
    ROUND(MIN(prix)::numeric, 0)               AS prix_min,
    ROUND(MAX(prix)::numeric, 0)               AS prix_max,
    ROUND(AVG(surface_m2)::numeric, 1)         AS surface_moy,
    ROUND(AVG(prix / NULLIF(surface_m2, 0))::numeric, 0)
                                               AS prix_m2_moy
FROM annonces
WHERE prix IS NOT NULL AND ville IS NOT NULL
GROUP BY ville
ORDER BY prix_moyen DESC;


-- ─── Analyse par Type de Bien ───────────────────────────────

-- 3. Répartition et prix par type de bien
SELECT
    type_bien,
    COUNT(*)                                   AS nb_annonces,
    ROUND(AVG(prix)::numeric, 0)               AS prix_moyen,
    ROUND(AVG(surface_m2)::numeric, 1)         AS surface_moy,
    ROUND(AVG(prix / NULLIF(surface_m2, 0))::numeric, 0)
                                               AS prix_m2_moy,
    SUM(parking)                               AS avec_parking,
    SUM(ascenseur)                             AS avec_ascenseur,
    SUM(piscine)                               AS avec_piscine
FROM annonces
WHERE prix IS NOT NULL AND type_bien IS NOT NULL
GROUP BY type_bien
ORDER BY nb_annonces DESC;


-- ─── Analyse par Source ─────────────────────────────────────

-- 4. Comparaison Avito vs Mubawab
SELECT
    source,
    COUNT(*)                                   AS nb_annonces,
    ROUND(AVG(prix)::numeric, 0)               AS prix_moyen,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix)::numeric, 0)
                                               AS prix_median,
    ROUND(AVG(surface_m2)::numeric, 1)         AS surface_moy,
    COUNT(*) FILTER (WHERE prix IS NOT NULL)   AS avec_prix,
    COUNT(*) FILTER (WHERE parking = 1)        AS avec_parking
FROM annonces
GROUP BY source
ORDER BY nb_annonces DESC;


-- ─── Évolution Temporelle ───────────────────────────────────

-- 5. Volume de scraping par date
SELECT
    date_scraping,
    source,
    COUNT(*)                                   AS nb_annonces,
    ROUND(AVG(prix)::numeric, 0)               AS prix_moyen
FROM annonces
GROUP BY date_scraping, source
ORDER BY date_scraping DESC;


-- ─── Analyse des Équipements ────────────────────────────────

-- 6. Taux d'équipements et impact sur le prix
SELECT
    ROUND(AVG(parking) * 100, 1)               AS pct_parking,
    ROUND(AVG(ascenseur) * 100, 1)             AS pct_ascenseur,
    ROUND(AVG(balcon) * 100, 1)                AS pct_balcon,
    ROUND(AVG(piscine) * 100, 1)               AS pct_piscine,
    ROUND(AVG(jardin) * 100, 1)                AS pct_jardin
FROM annonces;

-- Impact parking sur le prix
SELECT
    CASE WHEN parking = 1 THEN 'Avec parking' ELSE 'Sans parking' END AS statut,
    COUNT(*)                                   AS nb,
    ROUND(AVG(prix)::numeric, 0)               AS prix_moyen
FROM annonces
WHERE prix IS NOT NULL
GROUP BY parking;


-- ─── Distribution des Prix ──────────────────────────────────

-- 7. Distribution en tranches de prix
SELECT
    CASE
        WHEN prix < 500000        THEN '< 500k MAD'
        WHEN prix < 1000000       THEN '500k - 1M MAD'
        WHEN prix < 2000000       THEN '1M - 2M MAD'
        WHEN prix < 3000000       THEN '2M - 3M MAD'
        WHEN prix < 5000000       THEN '3M - 5M MAD'
        ELSE '> 5M MAD'
    END                                        AS tranche_prix,
    COUNT(*)                                   AS nb_annonces,
    ROUND(AVG(prix)::numeric, 0)               AS prix_moy_tranche
FROM annonces
WHERE prix IS NOT NULL
GROUP BY tranche_prix
ORDER BY MIN(prix);


-- ─── Vue Matérialisée pour Dashboard ────────────────────────

-- 8. Vue resumée pour Power BI / Tableau
CREATE OR REPLACE VIEW v_dashboard_kpis AS
SELECT
    a.ville,
    a.type_bien,
    a.source,
    a.prix,
    a.surface_m2,
    ROUND((a.prix / NULLIF(a.surface_m2, 0))::numeric, 0)  AS prix_m2,
    a.parking,
    a.ascenseur,
    a.balcon,
    a.piscine,
    a.jardin,
    (a.parking + a.ascenseur + a.balcon + a.piscine + a.jardin)
                                                             AS score_equipements,
    a.date_scraping,
    a.created_at
FROM annonces a
WHERE a.prix IS NOT NULL AND a.prix > 0;
