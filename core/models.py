from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone
from datetime import timedelta
import mimetypes
import os
import secrets

def user_upload_path(instance, filename):
    return f"u/{instance.owner_id}/{filename}"


def drop_upload_path(instance, filename):
    return f"drop/{instance.token}/{filename}"


def generate_drop_token(length: int = 10) -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class File(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="files",
    )
    file = models.FileField(upload_to=user_upload_path)
    name = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        updated = False
        if self.file and not self.name:
            self.name = os.path.basename(self.file.name)
            updated = True
        if self.file and not self.size:
            try:
                self.size = self.file.size
                updated = True
            except Exception:
                pass
        if not self.content_type:
            guess, _ = mimetypes.guess_type(self.name or "")
            if guess:
                self.content_type = guess
                updated = True
        if updated:
            super().save(update_fields=["name", "size", "content_type"])

    @property
    def is_image(self) -> bool:
        return (self.content_type or "").startswith("image/")

    @property
    def is_video(self) -> bool:
        return (self.content_type or "").startswith("video/")

    @property
    def is_pdf(self) -> bool:
        return (self.content_type or "") == "application/pdf"

    def __str__(self):
        return f"{self.owner_id}:{self.name}"


class DropFile(models.Model):
    token = models.CharField(
        max_length=16,
        unique=True,
        editable=False,
        default=generate_drop_token,
    )
    file = models.FileField(upload_to=drop_upload_path)
    name = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(blank=True)

    DEFAULT_LIFETIME = timedelta(hours=72)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + self.DEFAULT_LIFETIME
        super().save(*args, **kwargs)
        updated = False
        if self.file and not self.name:
            self.name = os.path.basename(self.file.name)
            updated = True
        if self.file and not self.size:
            try:
                self.size = self.file.size
                updated = True
            except Exception:
                pass
        if not self.content_type:
            guess, _ = mimetypes.guess_type(self.name or "")
            if guess:
                self.content_type = guess
                updated = True
        if updated:
            super().save(update_fields=["name", "size", "content_type"])

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def delete(self, *args, **kwargs):
        stored_file = self.file
        if stored_file:
            stored_file.delete(save=False)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"drop:{self.token}"


class PromoCode(models.Model):
    code = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=255, blank=True)
    discount_percent = models.PositiveSmallIntegerField(default=0)
    grant_subscription = models.BooleanField(default=False)
    extra_storage_bytes = models.BigIntegerField(default=0)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    use_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_promocodes",
    )

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def generate_code(length: int = 10, prefix: str = "") -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        token = "".join(secrets.choice(alphabet) for _ in range(length))
        if prefix:
            return f"{prefix.upper()}-{token}"
        return token

    def is_available(self) -> bool:
        if not self.active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses is not None and self.use_count >= self.max_uses:
            return False
        return True

    def register_use(self):
        PromoCode.objects.filter(pk=self.pk).update(use_count=F("use_count") + 1)
        self.refresh_from_db(fields=["use_count"])

    def apply_to_user(self, user):
        updates = set()
        notes = []
        if self.grant_subscription and not user.is_subscribed:
            user.is_subscribed = True
            updates.add("is_subscribed")
            notes.append("подписка активирована")
        if self.extra_storage_bytes:
            user.storage_quota = max(0, user.storage_quota) + self.extra_storage_bytes
            updates.add("storage_quota")
            notes.append(f"квота увеличена на {self.format_storage(self.extra_storage_bytes)}")
        if updates:
            user.save(update_fields=list(updates))
        return notes

    @staticmethod
    def format_storage(value: int) -> str:
        if value >= 1024 ** 4:
            tb = value / float(1024 ** 4)
            return f"{tb:g} ТБ"
        gb = value / float(1024 ** 3)
        if gb >= 1:
            return f"{gb:g} ГБ"
        mb = value / float(1024 ** 2)
        if mb >= 1:
            return f"{mb:g} МБ"
        kb = value / 1024
        if kb >= 1:
            return f"{kb:g} КБ"
        return f"{value} Б"

    def __str__(self):
        return self.code


class PromoRedemption(models.Model):
    promo = models.ForeignKey(
        PromoCode,
        on_delete=models.CASCADE,
        related_name="redemptions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="promo_redemptions",
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)
    discount_percent = models.PositiveSmallIntegerField(default=0)
    extra_storage_bytes = models.BigIntegerField(default=0)
    granted_subscription = models.BooleanField(default=False)

    class Meta:
        unique_together = ("promo", "user")
        ordering = ["-redeemed_at"]

    @property
    def extra_storage_display(self) -> str:
        if not self.extra_storage_bytes:
            return ""
        return PromoCode.format_storage(self.extra_storage_bytes)

    def __str__(self):
        return f"{self.user_id}:{self.promo_id}"