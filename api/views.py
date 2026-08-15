"""
views.py — представления (views) для API системы автоматизации закупок.

Реализует:
- регистрацию пользователя (отдельный APIView);
- CRUD по сущностям через ViewSet;
- разграничение прав доступа;
- фильтрацию данных (пользователь видит только своё);
- работу с корзиной через кастомное действие OrderViewSet.
"""
from typing import ClassVar

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Category,
    Contact,
    Order,
    OrderItem,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)
from .serializers import (
    CategorySerializer,
    ContactSerializer,
    OrderSerializer,
    ParameterSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProductInfoSerializer,
    ProductParameterSerializer,
    ProductSerializer,
    ShopSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)


class RegisterUserView(APIView):
    """Регистрация пользователя: принимает данные, валидирует, создаёт и возвращает профиль."""

    permission_classes: ClassVar[list] = []

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
    permission_classes: ClassVar[list] = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(id=self.request.user.id)


class ShopViewSet(viewsets.ModelViewSet):
    """Список магазинов (доступно без авторизации)"""

    queryset = Shop.objects.all()
    serializer_class = ShopSerializer

    def get_permissions(self):
        # Список магазинов могут смотреть все, а создание/редактирование требует авторизации
        if self.action in ["list", "retrieve"]:
            permission_classes: ClassVar[list] = [AllowAny]
        else:
            permission_classes: ClassVar[list] = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """
        Cоздавать магазин может только User типа 'shop'.
        """
        user = self.request.user

        if user.type != "shop":
            raise ValidationError(
                {
                    "detail": 'Создавать магазины могут только пользователи с ролью "Магазин".'
                }
            )

        # Если проверка пройдена — привязываем текущего пользователя к магазину
        serializer.save(owner=user)


class CategoryViewSet(viewsets.ModelViewSet):
    """Категории товаров (доступно без авторизации)"""

    queryset = Category.objects.prefetch_related("stores").all()
    serializer_class = CategorySerializer
    permission_classes: ClassVar[list] = [AllowAny]


class ProductViewSet(viewsets.ModelViewSet):
    """Базовые карточки товаров (доступно без авторизации)"""

    queryset = Product.objects.select_related("category").all()
    serializer_class = ProductSerializer
    permission_classes: ClassVar[list] = [AllowAny]


class ParameterViewSet(viewsets.ModelViewSet):
    """Справочник параметров (EAV)"""

    queryset = Parameter.objects.all()
    serializer_class = ParameterSerializer
    permission_classes: ClassVar[list] = [IsAuthenticated]


class ProductParameterViewSet(viewsets.ModelViewSet):
    """Значения параметров конкретных предложений"""

    queryset = ProductParameter.objects.select_related(
        "parameter", "product_info"
    ).all()
    serializer_class = ProductParameterSerializer
    permission_classes: ClassVar[list] = [IsAuthenticated]


class ProductInfoViewSet(viewsets.ModelViewSet):
    """Предложения товаров от магазинов (Прайс-лист)"""

    queryset = (
        ProductInfo.objects.select_related("product", "shop")
        .prefetch_related("parameters__parameter")
        .all()
    )
    serializer_class = ProductInfoSerializer
    permission_classes: ClassVar[list] = [AllowAny]


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

    queryset = Order.objects.all().prefetch_related("items__offer")
    serializer_class = OrderSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Order.objects.all().prefetch_related(
            "items__offer__product", "delivery_contact"
        )

        if not self.request.user.is_authenticated:
            return qs.none()

        user = self.request.user

        if getattr(user, "type", None) == "shop":
            qs = qs.filter(shop__owner=user)
            return qs

        # Обычный покупатель видит только свои заказы
        return qs.filter(buyer=user)

    def perform_create(self, serializer):
        serializer.save(buyer=self.request.user)

    @action(detail=False, methods=["post"], url_path="add-to-basket")
    def add_to_basket(self, request):
        """
        Эндпоинт добавления товара в корзину.
        Работает так:
        1. Находит текущую активную корзину (status='basket') или создает новую.
        2. Проверяет наличие товарного предложения (ProductInfo).
        3. Добавляет позицию или увеличивает количество существующей.
        """
        offer_id = request.data.get("offer_id")

        if not offer_id:
            raise ValidationError({"detail": "Поле offer_id обязательно."})

        try:
            offer = ProductInfo.objects.get(id=offer_id)
        except ProductInfo.DoesNotExist:
            raise ValidationError(
                {"detail": f"Товарное предложение {offer_id} не найдено."}
            )

        order, _ = Order.objects.get_or_create(
            buyer=request.user, status="basket", defaults={"delivery_contact": None}
        )

        item, item_created = OrderItem.objects.get_or_create(
            order=order, offer=offer, defaults={"amount": 1}
        )

        if not item_created:
            item.amount += 1
            item.save(update_fields=["amount"])

        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = self.get_object()

        if order.buyer != request.user:
            return Response(
                {"error": "Доступ запрещён"}, status=status.HTTP_403_FORBIDDEN
            )

        if order.status != "basket":
            return Response(
                {"error": "Подтверждать можно только корзину"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Группируем товары по магазинам
        items_by_shop = {}
        for item in order.items.all():
            shop = item.offer.shop
            items_by_shop.setdefault(shop, []).append(item)

        if not items_by_shop:
            order.delete()
            return Response({"detail": "Корзина пуста"}, status=status.HTTP_200_OK)

        created_ids = []
        for shop, items in items_by_shop.items():
            new_order = Order.objects.create(
                buyer=order.buyer,
                shop=shop,
                status="confirmed",
                delivery_contact=order.delivery_contact,
            )
            for item in items:
                OrderItem.objects.create(
                    order=new_order,
                    offer=item.offer,
                    amount=item.amount,
                )
            created_ids.append(new_order.id)

        order.delete()  # удаляем исходную корзину

        return Response(
            {
                "detail": "Корзина подтверждена и разбита по магазинам",
                "new_orders": created_ids,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["patch"])
    def change_status(self, request, pk=None):
        # Получаем заказ напрямую, игнорируя get_queryset
        try:
            order = Order.objects.select_related("shop", "buyer").get(pk=pk)
        except Order.DoesNotExist:
            return Response(
                {"error": "Заказ не найден."}, status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"error": "Поле status обязательно"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        # Проверяем права: менять статус может только покупатель или владелец магазина
        can_change = order.buyer_id == user.id or (
            order.shop_id and order.shop.owner_id == user.id
        )

        if not can_change:
            return Response(
                {"error": "У вас нет прав на изменение статуса этого заказа."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Меняем статус
        order.status = new_status
        order.save(update_fields=["status"])

        return Response(
            {
                "id": order.id,
                "status": order.status,
                "message": "Статус успешно изменён.",
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(APIView):
    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Проверьте почту для сброса пароля."}, status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(APIView):
    permission_classes: ClassVar[list] = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Пароль успешно изменен."}, status=status.HTTP_200_OK
        )
