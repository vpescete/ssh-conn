#!/usr/bin/env python3
import os
import sys
import json
import paramiko
import getpass
import inquirer
import select
import termios
import tty
from typing import Dict, List
from inquirer import themes
from colorama import init, Fore, Style

# Inizializza colorama per il supporto dei colori su Windows
init()

class SSHManager:
    def __init__(self, config_file: str = "ssh_config.json"):
        self.config_file = config_file
        self.instances = self.load_config()

    def load_config(self) -> Dict:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {}

    def save_config(self) -> None:
        with open(self.config_file, 'w') as f:
            json.dump(self.instances, f, indent=4)

    def add_instance(self) -> None:
        print(f"\n{Fore.CYAN}=== Aggiungi Nuova Istanza ==={Style.RESET_ALL}")
        
        questions = [
            inquirer.Text('name', message="Nome istanza"),
            inquirer.Text('hostname', message="Hostname"),
            inquirer.Text('username', message="Username"),
            inquirer.Confirm('custom_port', message="Vuoi specificare una porta personalizzata?", default=False),
            inquirer.Confirm('use_key', message="Vuoi utilizzare una chiave privata SSH?", default=True),
        ]
        
        answers = inquirer.prompt(questions)
        
        if answers.get('custom_port'):
            port_question = [
                inquirer.Text('port', message="Porta", default="22")
            ]
            port_answer = inquirer.prompt(port_question)
            port = int(port_answer['port'])
        else:
            port = 22
        
        if answers.get('use_key'):
            key_path_question = [
                inquirer.Path(
                    'key_path',
                    message="Percorso della chiave privata",
                    exists=True,
                    path_type=inquirer.Path.FILE,
                    default=os.path.expanduser("~/.ssh/id_ed25519")
                )
            ]
            key_answer = inquirer.prompt(key_path_question)
            key_path = key_answer.get('key_path')
        else:
            key_path = None

        self.instances[answers['name']] = {
            "hostname": answers['hostname'],
            "username": answers['username'],
            "port": port,
            "key_path": key_path
        }
        
        print(f"\n{Fore.GREEN}Istanza '{answers['name']}' aggiunta con successo!{Style.RESET_ALL}")
        print(f"\n{Fore.CYAN}Comando SSH equivalente:{Style.RESET_ALL}")
        if key_path:
            cmd = f"ssh -i {key_path} {answers['username']}@{answers['hostname']}"
            if port != 22:
                cmd += f" -p {port}"
        else:
            cmd = f"ssh {answers['username']}@{answers['hostname']}"
            if port != 22:
                cmd += f" -p {port}"
        print(f"{Fore.YELLOW}{cmd}{Style.RESET_ALL}")
        
        self.save_config()

    def list_instances(self) -> List[str]:
        if not self.instances:
            print(f"\n{Fore.YELLOW}Nessuna istanza configurata.{Style.RESET_ALL}")
            return []

        print(f"\n{Fore.CYAN}=== Istanze Disponibili ==={Style.RESET_ALL}")
        for name, details in self.instances.items():
            print(f"\n{Fore.WHITE}Nome: {Fore.GREEN}{name}{Style.RESET_ALL}")
            print(f"Hostname: {details['hostname']}")
            print(f"Username: {details['username']}")
            if details['port'] != 22:
                print(f"Porta: {details['port']}")
            if details.get('key_path'):
                print(f"Chiave SSH: {details['key_path']}")
            
            if details.get('key_path'):
                cmd = f"ssh -i {details['key_path']} {details['username']}@{details['hostname']}"
                if details['port'] != 22:
                    cmd += f" -p {details['port']}"
            else:
                cmd = f"ssh {details['username']}@{details['hostname']}"
                if details['port'] != 22:
                    cmd += f" -p {details['port']}"
            print(f"Comando: {Fore.YELLOW}{cmd}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'-' * 30}{Style.RESET_ALL}")
        
        return list(self.instances.keys())

    def connect_to_instance(self, name: str) -> None:
        if name not in self.instances:
            print(f"\n{Fore.RED}Errore: Istanza '{name}' non trovata.{Style.RESET_ALL}")
            return

        instance = self.instances[name]
        
        try:
            # Invece di usare paramiko, eseguiamo direttamente il comando ssh
            import subprocess
            
            # Costruiamo il comando ssh
            if instance.get('key_path'):
                cmd = ['ssh']
                if instance['port'] != 22:
                    cmd.extend(['-p', str(instance['port'])])
                cmd.extend([
                    '-i', instance['key_path'],
                    f"{instance['username']}@{instance['hostname']}"
                ])
            else:
                cmd = ['ssh']
                if instance['port'] != 22:
                    cmd.extend(['-p', str(instance['port'])])
                cmd.append(f"{instance['username']}@{instance['hostname']}")

            print(f"\n{Fore.YELLOW}Connessione in corso...{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Esecuzione comando: {' '.join(cmd)}{Style.RESET_ALL}")
            
            # Esegui il comando ssh come subprocess
            process = subprocess.run(cmd)
            
            if process.returncode != 0:
                print(f"\n{Fore.RED}La connessione è terminata con codice di errore: {process.returncode}{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"\n{Fore.RED}Errore durante la connessione: {str(e)}{Style.RESET_ALL}")

def main():
    manager = SSHManager()
    os.system('clear')
    while True:
        questions = [
            inquirer.List('action',
                         message="SSH Connection Manager",
                         choices=[
                             ('Lista istanze', 'list'),
                             ('Aggiungi istanza', 'add'),
                             ('Connetti a istanza', 'connect'),
                             ('Esci', 'exit')
                         ],
                         )
        ]
        
        answers = inquirer.prompt(questions)
        if answers['action'] == 'list':
            os.system('clear')
            manager.list_instances()
        elif answers['action'] == 'add':
            os.system('clear')
            manager.add_instance()
        elif answers['action'] == 'connect':
            os.system('clear')
            instance_list = manager.list_instances()
            if instance_list:
                instance_question = [
                    inquirer.List('instance',
                                message="Seleziona l'istanza a cui connettersi",
                                choices=instance_list,
                                )
                ]
                instance_answer = inquirer.prompt(instance_question)
                os.system('clear')
                if instance_answer:
                    manager.connect_to_instance(instance_answer['instance'])
        elif answers['action'] == 'exit':
            print(f"\n{Fore.YELLOW}Arrivederci!{Style.RESET_ALL}")
            break

if __name__ == "__main__":
    main()