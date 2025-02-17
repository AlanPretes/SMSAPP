from django.urls import path
from .views import send_and_check_sms

urlpatterns = [
    path('enqueue/', send_and_check_sms, name='enqueue'),  # NÃO usar as_view()
    # path('history/<str:phone>/', get_sms_history, name='history'),  
]
