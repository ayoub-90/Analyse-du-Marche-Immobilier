CREATE TABLE IF NOT EXISTS annonces (
    id              SERIAL PRIMARY KEY,
    id_annonce      VARCHAR(100) UNIQUE,   -- prevents duplicates
    source          VARCHAR(20),            -- 'Avito' or 'Mubawab'
    url             TEXT UNIQUE,
    titre           TEXT,
    prix            NUMERIC,
    ville           VARCHAR(100),
    type_bien       VARCHAR(50),
    surface_m2      INTEGER,
    nb_chambres     VARCHAR(10),
    nb_salles_bain  VARCHAR(10),
    etage           VARCHAR(20),
    parking         SMALLINT,
    ascenseur       SMALLINT,
    balcon          SMALLINT,
    piscine         SMALLINT,
    jardin          SMALLINT,
    description     TEXT,
    date_scraping   DATE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ville      ON annonces(ville);
CREATE INDEX IF NOT EXISTS idx_type_bien  ON annonces(type_bien);
CREATE INDEX IF NOT EXISTS idx_prix       ON annonces(prix);
CREATE INDEX IF NOT EXISTS idx_source     ON annonces(source);
CREATE INDEX IF NOT EXISTS idx_date       ON annonces(date_scraping);