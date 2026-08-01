"""
Команда для загрузки товаров из YAML-файла shop1.yaml.
"""

import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from yaml import load as load_yaml, Loader

from api.models import (
    Shop,
    Category,
    Product,
    ProductInfo,
    Parameter,
    ProductParameter
)


class Command(BaseCommand):
    help = 'Импорт каталога товаров из YAML-файла'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='shop1.yaml',
            help='Путь к YAML-файлу (относительно BASE_DIR)'
        )

    def handle(self, *args, **options):
        file_path = os.path.join(settings.BASE_DIR, options['file'])

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'Файл {file_path} не найден'))
            return

        try:
            with open(file_path, encoding='utf-8-sig') as f:
                data = load_yaml(f.read(), Loader=Loader)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка чтения файла: {e}'))
            return

        # 1/ Получаем или создаем магазин
        # Берем значение напрямую из ключа "shop"
        shop_title = data.get('shop')
        if not shop_title:
            self.stdout.write(self.style.ERROR('В файле не указано имя магазина (ключ "shop")'))
            return

        # Ищем по полю title
        shop, created = Shop.objects.get_or_create(
            title=shop_title,
            defaults={'accepts_orders': True}
        )

        action_word = 'создан' if created else 'найден/обновлен'
        self.stdout.write(self.style.SUCCESS(f'Магазин "{shop.title}" {action_word}. ID: {shop.id}'))

        # 2. Очистка старых предложений этого магазина
        deleted_count, _ = ProductInfo.objects.filter(shop=shop).delete()
        self.stdout.write(self.style.SUCCESS(f'Удалено старых предложений: {deleted_count}'))

        created_offers = 0

        # 3. Основной цикл обработки товаров
        for item in data.get('goods', []):
            cat_id = item.get('category')

            # Ищем описание категории внутри файла по ID
            cat_data = next((c for c in data.get('categories', []) if c['id'] == cat_id), None)

            if not cat_data:
                self.stdout.write(
                    self.style.WARNING(
                        f'Пропуск товара {item.get("name")}: категория {cat_id} не описана в разделе categories.'
                    )
                )
                continue

            # Создаем категорию, используя поле title
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
                'cost_price': Decimal(str(item['price'])),
                'retail_price': Decimal(str(item['price_rrc'])),
                'parameters': item.get('parameters', {}),
            }

            # Используем update_or_create, чтобы избежать дублей при повторном запуске импорта
            offer, is_created = ProductInfo.objects.update_or_create(
                product=product,
                shop=shop,
                article=str(item.get('id')),
                defaults=offer_defaults
            )

            # Обработка параметров (EAV-модель)
            existing_params = {pp.parameter.name: pp for pp in offer.parameter_links.select_related('parameter').all()}

            for param_name, value in item.get('parameters', {}).items():
                parameter_obj, _ = Parameter.objects.get_or_create(name=param_name)

                if param_name in existing_params:
                    # Если параметр уже есть у этого предложения — обновляем значение
                    existing_params[param_name].value = str(value)
                    existing_params[param_name].save()
                else:
                    # Если параметра нет — создаем новую связь
                    ProductParameter.objects.create(
                        product_info=offer,
                        parameter=parameter_obj,
                        value=str(value)
                    )

            if is_created:
                created_offers += 1

        self.stdout.write(
            self.style.SUCCESS(f'✅ Импорт завершен. Новых предложений создано: {created_offers}')
        )