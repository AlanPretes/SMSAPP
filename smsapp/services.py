# smsapp/services.py

import subprocess
import time
import shlex
import threading
from datetime import datetime, timedelta
import re
import os
from django_q.tasks import async_task

from django.utils import timezone
from smsapp.models import SmsQueue, SmsProcessing, SmsFailed, SmsSent

from django_q.tasks import schedule
from django_q.models import Schedule

os.environ.setdefault("adb", r"C:\adb\adb.exe")
adb_path = os.environ.get("adb")

def run():
    obj_sms = SmsQueue.objects.all().order_by('created_at')[:15]

    for sms in obj_sms:
        send_sms_via_adb(sms)

def send_sms_via_adb(obj_sms):
    phone = obj_sms.phone
    message = obj_sms.message
    """
    Envia a mensagem via ADB e retorna (thread_id, sms_id) se o SMS sumir dos logs (envio concluído)
    ou (None, None) se o SMS continuar nos logs (falha no envio).
    """
    message_escaped = shlex.quote(message)
    comando_adb = (
        f'{adb_path} shell am start -a android.intent.action.SENDTO -d "sms:{phone}" '
        f'--es "sms_body" {message_escaped} --ez exit_on_sent true'
    )
    subprocess.run(comando_adb)
    time.sleep(1)  # tempo para abrir o app de SMS

    # Toca no botão "Enviar"
    x, y = 999, 2137
    subprocess.run([adb_path, 'shell', 'input', 'tap', str(x), str(y)])
    time.sleep(2)  # tempo para o SMS ser registrado nos logs

    # Captura inicial do SMS nos logs
    sms_id_inicial = get_last_inserted_id_for_message(str(phone), str(message))
    print(sms_id_inicial)
    
    if sms_id_inicial:
        print("Tentativa de envio SMS criado!")
        return sms_id_inicial

    print("Falha no envio")
    return None 

def get_last_inserted_id_for_message(phone, message):
    """
    Retorna o SMS_ID do último SMS enviado nos últimos 10 segundos para o número e mensagem fornecidos.
    Se não encontrar, retorna None.
    """
    # Escapar aspas simples para evitar problemas no comando
    safe_message = message.replace("'", "\\'")
    safe_phone = phone.replace("'", "\\'")

    # Montar o comando correto
    comando = (
        f'{adb_path} shell "content query --uri content://sms/sent '
        f'--projection _id,body,date,address --where \\"body=\'{safe_message}\' AND address=\'{safe_phone}\'\\""'
    )

    # Executar o comando
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)

    # Exibir o resultado bruto para depuração
    print("Resultado do comando ADB:\n", resultado.stdout)

    # Verificar se há saída válida
    if not resultado.stdout.strip():
        print("Nenhum resultado encontrado.")
        return None

    # Calcular o limite de tempo (últimos 10 segundos)
    agora = datetime.now()

    # Inicializar o ID e o timestamp do SMS mais recente
    sms_id_mais_recente = None
    data_mais_recente = datetime.min

    # Percorrer todas as linhas para encontrar o SMS válido mais recente
    for linha in resultado.stdout.splitlines():
        match = re.search(r'_id=(\d+), body=(.*?), date=(\d+), address=([\+\d]+)', linha)
        if match:
            sms_id = int(match.group(1))
            body = match.group(2)
            date_millis = int(match.group(3))  # Timestamp em milissegundos
            address = match.group(4)

            # Converter o timestamp para datetime
            data_sms = datetime.fromtimestamp(date_millis / 1000)
            print(data_sms)
            print(data_mais_recente)
            print((agora - data_sms).total_seconds())
            print(f"SMS encontrado no smartphone: ID={sms_id}, Data={data_sms}, Mensagem='{body}'")

            # Verificar se o SMS foi enviado nos últimos 10 segundos
            if (agora - data_sms).total_seconds() < 15:
                sms_id_mais_recente = sms_id
                data_mais_recente = data_sms
                break

    if sms_id_mais_recente:
        print(f"Última tentativa de envio de SMS nos últimos 10 segundos: ID={sms_id_mais_recente}, Data={data_mais_recente}")
        return sms_id_mais_recente
    else:
        print("Nenhuma tentantiva de SMS encontrado nos últimos 10 segundos.")
        return None
    
    
    
    
