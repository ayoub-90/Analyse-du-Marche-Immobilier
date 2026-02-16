@echo off
SETLOCAL EnableDelayedExpansion

:: --- CONFIGURATION ---
SET "ROOT_NAME=analyse-immobilier-maroc"

echo [1/3] Creation de la structure des dossiers pour : %ROOT_NAME%

:: Dossiers principaux
mkdir data
mkdir data\raw
mkdir data\processed
mkdir data\final

mkdir docs
mkdir docs\img

mkdir notebooks

mkdir src
mkdir src\scripts
mkdir src\scripts\extraction
mkdir src\scripts\cleaning
mkdir src\scripts\analysis

mkdir airflow
mkdir airflow\dags
mkdir airflow\plugins

mkdir sql
mkdir sql\schema
mkdir sql\queries

mkdir tests

mkdir reports
mkdir reports\viz

:: --- CREATION DES FICHIERS DE BASE ---
echo [2/3] Creation des fichiers initiaux...

:: Fichier .gitignore
(
echo .venv/
echo __pycache__/
echo .env
echo data/raw/*
echo data/processed/*
echo data/final/*
echo *.log
echo .DS_Store
) > .gitignore

:: Fichier requirements.txt (Basé sur vos besoins identifiés)
(
echo pandas
echo numpy
echo beautifulsoup4
echo selenium
echo sqlalchemy
echo psycopg2-binary
echo apache-airflow
echo matplotlib
echo seaborn
echo plotly
echo python-dotenv
) > requirements.txt

:: Fichier README.md
(
echo # Analyse du Marche Immobilier au Maroc
echo.
echo ## 📌 Description
echo Projet Fil Rouge Data Analyst visant a analyser les tendances du marche immobilier marocain via le scraping et l'automatisation.
echo.
echo ## 🛠️ Installation
echo 1. Cloner le depot
echo 2. Installer les dependances : `pip install -r requirements.txt`
echo.
echo ## 📂 Structure
echo - `src/`: Scripts Python ^(Extraction, Cleaning^)
echo - `airflow/`: Orchestration des pipelines
echo - `sql/`: Scripts de creation de base de donnees ^(Medallion Architecture^)
echo - `notebooks/`: Analyses exploratoires ^(EDA^)
) > README.md

:: Création de fichiers __init__.py pour transformer les dossiers en packages python

echo [3/3] Termine ! La structure est prete.
pause