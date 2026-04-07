-- ==============================================================================
-- SCHÉMA EN ÉTOILE : Création des tables dimensionnelles et de la table de faits
-- ==============================================================================

-- 1. Dimension : Localisation (Ville et/ou Quartier)
-- La combinaison ville + quartier doit être unique
CREATE TABLE IF NOT EXISTS dim_localisation (
    id_loc SERIAL PRIMARY KEY,
    ville VARCHAR(100) NOT NULL,
    quartier VARCHAR(150),
    UNIQUE(ville, quartier)
);

-- 2. Dimension : Type de Bien
CREATE TABLE IF NOT EXISTS dim_type_bien (
    id_type SERIAL PRIMARY KEY,
    type_bien VARCHAR(50) NOT NULL UNIQUE
);

-- 3. Dimension : Source du Scraping
CREATE TABLE IF NOT EXISTS dim_source (
    id_source SERIAL PRIMARY KEY,
    site_source VARCHAR(50) NOT NULL UNIQUE
);

-- 4. Table de Faits : Annonces
CREATE TABLE IF NOT EXISTS fact_annonces (
    id SERIAL PRIMARY KEY,
    id_annonce VARCHAR(100),       -- ID d'origine sur le site source
    url TEXT UNIQUE NOT NULL,      -- URL unique utilisée pour la déduplication
    titre TEXT,
    prix NUMERIC,
    surface_m2 NUMERIC,
    nb_chambres VARCHAR(20),
    nb_salles_bain VARCHAR(20),
    etage VARCHAR(50),
    parking SMALLINT,
    ascenseur SMALLINT,
    balcon SMALLINT,
    piscine SMALLINT,
    jardin SMALLINT,
    description TEXT,
    date_scraping DATE,
    id_loc INTEGER REFERENCES dim_localisation(id_loc),
    id_type INTEGER REFERENCES dim_type_bien(id_type),
    id_source INTEGER REFERENCES dim_source(id_source),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- INDEX (Pour optimiser Power BI et les Insertions)
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_fact_loc      ON fact_annonces(id_loc);
CREATE INDEX IF NOT EXISTS idx_fact_type     ON fact_annonces(id_type);
CREATE INDEX IF NOT EXISTS idx_fact_source   ON fact_annonces(id_source);
CREATE INDEX IF NOT EXISTS idx_fact_prix     ON fact_annonces(prix);
CREATE INDEX IF NOT EXISTS idx_fact_date     ON fact_annonces(date_scraping);

-- ==============================================================================
-- VUES ANALYTIQUES POUR POWER BI
-- ==============================================================================
CREATE OR REPLACE VIEW v_dashboard_kpis AS
SELECT 
    f.id,
    f.url,
    f.titre,
    f.prix,
    f.surface_m2,
    f.nb_chambres,
    f.nb_salles_bain,
    f.date_scraping,
    l.ville,
    l.quartier,
    t.type_bien,
    s.site_source,
    -- KPIs Prédéfinis
    CASE WHEN f.surface_m2 > 0 THEN ROUND(f.prix / f.surface_m2, 2) ELSE NULL END AS prix_m2,
    (COALESCE(f.parking, 0) + COALESCE(f.ascenseur, 0) + COALESCE(f.balcon, 0) + COALESCE(f.piscine, 0) + COALESCE(f.jardin, 0)) AS score_equipements
FROM fact_annonces f
LEFT JOIN dim_localisation l ON f.id_loc = l.id_loc
LEFT JOIN dim_type_bien t ON f.id_type = t.id_type
LEFT JOIN dim_source s ON f.id_source = s.id_source;

-- ==============================================================================
-- TRACKING DES PERFORMANCES ML (Pour Power BI)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS model_metrics (
    id SERIAL PRIMARY KEY,
    date_entrainement TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modele VARCHAR(100) NOT NULL,
    r2_score NUMERIC,
    rmse NUMERIC,
    mae NUMERIC,
    lignes_entrainement INTEGER
);
CREATE TABLE IF NOT EXISTS model_epochs (
    id         SERIAL PRIMARY KEY,
    run_at     TIMESTAMP DEFAULT NOW(),
    modele     TEXT,
    run_mode   TEXT,
    epoch      INTEGER,
    n_trees    INTEGER,
    accuracy   FLOAT,   -- R² sur le test à cet epoch
    loss       FLOAT    -- RMSE sur le test à cet epoch
);