"""
Файл signals.py — здесь описываются "подписки" на события базы данных.
Сейчас здесь реализована отправка приветственного письма после создания пользователя.
"""
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.mail import send_mail
from django.conf import settings
from .models import User


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """
    Срабатывает каждый раз, когда объект User сохраняется в БД.
    Если создан НОВЫЙ пользователь (created=True) — шлем письмо.
    """
    if created and not instance.is_superuser:
        # Формируем тему и текст
        subject = 'Добро пожаловать в сервис закупок!'
        
        # Используем first_name, если он есть, иначе обращаемся по email
        name = instance.first_name if instance.first_name else ''
        
        message = (
            f"Привет, {name}!\n\n"
            f"Ваш аккаунт в системе автоматизации закупок успешно создан.\n\n"
            f"С уважением,\nКоманда сервиса"
        )
        
        # Отправляем письмо
        recipient_list = [instance.email]
       
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False 
        )