from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import LoginHistory

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    LoginHistory.objects.create(
        user=user,
        ip_address=ip
    ) 