# smsapp/views.py

from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from smsapp.models import SmsQueue, SmsProcessing, SmsFailed, SmsSent

import time
from datetime import datetime
from smsapp.services import send_sms_via_adb, get_message_by_id, delete_message_by_id

@api_view(['POST'])
def send_and_check_sms(request):
    """
    Envia o SMS de forma síncrona e aguarda até 60s pela confirmação da operadora.
    Retorna imediatamente success/fail no response.
    """
    phone = request.data.get('phone')
    message = request.data.get('message')

    if not phone or not message:
        return Response({'error': 'Parâmetros phone e message são obrigatórios'},
                        status=status.HTTP_400_BAD_REQUEST)

    # 1) Tentar enviar via ADB e capturar _id
    thread_id, sms_id = send_sms_via_adb(phone, message)
    if sms_id is None:
        # Falha direta: não conseguimos nem capturar o _id
        SmsFailed.objects.create(
            phone=phone,
            message=message,
            thread_id=thread_id,
            sms_id=None,  # pois não veio
            error_code=999,  # erro genérico de envio
        )
        return Response({'success': False, 'detail': 'Falha ao capturar _id do SMS (envio via ADB)'}, 
                         status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 2) Registrar em SmsProcessing (opcional, para logs)
    processing = SmsProcessing.objects.create(
        phone=phone,
        message=message,
        thread_id=thread_id,
        sms_id=sms_id
    )

    # 3) Aguardar até 60 segundos verificando se foi enviado ou falhou
    start_time = datetime.now()
    timeout = 20  # segundos

    while True:
        info = get_message_by_id(sms_id)
        if not info:
            # Se sumiu do Android, é muito estranho. Marcamos como falha
            processing.delete()
            SmsFailed.objects.create(
                phone=phone,
                message=message,
                thread_id=thread_id,
                sms_id=sms_id,
                error_code=998,  # codigo de 'desapareceu'
            )
            return Response({'success': False, 'detail': 'SMS não encontrado no Android (desaparecido)'}, 
                             status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        st = info.get('status', -1)
        err = info.get('error_code', 0)

        # Se st == 0 e err == 0 => SMS confirmado pela operadora
        if st == 0 and err == 0:
            # Registrar em SmsSent, remover de Processing
            SmsSent.objects.create(
                phone=phone,
                message=message,
                thread_id=thread_id,
                sms_id=sms_id
            )
            processing.delete()

            return Response({'success': True, 'detail': 'SMS enviado com sucesso!'}, status=status.HTTP_200_OK)

        # Se operadora retornou falha => st==32 ou err!=0
        if st == 32 or err != 0:
            processing.delete()
            SmsFailed.objects.create(
                phone=phone,
                message=message,
                thread_id=thread_id,
                sms_id=sms_id,
                error_code=err
            )
            return Response({'success': False, 
                             'detail': f'Falha no envio (status={st}, erro={err})'}, 
                            status=status.HTTP_424_FAILED_DEPENDENCY)

        # Se passou 60s, damos timeout
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > timeout:
            processing.delete()
            SmsFailed.objects.create(
                phone=phone,
                message=message,
                thread_id=thread_id,
                sms_id=sms_id,
                error_code=1  # por ex., 1 = Timeout
            )
            
            # 2) Exclui a mensagem do celular
            delete_message_by_id(sms_id)
            
            return Response({'success': False, 'detail': 'Timeout de 60s sem confirmação da operadora'},
                            status=status.HTTP_408_REQUEST_TIMEOUT)

        # Espera 1 segundo antes de checar novamente
        time.sleep(1)

@api_view(['GET'])
def get_sms_history(request, phone):
    """
    Retorna um único array contendo todos os SMS (em fila, em processamento, falhos, enviados)
    para o número especificado, ordenados por data de forma decrescente (mais recentes primeiro).
    Cada item do array terá um campo 'status' identificando em qual etapa ele se encontra.
    """

    # 1) Pegar registros da fila (SmsQueue)
    queue_objs = SmsQueue.objects.filter(phone=phone).order_by('-created_at')
    queue_list = []
    for obj in queue_objs:
        queue_list.append({
            "id": obj.id,
            "phone": obj.phone,
            "message": obj.message,
            "created_at": obj.created_at,
            "thread_id": obj.thread_id,
            "sms_id": obj.sms_id,
            "status": "QUEUE",  # <-- status para esse grupo
        })

    # 2) Pegar registros em processamento (SmsProcessing)
    #    Observando que o campo de data é "started_at"
    processing_objs = SmsProcessing.objects.filter(phone=phone).order_by('-started_at')
    processing_list = []
    for obj in processing_objs:
        processing_list.append({
            "id": obj.id,
            "phone": obj.phone,
            "message": obj.message,
            "created_at": obj.started_at,  # unificamos para 'created_at'
            "thread_id": obj.thread_id,
            "sms_id": obj.sms_id,
            "status": "PROCESSING",
        })

    # 3) Pegar registros que falharam (SmsFailed)
    #    O campo de data aqui é "failed_at"
    failed_objs = SmsFailed.objects.filter(phone=phone).order_by('-failed_at')
    failed_list = []
    for obj in failed_objs:
        failed_list.append({
            "id": obj.id,
            "phone": obj.phone,
            "message": obj.message,
            "created_at": obj.failed_at,
            "thread_id": obj.thread_id,
            "sms_id": obj.sms_id,
            "error_code": obj.error_code,
            "status": "FAILED",
        })

    # 4) Pegar registros enviados (SmsSent)
    #    O campo de data aqui é "sent_at"
    sent_objs = SmsSent.objects.filter(phone=phone).order_by('-sent_at')
    sent_list = []
    for obj in sent_objs:
        sent_list.append({
            "id": obj.id,
            "phone": obj.phone,
            "message": obj.message,
            "created_at": obj.sent_at,
            "thread_id": obj.thread_id,
            "sms_id": obj.sms_id,
            "status": "SENT",
        })

    # 5) Unificar tudo em uma só lista
    combined = queue_list + processing_list + failed_list + sent_list

    # 6) Ordenar (novamente) pela chave 'created_at' de forma decrescente
    #    Caso queira do mais antigo para o mais novo, remova o 'reverse=True'
    combined.sort(key=lambda x: x['created_at'], reverse=True)

    return Response({"history": combined})