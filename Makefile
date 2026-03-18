# ============================================================================
# Makefile - Projet Scraping Immobilier Maroc
# ============================================================================

.PHONY: help install docker-up docker-down logs test scrape clean

# Couleurs
BLUE=\033[0;34m
GREEN=\033[0;32m
RED=\033[0;31m
NC=\033[0m # No Color

help: ## Affiche cette aide
	@echo "$(BLUE)Commandes disponibles:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Installer les dépendances Python
	@echo "$(BLUE)Installation des dépendances...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)✓ Installation terminée$(NC)"

setup: ## Créer la structure de dossiers
	@echo "$(BLUE)Création de la structure...$(NC)"
	mkdir -p data/raw/{avito,mubawab} data/processed data/stats
	mkdir -p logs airflow/{dags,logs,plugins}
	mkdir -p src/{scrapers,processing,utils}
	@echo "$(GREEN)✓ Structure créée$(NC)"

docker-build: ## Build les images Docker
	@echo "$(BLUE)Build des images Docker...$(NC)"
	docker-compose build
	@echo "$(GREEN)✓ Build terminé$(NC)"

docker-up: ## Démarrer tous les services Docker
	@echo "$(BLUE)Démarrage des services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services démarrés$(NC)"
	@echo "Airflow UI: http://localhost:8080"
	@echo "PgAdmin: http://localhost:5050"

docker-down: ## Arrêter tous les services Docker
	@echo "$(BLUE)Arrêt des services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services arrêtés$(NC)"

docker-restart: docker-down docker-up ## Redémarrer tous les services

logs: ## Afficher les logs Airflow
	docker-compose logs -f airflow-scheduler

logs-avito: ## Afficher les logs du scraper Avito
	tail -f logs/avito_scraper.log

logs-mubawab: ## Afficher les logs du scraper Mubawab
	tail -f logs/mubawab_scraper.log

scrape-avito: ## Lancer scraper Avito (local)
	@echo "$(BLUE)Scraping Avito...$(NC)"
	python src/scrapers/avito_scraper.py
	@echo "$(GREEN)✓ Scraping Avito terminé$(NC)"

scrape-mubawab: ## Lancer scraper Mubawab (local)
	@echo "$(BLUE)Scraping Mubawab...$(NC)"
	python src/scrapers/mubawab_scraper.py
	@echo "$(GREEN)✓ Scraping Mubawab terminé$(NC)"

combine: ## Combiner les données
	@echo "$(BLUE)Combinaison des données...$(NC)"
	python src/processing/data_combiner.py
	@echo "$(GREEN)✓ Combinaison terminée$(NC)"

pipeline: scrape-avito scrape-mubawab combine ## Lancer le pipeline complet

test: ## Lancer les tests
	@echo "$(BLUE)Exécution des tests...$(NC)"
	pytest tests/ -v
	@echo "$(GREEN)✓ Tests terminés$(NC)"

clean: ## Nettoyer les fichiers temporaires
	@echo "$(BLUE)Nettoyage...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete
	@echo "$(GREEN)✓ Nettoyage terminé$(NC)"

clean-data: ## Supprimer toutes les données (ATTENTION)
	@echo "$(RED)⚠️  Suppression de toutes les données...$(NC)"
	@read -p "Êtes-vous sûr? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf data/raw/* data/processed/* data/stats/*; \
		echo "$(GREEN)✓ Données supprimées$(NC)"; \
	else \
		echo "Annulé"; \
	fi

ps: ## Afficher l'état des services Docker
	docker-compose ps

shell-airflow: ## Entrer dans le container Airflow
	docker exec -it immobilier_airflow_scheduler bash

shell-postgres: ## Entrer dans PostgreSQL
	docker exec -it immobilier_postgres psql -U airflow

trigger-dag: ## Trigger le DAG Airflow manuellement
	docker exec immobilier_airflow_scheduler airflow dags trigger immobilier_maroc_pipeline

list-dags: ## Lister les DAGs Airflow
	docker exec immobilier_airflow_scheduler airflow dags list

stats: ## Afficher les statistiques du dernier run
	@echo "$(BLUE)Statistiques:$(NC)"
	@python -c "import pandas as pd; import glob; files = glob.glob('data/processed/*.csv'); \
	if files: df = pd.read_csv(max(files)); \
	print(f'\nTotal: {len(df)} annonces'); \
	print(f'\nPar source:\n{df[\"source\"].value_counts()}'); \
	print(f'\nPar type:\n{df[\"type_bien\"].value_counts()}'); \
	print(f'\nTop villes:\n{df[\"ville\"].value_counts().head()}'); \
	else: print('Aucune donnée trouvée')"

backup: ## Backup des données
	@echo "$(BLUE)Backup des données...$(NC)"
	tar -czf backup_$(shell date +%Y%m%d_%H%M%S).tar.gz data/
	@echo "$(GREEN)✓ Backup créé$(NC)"

# Default
.DEFAULT_GOAL := help