from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import DropFile, PromoCode, PromoRedemption


class DropFileTests(TestCase):
    def test_upload_creates_short_lived_link(self):
        payload = SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")
        response = self.client.post(reverse("drop_upload"), {"file": payload})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("url", data)
        self.assertIn("expires_at", data)

        stored = DropFile.objects.get()
        self.assertIn(str(stored.token), data["url"])
        self.assertLessEqual(len(stored.token), 12)
        self.assertIn('/s/', data["url"])
        lifetime = stored.expires_at - stored.created_at
        self.assertAlmostEqual(lifetime.total_seconds(), 72 * 3600, delta=120)
        self.assertFalse(stored.is_expired)

    def test_download_and_expiration_cleanup(self):
        obj = DropFile.objects.create(
            file=SimpleUploadedFile("doc.txt", b"data", content_type="text/plain"),
        )

        url = reverse("drop_download", args=[obj.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"data")

        obj.refresh_from_db()
        obj.expires_at = timezone.now() - timedelta(minutes=5)
        obj.save(update_fields=["expires_at"])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(DropFile.objects.filter(pk=obj.pk).exists())


class PricingViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="test@example.com", password="strong-pass"
        )

    def test_discount_context_is_exposed(self):
        promo = PromoCode.objects.create(
            code="SAVE25",
            discount_percent=25,
        )
        PromoRedemption.objects.create(
            promo=promo,
            user=self.user,
            discount_percent=25,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("pricing"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["standard_price"], 299)
        self.assertEqual(response.context["premium_price"], 899)
        self.assertEqual(response.context["discounted_standard_price"], 224)
        self.assertEqual(response.context["discounted_premium_price"], 674)

        info = response.context["discount_info"]
        self.assertIsNotNone(info)
        self.assertEqual(info["percent"], 25)
        self.assertEqual(info["standard_price"], 224)
        self.assertEqual(info["premium_price"], 674)