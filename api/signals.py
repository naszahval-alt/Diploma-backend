"""
Файл signals.py — здесь описываются "подписки" на события базы данных.
Сейчас здесь реализована отправка приветственного письма после создания пользователя.
"""
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.mail import send_mail
from django.conf import settings
from .models import User, Order


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

@receiver(post_save, sender=Order)
def send_order_confirmation(sender, instance, created, **kwargs):
    """
    Отправляет письмо при изменении статуса заказа со "basket" на "new" или "confirmed".
    """
    # Если это создание нового заказа-корзины — пропускаем
    if created or not kwargs['update_fields']:
        return

    # Проверяем изменение статуса
    old_status = getattr(instance, '_original_status', None)
    new_status = instance.status

    # Генерируем уведомление при переходе из корзины к заказу
    if old_status in ['basket'] and new_status in ['new', 'confirmed']:
        subject = f"Ваш заказ №{instance.id} успешно оформлен"
        
        items_list = "\n".join([
            f"- {item.offer.product.name}: {item.amount}x ({item.line_total:.2f} ₽)"
            for item in instance.items.all()
        ])

        message = (
            f"Покупатель: {instance.buyer.first_name or ''}\n\n"
            f"Товары:\n{items_list}\n"
            f"Сумма: {instance.total_amount:.2f} ₽\n\n"
            "Благодарим за покупку!"
        )

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        recipient_list = [instance.buyer.email]

        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False 
        )