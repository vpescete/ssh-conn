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
	@echo "rich>=13.7,<14" > $(REQUIREMENTS)
	@echo "prompt_toolkit>=3.0,<4" >> $(REQUIREMENTS)
	@echo "typer>=0.12,<1" >> $(REQUIREMENTS)

.PHONY: init start install dev-install uninstall clean help

help:
	@echo "Comandi disponibili:"
	@echo "  make init         - Crea .venv e installa le dipendenze (dev)"
	@echo "  make start        - Avvia in modalità interattiva (richiede make init)"
	@echo "  make install      - Installa 'ssh-conn' globalmente con pipx"
	@echo "  make dev-install  - Installa in editable mode (pip install -e .)"
	@echo "  make uninstall    - Disinstalla 'ssh-conn' da pipx"
	@echo "  make clean        - Rimuove .venv e file generati"

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

install:
	@if ! command -v pipx >/dev/null 2>&1; then \
		echo "pipx non trovato. Installa con: brew install pipx"; \
		exit 1; \
	fi
	@echo "Installazione globale via pipx..."
	@pipx install --force .
	@echo ""
	@echo "Installazione completata. Esegui: ssh-conn --help"
	@echo "La config esistente in ./ssh_config.json è ancora utilizzabile con:"
	@echo "  export SSH_CONN_CONFIG=$$PWD/ssh_config.json"

dev-install:
	@if [ ! -d "$(VENV_NAME)" ]; then \
		echo "L'ambiente virtuale non esiste. Esegui 'make init' prima."; \
		exit 1; \
	fi
	@$(PIP) install -e .
	@echo "Editable install completato. Binario in $(VENV_NAME)/bin/ssh-conn"

uninstall:
	@if command -v pipx >/dev/null 2>&1; then \
		pipx uninstall ssh-conn || true; \
	fi

clean:
	@echo "Pulizia dell'ambiente..."
	@rm -rf $(VENV_NAME) build dist *.egg-info ssh_conn/__pycache__
	@echo "Pulizia completata!"
