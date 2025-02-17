#!/usr/bin/env python
import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    # Se o comando for 'runserver', iniciamos Django, depois importamos background
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        import django
        django.setup()  # Inicializa o Django (carrega Apps)

        print("[manage.py] Iniciando thread de processamento em background...")

        from threading import Thread
        from smsapp.background import run_background_processor

        t = Thread(target=run_background_processor, daemon=True)
        t.start()

    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
