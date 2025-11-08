from django.conf import settings
from django.db import models
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