"""
Cериализаторы для API автоматизации закупок.
Тут превращаем модели Django в JSON для фронтенда.
Пароль и себестоимость не отдаём в API.
"""

# serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, Shop, Category, Product,
    ProductInfo, Parameter, ProductParameter,
    Contact, Order, OrderItem
)

class UserSerializer(serializers.ModelSerializer):
    contacts = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'type', 'contacts')
        read_only_fields = ('id', 'contacts')


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'type', 'password', 'password2')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Пароли не совпадают."})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = self.Meta.model(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ShopSerializer(serializers.ModelSerializer):
    owner_email = serializers.ReadOnlyField(source='owner.email')

    class Meta:
        model = Shop
        fields = '__all__'


class CategorySerializer(serializers.ModelSerializer):
    shops = serializers.StringRelatedField(many=True, source='category_list', read_only=True)
    stores_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'title', 'shops', 'stores_count')

    def get_stores_count(self, obj):
        return obj.stores.count()


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.title', read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'category', 'category_name')


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = '__all__'


class ProductParameterSerializer(serializers.ModelSerializer):
    parameter_name = serializers.CharField(source='parameter.name', read_only=True)

    class Meta:
        model = ProductParameter
        fields = ('id', 'parameter', 'parameter_name', 'value')
        read_only_fields = ('id',)


class ProductInfoSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    shop_title = serializers.CharField(source='shop.title', read_only=True)
    parameters = serializers.SerializerMethodField()

    class Meta:
        model = ProductInfo
        exclude = ('cost_price',)  # себестоимость не отдаём в API

    def get_parameters(self, obj):
        result = []
        for pp in obj.parameter_links.select_related('parameter').all():
            result.append({
                'name': pp.parameter.name,
                'value': pp.value
            })
        return result


class ContactSerializer(serializers.ModelSerializer):
    user_email = serializers.ReadOnlyField(source='user.email')

    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'block', 'flat', 'phone_number', 'contact_type', 'user_email')
        read_only_fields = ('id', 'user_email')


class OrderItemSerializer(serializers.ModelSerializer):
    offer_data = ProductInfoSerializer(source='offer', read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ('id', 'amount', 'offer', 'offer_data', 'line_total')
        extra_kwargs = {'offer': {'write_only': True}}

    def get_line_total(self, obj):
        return obj.line_total


class OrderSerializer(serializers.ModelSerializer):
    buyer_email = serializers.ReadOnlyField(source='buyer.email')
    items = OrderItemSerializer(many=True, read_only=True)
    delivery_contact_data = ContactSerializer(source='delivery_contact', read_only=True)
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'status', 'created_at', 'buyer', 'buyer_email',
            'items', 'delivery_contact', 'delivery_contact_data', 'total_amount'
        )
        read_only_fields = ('id', 'buyer', 'buyer_email', 'created_at', 'items', 'total_amount')

    def get_total_amount(self, obj):
        # Считаем сумму по позициям, чтобы не хранить её в БД
        return sum(item.line_total for item in obj.items.all())
