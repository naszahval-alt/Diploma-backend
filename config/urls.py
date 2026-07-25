"""
config/urls.py — маршрутизация (URL-конфигурация) для API системы автоматизации закупок.

Реализует:
- подключение админки Django;
- регистрацию всех ViewSet через роутер (API v1);
- Swagger-документацию по адресу /docs/.
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from api.views import (
    ShopViewSet,
    CategoryViewSet,
    ProductViewSet,
    ProductInfoViewSet,
    ContactViewSet,
    OrderViewSet,
    UserViewSet,
)

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Создаём роутер и регистрируем все ViewSet
router = DefaultRouter()
router.register(r'shops', ShopViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'offers', ProductInfoViewSet)
router.register(r'contacts', ContactViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'users', UserViewSet)

# Настраиваем Swagger-документацию
schema_view = get_schema_view(
    openapi.Info(
        title="Diploma Project API",
        default_version='v1',
        description="Backend для автоматизации закупок",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Админка Django
    path('admin/', admin.site.urls),

    # Все API-маршруты по префиксу /api/v1/
    path('api/v1/', include(router.urls)),

    # Swagger UI для документации API
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0)),
]