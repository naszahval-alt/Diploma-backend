from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _

STATE_CHOICES = (
    ('basket', 'Корзина'),
    ('new', 'Новый'),
    ('confirmed', 'Подтвержден'),
    ('packed', 'Собран'),
    ('shipped', 'В пути'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)

USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель'),
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Адрес электронной почты обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('У суперпользователя должен быть флаг is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username_validator = None

    # Делаю обычное имя НЕ обязательным
    username = models.CharField(
        _('username'),
        max_length=150,
        unique=False,
        blank=True,
    )

    objects = UserManager()

    # Указываю почту как логин
    USERNAME_FIELD = 'email'

    # Очищаю список обязательных полей
    REQUIRED_FIELDS = []

    email = models.EmailField(_('адрес электронной почты'), unique=True)
    type = models.CharField(verbose_name='Тип пользователя', 
                            choices=USER_TYPE_CHOICES, 
                            max_length=5, 
                            default='buyer')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = "Список пользователей"
        ordering = ('email',)

    def __str__(self):
        return f'{self.email}'


# МОДЕЛИ КАТАЛОГА
class Shop(models.Model):
    title = models.CharField(max_length=100, verbose_name='Название магазина')
    url = models.URLField(verbose_name='Ссылка на API поставщика', null=True, blank=True)
    owner = models.OneToOneField(User, verbose_name='Ответственный менеджер',
                                 blank=True, null=True, on_delete=models.SET_NULL,
                                 related_name='managed_shop')
    accepts_orders = models.BooleanField(verbose_name='Принимает заказы', default=True)

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = "Список магазинов"
        ordering = ('title',)

    def __str__(self):
        return self.title


class Category(models.Model):
    title = models.CharField(max_length=40, verbose_name='Название категории')
    stores = models.ManyToManyField(Shop, 
                                    verbose_name='Магазины', 
                                    related_name='category_list', 
                                    blank=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = "Категории товаров"
        ordering = ('title',)

    def __str__(self):
        return self.title


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name='Наименование')
    category = models.ForeignKey(Category, 
                                 verbose_name='Категория',
                                 related_name='items', 
                                 on_delete=models.PROTECT, 
                                 null=True, 
                                 blank=True)

    class Meta:
        verbose_name = 'Товарная позиция'
        verbose_name_plural = "Справочник товаров"
        ordering = ('name',)

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(Product,
                                verbose_name='Базовый товар',
                                related_name='offers',
                                on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop,
                             verbose_name='Поставщик',
                             related_name='offers',
                             on_delete=models.CASCADE)
    article = models.CharField(max_length=100, verbose_name='Артикул/ID у поставщика')
    available_count = models.PositiveIntegerField(verbose_name='Остаток на складе')
    cost_price = models.DecimalField(verbose_name='Цена закупки', max_digits=10, decimal_places=2)
    retail_price = models.DecimalField(verbose_name='Розничная цена', max_digits=10, decimal_places=2)

    parameters = models.JSONField(
        verbose_name='Параметры товара',
        default=dict,
        blank=True
    )

    class Meta:
        verbose_name = 'Предложение товара'
        verbose_name_plural = "Предложения товаров"
        constraints = [
            models.UniqueConstraint(fields=['product', 'shop', 'article'], name='unique_offer')
        ]
        ordering = ('-retail_price',)

    def __str__(self):
        return f"{self.product.name} ({self.shop.title}) - {self.retail_price} ₽"


class Parameter(models.Model):
    """Характеристика товара"""
    name = models.CharField(max_length=40, verbose_name='Название параметра', unique=True)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = "Список параметров"

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    """
    Связующая таблица: какое значение имеет конкретный параметр для конкретного предложения товара
    """
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE, related_name='parameter_links')
    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100, verbose_name='Значение')

    class Meta:
        verbose_name = 'Значение параметра'
        verbose_name_plural = "Значения параметров"
        constraints = [
            models.UniqueConstraint(fields=['product_info', 'parameter'], name='unique_param_value'),
        ]

    def __str__(self):
        return f'{self.parameter.name}: {self.value}'


class Contact(models.Model):
    CONTACT_TYPES = (
        ('phone', 'Телефон'),
        ('address', 'Адрес доставки'),
    )

    user = models.ForeignKey(User, 
                             verbose_name='Владелец', 
                             related_name='contacts', 
                             on_delete=models.CASCADE)
    contact_type = models.CharField(verbose_name='Тип', choices=CONTACT_TYPES, max_length=10)
    city = models.CharField(max_length=50, verbose_name='Город')
    street = models.CharField(max_length=100, verbose_name='Улица')
    house = models.CharField(max_length=10, verbose_name='Дом')
    block = models.CharField(max_length=10, verbose_name='Корпус', blank=True)
    flat = models.CharField(max_length=10, verbose_name='Квартира', blank=True)
    phone_number = models.CharField(max_length=20, verbose_name='Контактный телефон')

    class Meta:
        verbose_name = 'Контактные данные'
        verbose_name_plural = "Адреса и телефоны"
        ordering = ('city', 'street')

    def __str__(self):
        return f"{self.city}, {self.street} д.{self.house}"


class Order(models.Model):
    buyer = models.ForeignKey(User, verbose_name='Покупатель', related_name='orders', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    status = models.CharField(verbose_name='Статус', choices=STATE_CHOICES, max_length=15, default='new')
    delivery_contact = models.ForeignKey(Contact, 
                                         verbose_name='Доставка',
                                         null=True, 
                                         blank=True, 
                                         on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = "Заказы"
        ordering = ('-created_at',)

    @property
    def total_amount(self):
        items_sum = sum(item.line_total for item in self.items.all())
        return items_sum

    def __str__(self):
        return f"№{self.id} от {self.created_at.strftime('%d.%m.%Y')} - {self.get_status_display()}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, verbose_name='Заказ', related_name='items', on_delete=models.CASCADE)
    offer = models.ForeignKey(ProductInfo, 
                              verbose_name='Позиция из прайса', 
                              related_name='order_lines', 
                              on_delete=models.PROTECT)
    amount = models.PositiveIntegerField(verbose_name='Количество')

    @property
    def line_total(self):
        return self.amount * float(self.offer.retail_price)

    class Meta:
        verbose_name = 'Строка заказа'
        verbose_name_plural = "Состав заказа"
        constraints = [
            models.UniqueConstraint(fields=['order', 'offer'], name='unique_order_item'),
        ]

    def __str__(self):
        return f"{self.amount} x {self.offer.product.name}"
