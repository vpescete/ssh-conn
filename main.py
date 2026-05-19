#!/usr/bin/env python3
"""Entry-point shim — delega a ssh_conn.cli.run().

Permette di avviare il tool con `python main.py` dalla directory del progetto
senza richiedere l'install via pip.
"""
from ssh_conn.cli import run

if __name__ == "__main__":
    run()
