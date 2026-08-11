"""
views.py — представления (views) для API системы автоматизации закупок.

Реализует:
- регистрацию пользователя (отдельный APIView);
- CRUD по сущностям через ViewSet;
- разграничение прав доступа;
- фильтрацию данных (пользователь видит только своё);
- работу с корзиной через кастомное действие OrderViewSet.
"""

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from django.db.models import Sum, F
from .models import (
    User, Shop, Category, Product,
    ProductInfo, Parameter, ProductParameter,
    Contact, Order, OrderItem
)
from .serializers import (
    UserSerializer, UserRegistrationSerializer, ShopSerializer, CategorySerializer,
    ProductSerializer, ProductInfoSerializer, ParameterSerializer,
    ProductParameterSerializer, ContactSerializer,
    OrderSerializer, OrderItemSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)


class RegisterUserView(APIView):
    """Регистрация пользователя: принимает данные, валидирует, создаёт и возвращает профиль."""
    permission_classes = []

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """Просмотр профиля текущего пользователя"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(id=self.request.user.id)


class ShopViewSet(viewsets.ModelViewSet):
    """Список магазинов (доступно без авторизации)"""
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [AllowAny]


class CategoryViewSet(viewsets.ModelViewSet):
    """Категории товаров (доступно без авторизации)"""
    queryset = Category.objects.prefetch_related('stores').all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class ProductViewSet(viewsets.ModelViewSet):
    """Базовые карточки товаров (доступно без авторизации)"""
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]


class ParameterViewSet(viewsets.ModelViewSet):
    """Справочник параметров (EAV)"""
    queryset = Parameter.objects.all()
    serializer_class = ParameterSerializer
    permission_classes = [IsAuthenticated]


class ProductParameterViewSet(viewsets.ModelViewSet):
    """Значения параметров конкретных предложений"""
    queryset = ProductParameter.objects.select_related('parameter', 'product_info').all()
    serializer_class = ProductParameterSerializer
    permission_classes = [IsAuthenticated]


class ProductInfoViewSet(viewsets.ModelViewSet):
    """Предложения товаров от магазинов (Прайс-лист)"""
    queryset = ProductInfo.objects.select_related('product', 'shop').prefetch_related('parameters__parameter').all()
    serializer_class = ProductInfoSerializer
    permission_classes = [AllowAny]


class ContactViewSet(viewsets.ModelViewSet):
    """
    Управление контактными данными пользователей (адреса, телефоны)
    """
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Contact.objects.filter(user=self.request.user)
        return Contact.objects.none()


class OrderViewSet(viewsets.ModelViewSet):
    """
    История заказов пользователя.
    Доступ только для авторизованных пользователей.
    Пользователь видит только свои заказы.
    """
    queryset = Order.objects.all().prefetch_related('items__offer')
    serializer_class = OrderSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Order.objects.filter(
                buyer=self.request.user
            ).prefetch_related(
                'items__offer__product',
                'delivery_contact'
            )
        return Order.objects.none()

    def perform_create(self, serializer):
        serializer.save(buyer=self.request.user)

    @action(detail=False, methods=['post'], url_path='add-to-basket')
    def add_to_basket(self, request):
        """
        Эндпоинт добавления товара в корзину.
        Работает так:
        1. Находит текущую активную корзину (status='basket') или создает новую.
        2. Проверяет наличие товарного предложения (ProductInfo).
        3. Добавляет позицию или увеличивает количество существующей.
        """
        offer_id = request.data.get('offer_id')

        if not offer_id:
            raise ValidationError({'detail': 'Поле offer_id обязательно.'})

        try:
            offer = ProductInfo.objects.get(id=offer_id)
        except ProductInfo.DoesNotExist:
            raise ValidationError({'detail': f'Товарное предложение {offer_id} не найдено.'})

        order, created = Order.objects.get_or_create(
            buyer=request.user,
            status='basket',
            defaults={'delivery_contact': None}
        )

        item, item_created = OrderItem.objects.get_or_create(
            order=order,
            offer=offer,
            defaults={'amount': 1}
        )

        if not item_created:
            item.amount += 1
            item.save(update_fields=['amount'])

        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """
        Подтверждение заказа владельцем.
        Реализована проверка владельца (защита от чужих заказов).
        """
        order = self.get_object()

        # проверка прав доступа
        if order.buyer != request.user:
            return Response(
                {'error': 'Доступ запрещен. Это чужой заказ.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if order.status == 'basket':
            order.status = 'confirmed'
            order.save()

            return Response({'status': 'confirmed', 'order_id': order.id}, status=status.HTTP_200_OK)

        return Response(
            {
                'error': 'Заказ нельзя подтвердить. Текущий статус: ' + order.get_status_display(),
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Проверьте почту для сброса пароля.'}, status=status.HTTP_200_OK)

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Пароль успешно изменен.'}, status=status.HTTP_200_OK)