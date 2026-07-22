from rest_framework import serializers
from .models import (
    User, Shop, Category, Product,
    ProductInfo, Parameter, ProductParameter,
    Contact, Order, OrderItem
)


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор пользователя. Скрывает пароль, выводит связанные контакты."""
    contacts = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'type', 'company', 'position', 'contacts')
        read_only_fields = ('id', 'contacts')


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
    """Сериализатор предложений товаров"""
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
    user_email = serializers.ReadOnlyField(source='user.email')

    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'block', 'flat', 'phone_number', 'contact_type', 'user_email')
        read_only_fields = ('id', 'user_email')


class OrderItemSerializer(serializers.ModelSerializer):
    offer_data = ProductInfoSerializer(source='offer', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'amount', 'offer', 'offer_data')
        extra_kwargs = {
            'offer': {'write_only': True}
        }


class OrderSerializer(serializers.ModelSerializer):
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