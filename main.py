#!/usr/bin/env python3
import os
import sys
import json
import time
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
        """Aggiunge una nuova istanza alla configurazione."""
        print(f"\n{Fore.CYAN}=== Aggiungi Nuova Istanza ==={Style.RESET_ALL}")
        
        questions = [
            inquirer.List('action',
                         message="Nome istanza",
                         choices=[
                             ('Inserisci nome istanza', 'continue'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        action = inquirer.prompt(questions)
        if not action or action['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return

        name_question = [
            inquirer.Text('name', message="Nome istanza")
        ]
        name_answer = inquirer.prompt(name_question)
        if not name_answer:
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return
        
        hostname_question = [
            inquirer.List('action',
                         message="Hostname",
                         choices=[
                             ('Inserisci hostname', 'continue'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        action = inquirer.prompt(hostname_question)
        if not action or action['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return

        hostname_input = [
            inquirer.Text('hostname', message="Hostname")
        ]
        hostname_answer = inquirer.prompt(hostname_input)
        if not hostname_answer:
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return

        username_question = [
            inquirer.List('action',
                         message="Username",
                         choices=[
                             ('Inserisci username', 'continue'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        action = inquirer.prompt(username_question)
        if not action or action['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return

        username_input = [
            inquirer.Text('username', message="Username")
        ]
        username_answer = inquirer.prompt(username_input)
        if not username_answer:
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return
        
        port_question = [
            inquirer.List('action',
                         message="Porta",
                         choices=[
                             ('Usa porta default (22)', 'default'),
                             ('Specifica porta personalizzata', 'custom'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        port_action = inquirer.prompt(port_question)
        if not port_action or port_action['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return
        
        if port_action['action'] == 'custom':
            port_input = [
                inquirer.Text('port', message="Porta", default="22")
            ]
            port_answer = inquirer.prompt(port_input)
            if not port_answer:
                print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
                return
            port = int(port_answer['port'])
        else:
            port = 22
        
        key_question = [
            inquirer.List('action',
                         message="Chiave SSH",
                         choices=[
                             ('Usa chiave SSH', 'use_key'),
                             ('Non usare chiave SSH', 'no_key'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        key_action = inquirer.prompt(key_question)
        if not key_action or key_action['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return
        
        if key_action['action'] == 'use_key':
            key_path_question = [
                inquirer.List('action',
                             message="Percorso chiave SSH",
                             choices=[
                                 ('Usa percorso default (~/.ssh/id_ed25519)', 'default'),
                                 ('Specifica percorso personalizzato', 'custom'),
                                 ('Annulla', 'cancel')
                             ])
            ]
            
            key_path_action = inquirer.prompt(key_path_question)
            if not key_path_action or key_path_action['action'] == 'cancel':
                print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
                return
            
            if key_path_action['action'] == 'custom':
                key_path_input = [
                    inquirer.Path(
                        'key_path',
                        message="Percorso della chiave privata",
                        exists=True,
                        path_type=inquirer.Path.FILE
                    )
                ]
                key_path_answer = inquirer.prompt(key_path_input)
                if not key_path_answer:
                    print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
                    return
                key_path = key_path_answer['key_path']
            else:
                key_path = os.path.expanduser("~/.ssh/id_ed25519")
        else:
            key_path = None

        # Conferma finale
        print("\nRiepilogo configurazione:")
        print(f"Nome: {name_answer['name']}")
        print(f"Hostname: {hostname_answer['hostname']}")
        print(f"Username: {username_answer['username']}")
        print(f"Porta: {port}")
        if key_path:
            print(f"Chiave SSH: {key_path}")
        
        confirm_question = [
            inquirer.List('action',
                         message="Confermi la creazione dell'istanza?",
                         choices=[
                             ('Conferma', 'confirm'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        confirm = inquirer.prompt(confirm_question)
        if not confirm or confirm['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return

        self.instances[name_answer['name']] = {
            "hostname": hostname_answer['hostname'],
            "username": username_answer['username'],
            "port": port,
            "key_path": key_path
        }
        
        print(f"\n{Fore.GREEN}Istanza '{name_answer['name']}' aggiunta con successo!{Style.RESET_ALL}")
        self._print_ssh_command(name_answer['name'])
        self.save_config()

    def edit_instance(self) -> None:
        """Modifica un'istanza esistente."""
        if not self.instances:
            print(f"\n{Fore.YELLOW}Nessuna istanza da modificare.{Style.RESET_ALL}")
            return

        # Seleziona l'istanza da modificare
        instance_choices = list(self.instances.keys())
        instance_choices.append('Annulla')
        
        instance_question = [
            inquirer.List('instance',
                         message="Seleziona l'istanza da modificare",
                         choices=instance_choices)
        ]
        
        instance_answer = inquirer.prompt(instance_question)
        if not instance_answer or instance_answer['instance'] == 'Annulla':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return

        instance_name = instance_answer['instance']
        current_instance = self.instances[instance_name]

        print(f"\n{Fore.CYAN}=== Modifica Istanza: {instance_name} ==={Style.RESET_ALL}")
        
        # Hostname
        hostname_question = [
            inquirer.List('action',
                         message=f"Hostname attuale: {current_instance['hostname']}",
                         choices=[
                             ('Mantieni valore attuale', 'keep'),
                             ('Modifica', 'edit'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        hostname_action = inquirer.prompt(hostname_question)
        if not hostname_action or hostname_action['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return
        
        if hostname_action['action'] == 'edit':
            hostname_input = [
                inquirer.Text('hostname', 
                            message="Nuovo hostname",
                            default=current_instance['hostname'])
            ]
            hostname_answer = inquirer.prompt(hostname_input)
            if not hostname_answer:
                print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
                return
            new_hostname = hostname_answer['hostname']
        else:
            new_hostname = current_instance['hostname']
        
        # Username
        username_question = [
            inquirer.List('action',
                         message=f"Username attuale: {current_instance['username']}",
                         choices=[
                             ('Mantieni valore attuale', 'keep'),
                             ('Modifica', 'edit'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        username_action = inquirer.prompt(username_question)
        if not username_action or username_action['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return
        
        if username_action['action'] == 'edit':
            username_input = [
                inquirer.Text('username', 
                            message="Nuovo username",
                            default=current_instance['username'])
            ]
            username_answer = inquirer.prompt(username_input)
            if not username_answer:
                print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
                return
            new_username = username_answer['username']
        else:
            new_username = current_instance['username']
        
        # Porta
        port_question = [
            inquirer.List('action',
                         message=f"Porta attuale: {current_instance['port']}",
                         choices=[
                             ('Mantieni valore attuale', 'keep'),
                             ('Modifica', 'edit'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        port_action = inquirer.prompt(port_question)
        if not port_action or port_action['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return
        
        if port_action['action'] == 'edit':
            port_input = [
                inquirer.Text('port', 
                            message="Nuova porta",
                            default=str(current_instance['port']))
            ]
            port_answer = inquirer.prompt(port_input)
            if not port_answer:
                print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
                return
            new_port = int(port_answer['port'])
        else:
            new_port = current_instance['port']
        
        # Chiave SSH
        key_question = [
            inquirer.List('action',
                         message=f"Chiave SSH attuale: {current_instance.get('key_path', 'Nessuna')}",
                         choices=[
                             ('Mantieni valore attuale', 'keep'),
                             ('Modifica', 'edit'),
                             ('Rimuovi chiave', 'remove'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        key_action = inquirer.prompt(key_question)
        if not key_action or key_action['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return
        
        if key_action['action'] == 'edit':
            key_path_input = [
                inquirer.Path(
                    'key_path',
                    message="Nuovo percorso della chiave privata",
                    exists=True,
                    path_type=inquirer.Path.FILE,
                    default=current_instance.get('key_path', os.path.expanduser("~/.ssh/id_ed25519"))
                )
            ]
            key_path_answer = inquirer.prompt(key_path_input)
            if not key_path_answer:
                print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
                return
            new_key_path = key_path_answer['key_path']
        elif key_action['action'] == 'remove':
            new_key_path = None
        else:
            new_key_path = current_instance.get('key_path')

        # Riepilogo modifiche
        print("\nRiepilogo modifiche:")
        print(f"Hostname: {new_hostname}")
        print(f"Username: {new_username}")
        print(f"Porta: {new_port}")
        print(f"Chiave SSH: {new_key_path or 'Nessuna'}")
        
        # Conferma finale
        confirm_question = [
            inquirer.List('action',
                         message="Confermi le modifiche?",
                         choices=[
                             ('Conferma', 'confirm'),
                             ('Annulla', 'cancel')
                         ])
        ]
        
        confirm = inquirer.prompt(confirm_question)
        if not confirm or confirm['action'] == 'cancel':
            print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
            return

        # Aggiorna l'istanza
        self.instances[instance_name] = {
            "hostname": new_hostname,
            "username": new_username,
            "port": new_port,
            "key_path": new_key_path
        }
        
        self.save_config()
        print(f"\n{Fore.GREEN}Istanza '{instance_name}' modificata con successo!{Style.RESET_ALL}")
        self._print_ssh_command(instance_name)


    def delete_instance(self) -> None:
        """Elimina un'istanza esistente."""
        if not self.instances:
            print(f"\n{Fore.YELLOW}Nessuna istanza da eliminare.{Style.RESET_ALL}")
            return

        # Seleziona l'istanza da eliminare
        instance_question = [
            inquirer.List('instance',
                         message="Seleziona l'istanza da eliminare",
                         choices=list(self.instances.keys()))
        ]
        instance_answer = inquirer.prompt(instance_question)
        if not instance_answer:
            return

        instance_name = instance_answer['instance']

        # Chiedi conferma
        confirm_question = [
            inquirer.Confirm('confirm',
                           message=f"Sei sicuro di voler eliminare l'istanza '{instance_name}'?",
                           default=False)
        ]
        confirm_answer = inquirer.prompt(confirm_question)

        if confirm_answer and confirm_answer['confirm']:
            del self.instances[instance_name]
            self.save_config()
            print(f"\n{Fore.GREEN}Istanza '{instance_name}' eliminata con successo!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}Eliminazione annullata.{Style.RESET_ALL}")

    def _print_ssh_command(self, instance_name: str) -> None:
        """Utility per stampare il comando SSH equivalente."""
        instance = self.instances[instance_name]
        print(f"\n{Fore.CYAN}Comando SSH equivalente:{Style.RESET_ALL}")
        if instance.get('key_path'):
            cmd = f"ssh -i {instance['key_path']} {instance['username']}@{instance['hostname']}"
            if instance['port'] != 22:
                cmd += f" -p {instance['port']}"
        else:
            cmd = f"ssh {instance['username']}@{instance['hostname']}"
            if instance['port'] != 22:
                cmd += f" -p {instance['port']}"
        print(f"{Fore.YELLOW}{cmd}{Style.RESET_ALL}")

    def list_instances(self) -> List[str]:
        os.system('clear')
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
            
            self._print_ssh_command(name)
            print(f"{Fore.CYAN}{'-' * 30}{Style.RESET_ALL}")
        
        return list(self.instances.keys())

    def connect_to_instance(self, name: str) -> None:
        if name not in self.instances:
            print(f"\n{Fore.RED}Errore: Istanza '{name}' non trovata.{Style.RESET_ALL}")
            return

        instance = self.instances[name]
        
        try:
            import subprocess
            
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
                             ('Modifica istanza', 'edit'),
                             ('Elimina istanza', 'delete'),
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
        elif answers['action'] == 'edit':
            os.system('clear')
            manager.edit_instance()
        elif answers['action'] == 'delete':
            os.system('clear')
            manager.delete_instance()
        elif answers['action'] == 'connect':
            os.system('clear')
            instance_list = manager.list_instances()
            if instance_list:
                instance_question = [
                    inquirer.List('instance',
                                message="Seleziona l'istanza a cui connettersi",
                                choices=instance_list + [('Annulla', 'cancel')]
                                )
                ]
                instance_answer = inquirer.prompt(instance_question)
                if instance_answer['instance'] != 'cancel':
                    manager.connect_to_instance(instance_answer['instance'])
                if instance_answer['instance'] == 'cancel':
                    print(f"\n{Fore.YELLOW}Operazione annullata.{Style.RESET_ALL}")
                    time.sleep(1)
                    os.system('clear')
        elif answers['action'] == 'exit':
            print(f"\n{Fore.YELLOW}Arrivederci!{Style.RESET_ALL}")
            break

if __name__ == "__main__":
    main()