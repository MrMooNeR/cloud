from django.conf import settings
from django.db import models
from django.utils import timezone
import os
import mimetypes

def user_upload_path(instance, filename):
    return f"u/{instance.owner_id}/{filename}"

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
