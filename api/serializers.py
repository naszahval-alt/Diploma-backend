"""
Cериализаторы для API автоматизации закупок.
Тут превращаем модели Django в JSON для фронтенда.
Пароль и себестоимость не отдаём в API.
"""
import secrets
from datetime import timedelta
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Category,
    Contact,
    Order,
    OrderItem,
    Parameter,
    PasswordResetToken,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)


class UserSerializer(serializers.ModelSerializer):
    contacts = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "type", "contacts")
        read_only_fields = ("id", "contacts")


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "type", "password", "password2")

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "Пароли не совпадают."})
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        user = self.Meta.model(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ShopSerializer(serializers.ModelSerializer):
    owner_email = serializers.ReadOnlyField(source="owner.email")

    class Meta:
        model = Shop
        fields = "__all__"


class CategorySerializer(serializers.ModelSerializer):
    shops = serializers.StringRelatedField(
        many=True, source="category_list", read_only=True
    )
    stores_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "title", "shops", "stores_count")

    def get_stores_count(self, obj):
        return obj.stores.count()


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.title", read_only=True)

    class Meta:
        model = Product
        fields = ("id", "name", "category", "category_name")


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = "__all__"


class ProductParameterSerializer(serializers.ModelSerializer):
    parameter_name = serializers.CharField(source="parameter.name", read_only=True)

    class Meta:
        model = ProductParameter
        fields = ("id", "parameter", "parameter_name", "value")
        read_only_fields = ("id",)


class ProductInfoSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    shop_title = serializers.CharField(source="shop.title", read_only=True)
    parameters = serializers.SerializerMethodField()

    class Meta:
        model = ProductInfo
        exclude = ("cost_price",)  # себестоимость не отдаём в API

    def get_parameters(self, obj):
        result = []
        for pp in obj.parameter_links.select_related("parameter").all():
            result.append({"name": pp.parameter.name, "value": pp.value})
        return result


class ContactSerializer(serializers.ModelSerializer):
    user_email = serializers.ReadOnlyField(source="user.email")

    class Meta:
        model = Contact
        fields = (
            "id",
            "city",
            "street",
            "house",
            "block",
            "flat",
            "phone_number",
            "contact_type",
            "user_email",
        )
        read_only_fields = ("id", "user_email")


class OrderItemSerializer(serializers.ModelSerializer):
    offer_data = ProductInfoSerializer(source="offer", read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ("id", "amount", "offer", "offer_data", "line_total")
        extra_kwargs: ClassVar[dict] = {"offer": {"write_only": True}}

    def get_line_total(self, obj):
        return obj.line_total


class OrderSerializer(serializers.ModelSerializer):
    buyer_email = serializers.ReadOnlyField(source="buyer.email")
    items = OrderItemSerializer(many=True, read_only=True)
    delivery_contact_data = ContactSerializer(source="delivery_contact", read_only=True)
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "created_at",
            "buyer",
            "buyer_email",
            "items",
            "delivery_contact",
            "delivery_contact_data",
            "total_amount",
        )
        read_only_fields = (
            "id",
            "buyer",
            "buyer_email",
            "created_at",
            "items",
            "total_amount",
            "status",
        )

    def get_total_amount(self, obj):
        # Считаем сумму по позициям, чтобы не хранить её в БД
        return sum(item.line_total for item in obj.items.all())

    def to_internal_value(self, data):
        internal_value = super().to_internal_value(data)

        # Сохраняем исходные значения полей перед обновлением
        instance = getattr(self, "instance", None)
        if instance is not None:
            instance._original_status = instance.status

        return internal_value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                {"email": "Пользователь с таким адресом не найден."}
            )
        return value

    def save(self):
        email = self.validated_data["email"]
        user = User.objects.get(email=email)

        # Очистка старых токенов
        user.password_reset_tokens.filter(expires_at__lt=timezone.now()).delete()

        token_str = secrets.token_urlsafe(32)
        expires = timezone.now() + timedelta(hours=24)

        PasswordResetToken.objects.create(
            user=user, token=token_str, expires_at=expires
        )

        reset_link = f"{settings.FRONTEND_URL}/reset-password/{token_str}/"

        subject = "Сброс пароля"
        message = (
            f"Для сброса пароля перейдите по ссылке:\n{reset_link}\n\n"
            "Ссылка действительна 24 часа."
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[email],
            fail_silently=False,
        )


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    new_password2 = serializers.CharField(write_only=True)
    token = serializers.CharField(write_only=True)

    def validate_token(self, value):
        try:
            self.token_obj = PasswordResetToken.objects.select_related("user").get(
                token=value
            )
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError(
                {"token": "Неверный или устаревший токен."}
            )

        if not self.token_obj.is_valid():
            raise serializers.ValidationError({"token": "Срок действия токена истек."})

        return value

    def validate(self, data):
        if data["new_password"] != data["new_password2"]:
            raise serializers.ValidationError({"new_password": "Пароли не совпадают."})
        return data

    def save(self):
        user = self.token_obj.user
        user.set_password(self.validated_data["new_password"])
        user.save()
        self.token_obj.delete()
