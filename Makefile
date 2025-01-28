# Variabili
VENV_NAME := .venv
PYTHON := python3
PIP := $(VENV_NAME)/bin/pip
PYTHON_VENV := $(VENV_NAME)/bin/python
REQUIREMENTS := requirements.txt

# Determina il sistema operativo
ifeq ($(OS),Windows_NT)
	VENV_BIN := $(VENV_NAME)/Scripts
	PYTHON_VENV := $(VENV_BIN)/python
	PIP := $(VENV_BIN)/pip
else
	VENV_BIN := $(VENV_NAME)/bin
endif

# Crea il file requirements.txt se non esiste
$(REQUIREMENTS):
	@echo "colorama" > $(REQUIREMENTS)
	@echo "inquirer" >> $(REQUIREMENTS)
	@echo "paramiko" >> $(REQUIREMENTS)

# Target principale
.PHONY: init start clean help

help:
	@echo "Comandi disponibili:"
	@echo "  make init     - Inizializza l'ambiente virtuale e installa le dipendenze"
	@echo "  make start    - Avvia l'applicazione SSH Manager"
	@echo "  make clean    - Rimuove l'ambiente virtuale e i file generati"

init: $(REQUIREMENTS)
	@echo "Creazione dell'ambiente virtuale..."
	@$(PYTHON) -m venv $(VENV_NAME)
	@echo "Installazione delle dipendenze..."
	@$(PIP) install -r $(REQUIREMENTS)
	@echo "Inizializzazione completata!"

start:
	@if [ ! -d "$(VENV_NAME)" ]; then \
		echo "L'ambiente virtuale non esiste. Esegui 'make init' prima."; \
		exit 1; \
	fi
	@echo "Avvio SSH Manager..."
	@$(PYTHON_VENV) main.py

clean:
	@echo "Pulizia dell'ambiente..."
	@rm -rf $(VENV_NAME)
	@echo "Pulizia completata!"