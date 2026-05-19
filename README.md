# ssh-conn

CLI Python per gestire connessioni SSH a molte istanze cloud con tabella raggruppata, fuzzy search, health check parallelo, CLI args e import da `~/.ssh/config`.

## Caratteristiche

- **Tabella raggruppata** per provider (OVH, GCP, CL, OVS, Odoo, Buyprotect, other) con colori `rich`.
- **Auto-detect** di gruppo e tag dal nome dell'istanza (es. `OVH - blendX Demo` → gruppo `OVH`, tag `blendx demo`). Nessuna migrazione del JSON richiesta.
- **Fuzzy search** su nome, host, user e tag per connessione rapida tra decine di istanze.
- **Sezione "Recenti"** in cima alla lista: le ultime istanze a cui ti sei connesso, con timestamp relativo.
- **Health check parallelo** via `asyncio.open_connection` (TCP) per vedere quali istanze rispondono prima di tentare la connessione.
- **CLI args con Typer**: `ssh-conn connect <name>`, `ssh-conn list ovh prod`, `ssh-conn health`, ecc. Senza argomenti: modalità interattiva.
- **Import da `~/.ssh/config`** per unificarsi con la configurazione SSH di sistema.
- **Installabile globalmente** via `pipx` con binario `ssh-conn` sul PATH.

## Installazione

### Opzione 1 — Globale via pipx (consigliata)

```bash
brew install pipx        # se non già installato
make install             # equivalente a: pipx install --force .
ssh-conn --help
```

Dopo l'install, `ssh-conn` è disponibile da qualsiasi directory. La config si trova automaticamente con questa priorità:

1. `--config PATH`
2. `$SSH_CONN_CONFIG`
3. `./ssh_config.json` (se presente nella cwd — retrocompatibilità)
4. `~/.config/ssh-conn/config.json` (default)

Per continuare a usare il file esistente in questo progetto:

```bash
export SSH_CONN_CONFIG=/Users/vpescetelli/ssh-conn/ssh_config.json
# oppure copia in ~/.config:
mkdir -p ~/.config/ssh-conn
cp ssh_config.json ~/.config/ssh-conn/config.json
```

### Opzione 2 — Sviluppo locale

```bash
make init           # crea .venv + dipendenze
make dev-install    # pip install -e .  (binario in .venv/bin/ssh-conn)
make start          # alternativa: python main.py (modalità interattiva)
```

## Uso

### Modalità interattiva

```bash
ssh-conn
```

Menu principale:

```
1. Lista istanze
2. Connetti a istanza
3. Aggiungi istanza
4. Modifica istanza
5. Elimina istanza
6. Health check
7. Importa da ~/.ssh/config
q. Esci
```

### CLI args

```bash
ssh-conn connect samir              # fuzzy match → connette
ssh-conn list ovh prod              # tabella filtrata
ssh-conn list --health              # tabella + reachability
ssh-conn health                     # check parallelo su tutte
ssh-conn health ovh                 # solo OVH
ssh-conn edit "OVH - Nixie Core"    # modifica
ssh-conn delete vespa               # elimina con conferma
ssh-conn import-ssh --source ~/.ssh/config
ssh-conn config-path                # stampa il file di config in uso
ssh-conn --config /path/to/cfg.json list   # override esplicito
ssh-conn --help                     # vedi tutti i subcomandi
```

### Filtri

Il filtro è case-insensitive e funziona come AND su tutti i termini, cercando in:
- nome istanza
- hostname
- username
- gruppo (OVH/GCP/CL/...)
- tag

Esempi:
- `list ovh` → tutte le OVH
- `list blendx prod` → tutte quelle con blendX e prod
- `list ubuntu` → tutte quelle con utente ubuntu

### Fuzzy connect

`ssh-conn connect <query>` risolve in ordine:
1. Match esatto sul nome.
2. Match case-insensitive.
3. Substring univoco.
4. Match ambiguo → mostra i candidati e annulla.

Esempi: `samir`, `nixie core`, `blendx demo`.

## Struttura

```
ssh-conn/
├── main.py                # entry-point shim (legacy: python main.py)
├── pyproject.toml         # metadata + entry point ssh-conn
├── requirements.txt       # dipendenze dev
├── Makefile               # init / start / install / dev-install / clean
├── ssh_config.json        # config istanze locale (gitignored)
└── ssh_conn/              # package
    ├── __init__.py
    ├── __main__.py        # python -m ssh_conn
    ├── cli.py             # Typer CLI app
    ├── commands.py        # business logic (interactive + by-name)
    ├── store.py           # SSHInstance + JSON + auto-detect tag
    ├── ui.py              # rich rendering + prompt_toolkit
    ├── history.py         # tracking ultimo accesso
    ├── health.py          # async TCP reachability
    └── ssh_import.py      # parser ~/.ssh/config
```

## Storage

- **Istanze**: vedi la priorità nella sezione Installazione. Schema JSON:
  ```json
  {
    "Nome istanza": {
      "hostname": "1.2.3.4",
      "username": "ubuntu",
      "port": 22,
      "key_path": "/Users/.../.ssh/id_ed25519"
    }
  }
  ```
  I campi `group` e `tags` sono derivati in-memory dal nome — non vengono persistiti.

- **History**: `~/.config/ssh-conn/history.json` (timestamp ISO per ogni nome). Override con `SSH_CONN_HISTORY=/path/to/history.json`.

## Health check

Tenta una connessione TCP (non SSH) sulla porta configurata con timeout di 1.5s, in parallelo via `asyncio`.

- `●` verde: porta aperta (raggiungibile).
- `●` rosso: connessione rifiutata o errore di rete.
- `●` giallo: timeout.

Su 68 istanze il check completo dura circa 2-3 secondi.

## Dipendenze

```
rich>=13.7,<14
prompt_toolkit>=3.0,<4
typer>=0.12,<1
```

Niente `paramiko`: la connessione SSH passa per `subprocess` chiamando il binario `ssh` di sistema.

## Limitazioni note

- L'import da `~/.ssh/config` ignora pattern wildcard (`Host *`).
- L'auto-detect di gruppo cerca il prefisso noto solo all'inizio del nome (es. `Schalcon GCP` finisce in `other`, non in `GCP`).
- Su terminali senza TTY (script/pipe) `prompt_toolkit` mostra un warning ma resta funzionante per i comandi non interattivi.

## Disinstallazione

```bash
make uninstall      # pipx uninstall ssh-conn
make clean          # rimuove .venv, build/, dist/, *.egg-info
```
