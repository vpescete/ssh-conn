# SSH Manager

Un'applicazione Python interattiva per gestire e organizzare le connessioni SSH. Permette di salvare configurazioni SSH, modificarle e connettersi facilmente ai server remoti attraverso un'interfaccia a menu colorata.

## 🚀 Funzionalità

- ✅ Gestione delle istanze SSH (aggiungi, modifica, elimina)
- ✅ Supporto per chiavi SSH personalizzate
- ✅ Configurazione personalizzabile delle porte
- ✅ Interfaccia utente colorata e intuitiva
- ✅ Salvataggio automatico delle configurazioni
- ✅ Connessione diretta alle istanze configurate

## 📋 Prerequisiti

- Python 3.6 o superiore
- Sistema operativo: Linux, macOS, o Windows
- Accesso al terminale/command prompt

## 🔧 Installazione

### Metodo 1: Usando Makefile (Raccomandato)

Il progetto include un Makefile che automatizza l'installazione:

```bash
# Inizializza l'ambiente virtuale e installa le dipendenze
make init

# Avvia l'applicazione
make start
```

### Metodo 2: Installazione Manuale

Se preferisci installare manualmente:

```bash
# 1. Clona o scarica il progetto
git clone <repository-url>
cd ssh-manager

# 2. Crea un ambiente virtuale Python
python3 -m venv .venv

# 3. Attiva l'ambiente virtuale
# Su Linux/macOS:
source .venv/bin/activate
# Su Windows:
.venv\Scripts\activate

# 4. Installa le dipendenze
pip install -r requirements.txt

# 5. Avvia l'applicazione
python3 main.py
```

## 📁 Struttura del Progetto

```
ssh-manager/
├── main.py              # Script principale
├── requirements.txt     # Dipendenze Python
├── Makefile            # Automazione build/run
├── .gitignore          # File da ignorare in Git
└── ssh_config.json     # Configurazioni SSH (generato automaticamente)
```

## 🖥️ Utilizzo

### Avvio dell'Applicazione

```bash
make start
```

oppure:

```bash
python3 main.py
```

### Menu Principale

L'applicazione presenta un menu interattivo con le seguenti opzioni:

1. **Lista istanze**: Visualizza tutte le istanze SSH configurate
2. **Aggiungi istanza**: Crea una nuova configurazione SSH
3. **Modifica istanza**: Modifica una configurazione esistente
4. **Elimina istanza**: Rimuove una configurazione
5. **Connetti a istanza**: Stabilisce una connessione SSH
6. **Esci**: Termina l'applicazione

### Aggiunta di una Nuova Istanza

Quando aggiungi una nuova istanza, dovrai fornire:

- **Nome istanza**: Un nome identificativo (es. "Server Produzione")
- **Hostname**: L'indirizzo del server (es. "192.168.1.100" o "example.com")
- **Username**: Il nome utente per l'accesso SSH
- **Porta**: La porta SSH (default: 22)
- **Chiave SSH**: (Opzionale) Percorso alla chiave privata SSH

### Esempio di Configurazione

```json
{
  "Server Produzione": {
    "hostname": "prod.example.com",
    "username": "admin",
    "port": 22,
    "key_path": "/home/user/.ssh/id_ed25519"
  },
  "Server Test": {
    "hostname": "test.example.com",
    "username": "developer",
    "port": 2222,
    "key_path": null
  }
}
```

## 🔧 Comandi Makefile

```bash
make help    # Mostra tutti i comandi disponibili
make init    # Inizializza l'ambiente di sviluppo
make start   # Avvia l'applicazione
make clean   # Rimuove l'ambiente virtuale e i file temporanei
```

## 📦 Dipendenze

- **paramiko**: Libreria per connessioni SSH
- **inquirer**: Interfaccia interattiva per il terminale
- **colorama**: Supporto per colori nel terminale (cross-platform)

## 🔐 Gestione delle Chiavi SSH

L'applicazione supporta:

- Chiavi SSH personalizzate (specificando il percorso)
- Chiave SSH di default (`~/.ssh/id_ed25519`)
- Connessioni tramite password (senza chiave)

### Generazione di una Nuova Chiave SSH

Se non hai una chiave SSH, puoi generarla con:

```bash
ssh-keygen -t ed25519 -C "tuo-email@example.com"
```

## 🐛 Risoluzione Problemi

### Errore "L'ambiente virtuale non esiste"

```bash
make clean
make init
```

### Errore di Connessione SSH

- Verifica che l'hostname e la porta siano corretti
- Controlla che la chiave SSH abbia i permessi corretti (600)
- Assicurati che il server SSH sia in esecuzione

### Problemi con i Colori su Windows

L'applicazione usa `colorama` per garantire la compatibilità con Windows Terminal.

## 📄 File di Configurazione

Le configurazioni SSH vengono salvate automaticamente in `ssh_config.json` nella directory del progetto. Questo file viene creato automaticamente al primo utilizzo.

⚠️ **Attenzione**: Il file `ssh_config.json` è incluso nel `.gitignore` per motivi di sicurezza.

## 🤝 Contributi

Per contribuire al progetto:

1. Forka il repository
2. Crea un branch per la tua feature (`git checkout -b feature/nuova-funzionalita`)
3. Committa le tue modifiche (`git commit -am 'Aggiungi nuova funzionalità'`)
4. Pusha il branch (`git push origin feature/nuova-funzionalita`)
5. Crea una Pull Request
---

**Nota**: Assicurati di non condividere mai file di configurazione contenenti informazioni sensibili come percorsi di chiavi private o dettagli dei server.
