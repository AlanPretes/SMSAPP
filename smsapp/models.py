# smsapp/models.py

from django.db import models

class SmsQueue(models.Model):
    phone = models.CharField(max_length=20)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Salvar os valores que você captura no Android/Thread
    thread_id = models.CharField(max_length=50, blank=True, null=True)  # ou int, conforme necessidade
    sms_id = models.IntegerField(blank=True, null=True)  # _id do SMS

    def __str__(self):
        return f"Queue #{self.pk} - {self.phone}"

class SmsProcessing(models.Model):
    phone = models.CharField(max_length=20)
    message = models.TextField()
    started_at = models.DateTimeField(auto_now_add=True)
    
    thread_id = models.CharField(max_length=50, blank=True, null=True)
    sms_id = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"Processing #{self.pk} - {self.phone}"

class SmsFailed(models.Model):
    phone = models.CharField(max_length=20)
    message = models.TextField()
    failed_at = models.DateTimeField(auto_now_add=True)
    
    thread_id = models.CharField(max_length=50, blank=True, null=True)
    sms_id = models.IntegerField(blank=True, null=True)
    error_code = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"Failed #{self.pk} - {self.phone}"

class SmsSent(models.Model):
    phone = models.CharField(max_length=20)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    
    thread_id = models.CharField(max_length=50, blank=True, null=True)
    sms_id = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"Sent #{self.pk} - {self.phone}"
