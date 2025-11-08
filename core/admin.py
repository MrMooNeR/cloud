from django.contrib import admin
from .models import File, PromoCode, PromoRedemption
@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ("id","owner","name","size","uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("name", "owner__email")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_percent",
        "grant_subscription",
        "extra_storage_bytes",
        "use_count",
        "max_uses",
        "valid_until",
        "active",
    )
    list_filter = ("active", "grant_subscription", "valid_until")
    search_fields = ("code", "description")
    readonly_fields = ("use_count", "created_at")
    ordering = ("-created_at",)


@admin.register(PromoRedemption)
class PromoRedemptionAdmin(admin.ModelAdmin):
    list_display = (
        "promo",
        "user",
        "redeemed_at",
        "discount_percent",
        "extra_storage_bytes",
        "granted_subscription",
    )
    list_filter = ("redeemed_at", "granted_subscription")
    search_fields = ("promo__code", "user__email")