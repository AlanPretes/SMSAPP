import time
import threading

from django.utils import timezone
from smsapp.models import SmsQueue, SmsProcessing, SmsSent, SmsFailed
from smsapp.services import send_sms_via_adb

# Podemos usar um flag global para parar a thread graciosamente, se quiser
stop_processing = False

def run_background_processor():
    """
    Loop infinito que:
      1. Lê da tabela de fila (SmsQueue).
      2. Move para SmsProcessing.
      3. Envia via ADB.
      4. Se sucesso, move para SmsSent; se falha, move para SmsFailed.
    """
    print("Iniciando processador de SMS em segundo plano... Ctrl+C para encerrar.")
    while not stop_processing:
        sms_in_queue = SmsQueue.objects.first()
        if sms_in_queue:
            # Mover para PROCESSING
            processing = SmsProcessing.objects.create(
                phone=sms_in_queue.phone,
                message=sms_in_queue.message
            )
            sms_in_queue.delete()

            # Tentar enviar
            thread_id, new_id = send_sms_via_adb(processing.phone, processing.message)
            if new_id is None:
                # Falha: mover para Failed
                SmsFailed.objects.create(
                    phone=processing.phone,
                    message=processing.message,
                    error_code=999,  # Exemplo de "erro genérico"
                )
                print(f"[BackgroundProcessor] Falha ao enviar SMS para {processing.phone}")
                processing.delete()
            else:
                # Sucesso: mover para Sent
                processing.thread_id = thread_id
                processing.sms_id = new_id
                processing.save()

                SmsSent.objects.create(
                    phone=processing.phone,
                    message=processing.message,
                    thread_id=processing.thread_id,
                    sms_id=processing.sms_id
                )
                print(f"[BackgroundProcessor] SMS enviado com sucesso para {processing.phone}")
                processing.delete()
        time.sleep(3)  # Aguarda 3s entre cada tentativa
