from django.contrib import admin
from .models import File
@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ("id","owner","name","size","uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("name", "owner__email")
