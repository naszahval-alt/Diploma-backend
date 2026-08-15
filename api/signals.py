"""
Файл signals.py — подписки на события базы данных.
Реализует отправку уведомлений о смене статуса заказа.
"""
import logging
from io import BytesIO

from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

logger = logging.getLogger(__name__)


@receiver(post_save, sender="api.User")
def send_welcome_email(sender, instance, created, **kwargs):
    if not created or instance.is_superuser:
        return

    name = instance.first_name or ""
    subject = "Добро пожаловать в сервис закупок!"
    message = (
        f"Привет, {name}!\n\n"
        f"Ваш аккаунт в системе автоматизации закупок успешно создан.\n\n"
        "С уважением,\nКоманда сервиса"
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    recipient_list = [instance.email]

    if not from_email:
        logger.warning("DEFAULT_FROM_EMAIL не настроен.")
        return

    try:
        # Отправка письма (в консоль из-за настроек DEBUG)
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        logger.info(f"Письмо отправлено на {instance.email}")
    except Exception:
        logger.exception("Ошибка отправки приветственного письма")


@receiver(post_save, sender="api.Order")
def send_order_notification(sender, instance, created, **kwargs):
    if created or not hasattr(instance, "_original_status"):
        return

    old_status = instance._original_status
    new_status = instance.status

    if old_status == new_status:
        return

    if new_status != "packed":
        return

    logger.info(f"Заказ #{instance.id} перешёл в статус 'Собран'. Готовим накладную.")

    table_data = []  # Список для генерации PDF

    for item in instance.items.select_related("offer__product").all():
        product_name = item.offer.product.name

        data_row = [f"{product_name}", str(item.amount), f"{item.line_total:.2f} ₽"]
        table_data.append(data_row)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"Накладная №{instance.id}", styles["Title"]),
        Paragraph(
            f"Дата: {timezone.now().strftime('%d.%m.%Y %H:%M')}", styles["Normal"]
        ),
    ]

    # Формируем таблицу
    table = Table(table_data)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    admin_emails = [email for _, email in getattr(settings, "ADMINS", [])]
    default_from = getattr(settings, "DEFAULT_FROM_EMAIL", None)

    if not admin_emails or not default_from:
        logger.warning("Не настроены ADMINS или DEFAULT_FROM_EMAIL")
        return

    subject = f"[ОТЧЕТ] Заказ №{instance.id} собран поставщиком"
    body = (
        "Поставщик собрал заказ.\n\n"
        "Список товаров:\n"
        + "\n".join([f"- {row[0]} x{row[1]}" for row in table_data[1:]])
        + f"\n\nИтого: {instance.total_amount:.2f} ₽\n\nФайл прикреплен."
    )

    try:
        msg = EmailMessage(subject, body, default_from, to=admin_emails)
        msg.attach(f"nakladnaya_{instance.id}.pdf", buffer.read(), "application/pdf")
        msg.send(fail_silently=False)
        logger.info(f"Успешно: Накладная отправлена админу для заказа #{instance.id}")
    except Exception:
        logger.exception("Критическая ошибка почты")
