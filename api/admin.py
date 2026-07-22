from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Shop, Category, Product,
    ProductInfo, Parameter, ProductParameter,
    Order, OrderItem, Contact
)


# --- ИНЛАЙНЫ (ВЛОЖЕННЫЕ ТАБЛИЦЫ) ---
class ProductParameterInline(admin.TabularInline):
    model = ProductParameter
    extra = 1


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('line_total',)
    autocomplete_fields = ['offer']


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 1
    verbose_name = "Контакт"
    verbose_name_plural = "Контакты"


class OrderInline(admin.TabularInline):
    model = Order
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


    # --- РЕГИСТРАЦИЯ МОДЕЛЕЙ ---
@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner_email', 'accepts_orders')
    search_fields = ('title', 'owner__email')
    list_filter = ('accepts_orders',)

    @admin.display(description='Email владельца')
    def owner_email(self, obj):
        return obj.owner.email if obj.owner else '-'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title',)
    filter_horizontal = ('stores',)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = "Категории товаров"
        ordering = ('title',)

    def __str__(self):
        return self.title


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    search_fields = ('name',)
    list_filter = ('category',)

    class Meta:
        verbose_name = 'Товарная позиция'
        verbose_name_plural = "Справочник товаров"
        ordering = ('name',)

    def __str__(self):
        return self.name


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('product_title', 'shop_title', 'retail_price', 'available_count')
    list_filter = ('shop',)
    search_fields = ('product__name', 'shop__title', 'article')
    inlines = [ProductParameterInline]

    @admin.display(description='Товар')
    def product_title(self, obj):
        return obj.product.name

    @admin.display(description='Магазин')
    def shop_title(self, obj):
        return obj.shop.title


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = "Список параметров"


class ContactAdmin(admin.ModelAdmin):
    search_fields = ('user__email', 'city', 'street')
    list_filter = ('contact_type', 'city')

    def user_email(self, obj):
        return obj.user.email

    class Meta:
        verbose_name = 'Контактные данные'
        verbose_name_plural = "Адреса и телефоны"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer_email', 'status', 'created_at', 'total_amount')
    list_filter = ('status', 'created_at')
    search_fields = ('buyer__email', 'id')
    inlines = [OrderItemInline]
    readonly_fields = ('total_amount', 'created_at')

    @admin.display(description='Покупатель')
    def buyer_email(self, obj):
        return obj.buyer.email

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('buyer')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Админка для управления покупателями и магазинами"""

    list_display = ('email', 'type', 'is_staff', 'is_active')
    search_fields = ('email',)
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'company', 'position', 'type')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'type'),
        }),
    )

    inlines = [ContactInline, OrderInline] 