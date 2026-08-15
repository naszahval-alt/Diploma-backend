"""
Конфигурация URL-маршрутизации проекта DiplomaProject.

Настраивает:
- Доступ к админ-панели Django.
- Маршруты API v1 через DefaultRouter.
- Интерактивную документацию Swagger/ReDoc.
- Эндпоинты авторизации SimpleJWT.
"""

from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi

# Документация (Swagger / ReDoc)
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Вьюсеты нашего приложения 'api'
from api.views import (
    CategoryViewSet,
    ContactViewSet,
    OrderViewSet,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProductInfoViewSet,
    ProductViewSet,
    RegisterUserView,
    ShopViewSet,
    UserViewSet,
)

# Настраиваем Swagger-документацию
schema_view = get_schema_view(
    openapi.Info(
        title="Diploma Project API",
        default_version="v1",
        description="Backend сервиса автоматизации закупок.",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

# РЕГИСТРАЦИЯ МАРШРУТОВ
router = DefaultRouter()

# Регистрация ресурсов каталога и пользователей
router.register(r"shops", ShopViewSet)
router.register(r"categories", CategoryViewSet)
router.register(r"products", ProductViewSet)
router.register(r"offers", ProductInfoViewSet)
router.register(r"contacts", ContactViewSet)
router.register(r"orders", OrderViewSet)
router.register(r"users", UserViewSet)

urlpatterns = [
    # Админка Django
    path("admin/", admin.site.urls),
    # Основной префикс API версии 1
    path("api/v1/", include(router.urls)),
    # Аутентификация (SimpleJWT)
    path("api/v1/token/", TokenObtainPairView.as_view()),
    path("api/v1/token/refresh/", TokenRefreshView.as_view()),
    # Регистрация
    path("api/v1/register/", RegisterUserView.as_view()),
    # Восстановление пароля
    path("api/v1/password-reset/", PasswordResetRequestView.as_view()),
    path("api/v1/password-reset/confirm/", PasswordResetConfirmView.as_view()),
    # Кастомный endpoint для смены статуса заказа
    path(
        "api/v1/orders/<int:pk>/change-status/",
        OrderViewSet.as_view({"patch": "change_status"}),
    ),
    # Документация
    path("docs/", schema_view.with_ui("swagger", cache_timeout=0)),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0)),
]
