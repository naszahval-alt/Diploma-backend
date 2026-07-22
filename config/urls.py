from django.contrib import admin
from django.urls import path, include, re_path
from django.shortcuts import redirect
from rest_framework.routers import DefaultRouter

from api.views import (
    ShopViewSet,
    CategoryViewSet,
    ProductViewSet,
    ProductInfoViewSet,
    ContactViewSet,
    OrderViewSet,
)

# Документация Swagger
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Diploma Project API",
        default_version='v1',
        description="Backend для автоматизации закупок",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

router = DefaultRouter()
router.register(r'shops', ShopViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'offers', ProductInfoViewSet)
router.register(r'contacts', ContactViewSet)
router.register(r'orders', OrderViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),

    # Пути для документации
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0)),
]