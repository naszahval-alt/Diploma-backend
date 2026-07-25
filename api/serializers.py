"""
Cериализаторы для API автоматизации закупок.
Тут превращаем модели Django в JSON для фронтенда.
Пароль и себестоимость не отдаём в API.
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, Shop, Category, Product,
    ProductInfo, Parameter, ProductParameter,
    Contact, Order, OrderItem
)


class UserSerializer(serializers.ModelSerializer):
    """Пользователь: показываем контакты, пароль не возвращаем."""
    contacts = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'type', 'contacts')
        read_only_fields = ('id', 'contacts')


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Регистрация: проверяем, что пароли совпадают, и ставим пароль"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'type', 'password', 'password2')

    def validate(self, data):
        """Проверяем, что password и password2 одинаковые."""
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Пароли не совпадают."})
        return data

    def create(self, validated_data):
        """Создаём пользователя и ставим пароль."""
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = self.Meta.model(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ShopSerializer(serializers.ModelSerializer):
    """Магазин: показываем email владельца."""
    owner_email = serializers.ReadOnlyField(source='owner.email')

    class Meta:
        model = Shop
        fields = '__all__'


class CategorySerializer(serializers.ModelSerializer):
    """Категория: список магазинов и их количество."""
    shops = serializers.StringRelatedField(many=True, source='category_list', read_only=True)
    stores_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'title', 'shops', 'stores_count')

    def get_stores_count(self, obj):
        return obj.stores.count()


class ProductSerializer(serializers.ModelSerializer):
    """Товар: показываем название категории вместо ID."""
    category_name = serializers.CharField(source='category.title', read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'category', 'category_name')


class ParameterSerializer(serializers.ModelSerializer):
    """Параметры (цвет, размер и т.п.) — справочник."""
    class Meta:
        model = Parameter
        fields = '__all__'


class ProductParameterSerializer(serializers.ModelSerializer):
    """Значение параметра у товара: имя параметра и его значение."""
    parameter_name = serializers.CharField(source='parameter.name', read_only=True)

    class Meta:
        model = ProductParameter
        fields = ('id', 'parameter', 'parameter_name', 'value')
        read_only_fields = ('id',)


class ProductInfoSerializer(serializers.ModelSerializer):
    """Предложение товара (прайс): данные товара, магазина и параметры."""
    product = ProductSerializer(read_only=True)
    shop_title = serializers.CharField(source='shop.title', read_only=True)

    parameters = serializers.SerializerMethodField()

    class Meta:
        model = ProductInfo
        # Исключаю себестоимость из публичного API
        exclude = ('cost_price',)

    def get_parameters(self, obj):
        result = []
        for pp in obj.parameter_links.select_related('parameter').all():
            result.append({
                'name': pp.parameter.name,
                'value': pp.value
            })
        return result


class ContactSerializer(serializers.ModelSerializer):
    """Контакт: показываем email пользователя"""
    user_email = serializers.ReadOnlyField(source='user.email')

    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'block', 'flat', 'phone_number', 'contact_type', 'user_email')
        read_only_fields = ('id', 'user_email')


class OrderItemSerializer(serializers.ModelSerializer):
    """Позиция заказа: количество и данные предложения"""
    offer_data = ProductInfoSerializer(source='offer', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'amount', 'offer', 'offer_data')
        extra_kwargs = {
            'offer': {'write_only': True}
        }


class OrderSerializer(serializers.ModelSerializer):
    """Заказ: покупатель, позиции, доставка и итоговая сумма"""
    buyer_email = serializers.ReadOnlyField(source='buyer.email')
    items = OrderItemSerializer(many=True, read_only=True)
    delivery_contact_data = ContactSerializer(source='delivery_contact', read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'status', 'created_at', 'buyer', 'buyer_email',
            'items', 'delivery_contact', 'delivery_contact_data', 'total_amount'
        )
        read_only_fields = ('id', 'buyer', 'buyer_email', 'created_at', 'items', 'total_amount')