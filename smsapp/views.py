# smsapp/views.py

from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from smsapp.models import SmsQueue, SmsProcessing, SmsFailed, SmsSent

import time
from datetime import datetime
from smsapp.services import send_sms_via_adb

from django_q.tasks import async_task

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

    queue = SmsQueue.objects.create(
            phone=phone,
            message=message,
        )  

    return Response({'success': True, 'detail': 'SMS enviado para fila de envios!'}, status=status.HTTP_202_ACCEPTED)

@api_view(['GET'])
def get_sms_history(request, phone):
    return Response({"history": sms_history})