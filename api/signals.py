"""
Файл signals.py — здесь описываются "подписки" на события базы данных.
Сейчас здесь реализована отправка приветственного письма после создания пользователя.
"""
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.mail import send_mail
from django.conf import settings
from .models import User, Order
import logging
from django.core.mail import EmailMessage
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    if not created or instance.is_superuser:
        return

    name = instance.first_name or ''
    subject = 'Добро пожаловать в сервис закупок!'
    message = (
        f"Привет, {name}!\n\n"
        f"Ваш аккаунт в системе автоматизации закупок успешно создан.\n\n"
        "С уважением,\nКоманда сервиса"
    )
    recipient_list = [instance.email]
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)

    if not from_email:
        logger.warning("DEFAULT_FROM_EMAIL не настроен, приветственное письмо не отправлено.")
        return

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False
        )
        logger.info(f"Приветственное письмо отправлено на {instance.email}")
    except Exception as e:
        logger.error(f"Ошибка отправки приветственного письма: {e}", exc_info=True)


@receiver(post_save, sender=Order)
def send_order_confirmation(sender, instance, created, **kwargs):
    # Если заказ только создан — не отправляем уведомления о смене статуса
    if created:
        return

    old_status = getattr(instance, '_original_status', None)
    new_status = instance.status

    if old_status is not None and old_status == new_status:
        return

    if new_status != 'packed':
        return

    logger.info(f"Заказ №{instance.id} перешёл в статус 'Собран'. Готовим накладную.")

    items_list = []
    for item in instance.items.all():
        items_list.append([
            f"{item.offer.product.name} (арт: {item.offer.article})",
            str(item.amount)
        ])

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Накладная №{instance.id}", styles['Title']))
    data = [["Товар", "Кол-во"]] + items_list
    table = Table(data)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    admin_emails = [email for _, email in getattr(settings, 'ADMINS', [])]
    default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', None)

    if not admin_emails or not default_from:
        logger.warning("ADMINS или DEFAULT_FROM_EMAIL не настроены. Письмо не отправлено.")
        return

    subject = f"[ВАЖНО] Заказ №{instance.id} собран поставщиком"
    body = f"Заказ №{instance.id} переведён в статус 'Собран'.\n\nСписок товаров:\n{chr(10).join([f'- {i[0]} x{i[1]}' for i in items_list])}"

    try:
        email = EmailMessage(
            subject,
            body,
            default_from,
            to=admin_emails
        )
        email.attach(f'nakladnaya_{instance.id}.pdf', buffer.read(), 'application/pdf')
        email.send(fail_silently=False)
        logger.info(f"Письмо с накладной отправлено администраторам для заказа №{instance.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки письма с накладной: {e}", exc_info=True)
