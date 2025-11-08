from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import File


class PromoCodeApplyForm(forms.Form):
    code = forms.CharField(
        label="Промокод",
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Введите промокод",
            }
        ),
    )


class PromoCodeGenerateForm(forms.Form):
    prefix = forms.CharField(
        label="Префикс",
        max_length=12,
        required=False,
        help_text="Необязательная приставка к коду (например, TEST)",
    )
    quantity = forms.IntegerField(
        label="Количество",
        min_value=1,
        max_value=50,
        initial=1,
        help_text="Сколько кодов создать за один раз",
    )
    length = forms.IntegerField(
        label="Длина",
        min_value=6,
        max_value=24,
        initial=10,
    )
    discount_percent = forms.IntegerField(
        label="Скидка %",
        min_value=0,
        max_value=100,
        required=False,
        initial=0,
    )
    grant_subscription = forms.BooleanField(
        label="Открыть подписку",
        required=False,
        initial=True,
    )
    extra_storage_gb = forms.IntegerField(
        label="Доп. хранилище (ГБ)",
        min_value=0,
        max_value=10240,
        required=False,
        initial=0,
    )
    valid_days = forms.IntegerField(
        label="Срок действия (дней)",
        min_value=1,
        max_value=365,
        required=False,
        help_text="Оставьте пустым для бессрочного кода",
    )
    max_uses = forms.IntegerField(
        label="Лимит активаций",
        min_value=1,
        required=False,
        help_text="Пусто — без ограничений",
    )
    description = forms.CharField(
        label="Описание",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Подсказка, для чего нужен код",
            }
        ),
    )

    def clean(self):
        data = super().clean()
        discount = data.get("discount_percent") or 0
        grant = data.get("grant_subscription")
        extra = data.get("extra_storage_gb") or 0
        if discount <= 0 and not grant and extra <= 0:
            raise forms.ValidationError(
                "Нужно выбрать хотя бы одно действие: скидку, подписку или дополнительное хранилище."
            )
        return data

    def build_expiry(self):
        days = self.cleaned_data.get("valid_days")
        if days:
            return timezone.now() + timedelta(days=days)
        return None


class UploadForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ["file"]
        widgets = {
            "file": forms.ClearableFileInput(attrs={"class": "input-file"})
        }