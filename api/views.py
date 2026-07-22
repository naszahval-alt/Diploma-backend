from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Sum, F
from .models import (
    User, Shop, Category, Product,
    ProductInfo, Parameter, ProductParameter,
    Contact, Order, OrderItem
)
from .serializers import (
    UserSerializer, ShopSerializer, CategorySerializer,
    ProductSerializer, ProductInfoSerializer, ParameterSerializer,
    ProductParameterSerializer, ContactSerializer,
    OrderSerializer, OrderItemSerializer
)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """Просмотр профиля"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(id=self.request.user.id)


class ShopViewSet(viewsets.ModelViewSet):
    """Список магазинов"""
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [AllowAny]


class CategoryViewSet(viewsets.ModelViewSet):
    """Категории"""
    queryset = Category.objects.prefetch_related('stores').all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class ProductViewSet(viewsets.ModelViewSet):
    """Базовые товары"""
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]


class ParameterViewSet(viewsets.ModelViewSet):
    """Параметры (EAV)"""
    queryset = Parameter.objects.all()
    serializer_class = ParameterSerializer
    permission_classes = [IsAuthenticated]


class ProductParameterViewSet(viewsets.ModelViewSet):
    """Значения параметров"""
    queryset = ProductParameter.objects.select_related('parameter', 'product_info').all()
    serializer_class = ProductParameterSerializer
    permission_classes = [IsAuthenticated]


class ProductInfoViewSet(viewsets.ModelViewSet):
    """Предложения товаров (Прайс)"""
    queryset = ProductInfo.objects.select_related('product', 'shop').prefetch_related('parameters__parameter').all()
    serializer_class = ProductInfoSerializer
    permission_classes = [AllowAny]


class ContactViewSet(viewsets.ModelViewSet):
    """
    Управление контактными данными пользователей
    """
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer

    def get_permissions(self):
        # Просмотр списка и деталей доступен всем (например, чтобы админ мог видеть структуру БД)
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]

        # Создание, изменение и удаление требует входа в систему
        return [IsAuthenticated()]

    def get_queryset(self):
        # Пользователь видит только свои контакты
        if self.request.user.is_authenticated:
            return Contact.objects.filter(user=self.request.user)
        return Contact.objects.none()

    def perform_create(self, serializer):
        # Автоматически привязываем создаваемый контакт к текущему пользователю
        serializer.save(user=self.request.user)


class OrderViewSet(viewsets.ModelViewSet):
    """
    История заказов пользователя
    """
    # Базовый набор данных для всех действий
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        # Просмотр (свой или чужой по ссылке) разрешен всем
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]

        # Подтверждение заказа и другие изменения - только владельцу
        return [IsAuthenticated()]

    def get_queryset(self):
        # Фильтрация: покупатель видит только свои заказы
        if self.request.user.is_authenticated:
            return Order.objects.filter(
                buyer=self.request.user
            ).prefetch_related(
                'items__offer__product',
                'delivery_contact'
            )
        return Order.objects.none()

    def perform_create(self, serializer):
        # При создании заказа автоматически подставляем текущего пользователя как покупателя
        if self.request.user.is_authenticated:
            serializer.save(buyer=self.request.user)
        else:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Требуется авторизация для создания заказа")