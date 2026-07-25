"""
Команда для загрузки товаров из файла shop1.yaml в базу данных.
Позволяет быстро заполнить каталог данными от поставщика перед тестированием API.
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from yaml import load as load_yaml, Loader
from api.models import (
    Shop, Category, Product,
    ProductInfo, Parameter, ProductParameter
)


class Command(BaseCommand):
    help = 'Импорт каталога товаров из YAML-файла'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        """
        Основная логика команды:
        1. Читает файл shop1.yaml.
        2. Находит магазин "Связной" (или создает его).
        3. Удаляет старые товары этого магазина.
        4. Создает новые товары и предложения с ценами.
        """
        file_path = os.path.join(settings.BASE_DIR, 'shop1.yaml')

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'Файл {file_path} не найден'))
            return

        try:
            with open(file_path, encoding='utf-8-sig') as f:
                data = load_yaml(f.read(), Loader=Loader)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка чтения файла: {e}'))
            return

        # --- 1. Получаем или создаем магазин ---
        # Название берем прямо из поля "shop:" внутри самого YAML-файла
        shop_data = data.get('shop', {})
        shop_title = shop_data if isinstance(shop_data, str) else shop_data.get('name', '')

        if not shop_title:
            self.stdout.write(self.style.ERROR(
                f'В файле {file_path} не указано имя магазина (ключ "shop")'
            ))
            return

        # Ищем магазин по названию. Если его нет — создаем новый.
        shop, created = Shop.objects.get_or_create(
            title=shop_title,
            defaults={'accepts_orders': True}
        )
        action_word = 'создан' if created else 'найден/обновлен'
        self.stdout.write(self.style.SUCCESS(f'Магазин "{shop.title}" {action_word}. ID: {shop.id}'))

        # --- 2. Очистка старых предложений этого магазина ---
        # Перед новой заливкой удаляем старые цены этого же магазина, чтобы не было дублей цен.
        deleted_count, _ = ProductInfo.objects.filter(shop=shop).delete()
        self.stdout.write(self.style.SUCCESS(f'Удалено старых предложений: {deleted_count}'))

        created_offers = 0

        # --- 3. Основной цикл обработки товаров ---
        for item in data.get('goods', []):

            cat_id = item.get('category')
            # Ищем описание категории внутри самого файла по ID
            cat_data = next(
                (c for c in data.get('categories', []) if c['id'] == cat_id),
                None
            )

            if not cat_data:
                self.stdout.write(
                    self.style.WARNING(
                        f'Пропуск товара {item.get("name")}: категория {cat_id} не описана в разделе categories.')
                )
                continue

            # Создаем категорию (если её еще нет в базе)
            category, _ = Category.objects.get_or_create(
                id=cat_data['id'],
                defaults={'title': cat_data['name']}
            )
            # Привязываем магазин к категории (связь Many-to-Many)
            category.stores.add(shop)

            # Базовый товар (справочник названий)
            product, _ = Product.objects.get_or_create(
                name=item['name'],
                category=category
            )

            # Конкретное предложение от магазина (цена + наличие)
            offer_defaults = {
                'available_count': item['quantity'],
                'cost_price': item['price'],
                'retail_price': item['price_rrc'],
                'parameters': item.get('parameters', {}),  # JSON-поле с характеристиками
            }

            # Обновляем цену если она изменилась, или создаем новую запись
            offer, is_created = ProductInfo.objects.update_or_create(
                product=product,
                shop=shop,
                article=str(item.get('id', '')),
                defaults=offer_defaults
            )

            if is_created:
                created_offers += 1

        self.stdout.write(
            self.style.SUCCESS(f'✅ Импорт завершен. Новых предложений создано: {created_offers}')
        )