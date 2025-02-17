# smsapp/services.py

import subprocess
import time
import shlex
import threading
from datetime import datetime

from django.utils import timezone
from smsapp.models import SmsQueue, SmsProcessing, SmsFailed, SmsSent

lock = threading.Lock()

def delete_message_by_id(sms_id):
    """
    Exclui a mensagem do celular Android, onde sms_id é o _id da mensagem.
    """
    comando = f'adb shell content delete --uri content://sms --where \"_id={sms_id}\"'
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)

    # Opcional: verificar resultado
    if resultado.returncode == 0:
        # Comando rodou com sucesso. 
        # Não há necessariamente uma confirmação formal de que foi deletado, 
        # mas se returncode=0, em geral deu certo.
        return True
    else:
        # Não foi possível deletar (talvez já não exista, 
        # ou o Android não permitiu). 
        return False

def get_message_by_id(sms_id):
    """
    Consulta o SMS pelo _id usando ADB e retorna os dados como dict.
    Retorna None se não encontrar.
    """
    comando = f'adb shell content query --uri content://sms --where \"_id={sms_id}\"'
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)

    if not resultado.stdout.strip():
        return None

    # Lê cada linha do resultado
    for line in resultado.stdout.splitlines():
        # Verifica se estamos no SMS certo
        if f'_id={sms_id}' in line:
            info = {
                'status': -1,
                'error_code': 0
            }
            # status=
            if 'status=' in line:
                try:
                    si = line.index('status=') + len('status=')
                    sc = line.find(',', si)
                    st_str = line[si:sc].strip() if sc != -1 else line[si:].strip()
                    info['status'] = int(st_str)
                except:
                    pass

            # error_code=
            if 'error_code=' in line:
                try:
                    ei = line.index('error_code=') + len('error_code=')
                    ec = line.find(',', ei)
                    err_str = line[ei:ec].strip() if ec != -1 else line[ei:].strip()
                    info['error_code'] = int(err_str)
                except:
                    pass

            return info

    return None

def normalize_number(phone):
    return ''.join(c for c in phone if c.isdigit())

def send_sms_via_adb(phone, message):
    """
    Função para enviar via ADB,
    retornando (thread_id, sms_id) ou (None, None) se falhar ao capturar o _id.
    """
    message_escaped = shlex.quote(message)
    comando_adb = (
        f'adb shell am start -a android.intent.action.SENDTO -d "sms:{phone}" '
        f'--es "sms_body" {message_escaped} --ez exit_on_sent true'
    )
    subprocess.run(comando_adb, shell=True)
    time.sleep(1)  # tempo para abrir o app de SMS

    # Tocar no botão 'Enviar'
    x, y = 999, 2137
    subprocess.run(['adb', 'shell', 'input', 'tap', str(x), str(y)])
    time.sleep(1)  # aguarda registrar

    # Tenta capturar o _id (e thread_id)
    for _ in range(3):
        sms_id, th_id = get_last_inserted_id_for_phone(phone)
        if sms_id is not None:
            return (th_id, sms_id)  # Retorna uma tupla (thread_id, sms_id)
        time.sleep(1)

    return None, None

def get_last_inserted_id_for_phone(phone):
    """
    Retorna (newest_id, best_th_id) para o número especificado,
    considerando o SMS com maior 'date'.
    """
    comando = 'adb shell content query --uri content://sms'
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)
    alvo = normalize_number(phone)

    newest_id = None
    best_th_id = None
    newest_date = -1

    for line in resultado.stdout.splitlines():
        if "address=" not in line:
            continue

        address_val = get_address_from_line(line)
        if not address_val:
            continue

        addr_norm = normalize_number(address_val)
        if addr_norm.endswith(alvo) or alvo.endswith(addr_norm):
            current_id, current_date, current_th_id = get_id_and_date_from_line(line)
            if current_id and current_date > newest_date:
                newest_id = current_id
                newest_date = current_date
                best_th_id = current_th_id

    return newest_id, best_th_id

def get_address_from_line(line):
    if "address=" not in line:
        return None
    try:
        start = line.index("address=") + len("address=")
        end = line.find(",", start)
        return line[start:end].strip() if end != -1 else line[start:].strip()
    except:
        return None

def get_id_and_date_from_line(line):
    """
    Retorna (current_id, current_date, current_th_id).
    """
    current_id = None
    current_th_id = None
    current_date = 0

    # thread_id=
    if "thread_id=" in line:
        try:
            z1 = line.index("thread_id=") + len("thread_id=")
            z2 = line.find(",", z1)
            if z2 == -1:
                current_th_id = int(line[z1:].strip())
            else:
                current_th_id = int(line[z1:z2].strip())
        except:
            pass

    # _id=
    if "_id=" in line:
        try:
            i1 = line.index("_id=") + len("_id=")
            i2 = line.find(",", i1)
            if i2 == -1:
                current_id = int(line[i1:].strip())
            else:
                current_id = int(line[i1:i2].strip())
        except:
            pass

    # date=
    if "date=" in line:
        try:
            d1 = line.index("date=") + len("date=")
            d2 = line.find(",", d1)
            if d2 == -1:
                current_date = int(line[d1:].strip())
            else:
                current_date = int(line[d1:d2].strip())
        except:
            pass

    return current_id, current_date, current_th_id
