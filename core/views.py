from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import render, redirect
from django.http import FileResponse, Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import DropFile, File, PromoCode, PromoRedemption
from .forms import PromoCodeApplyForm, PromoCodeGenerateForm, UploadForm
from .utils import cleanup_expired_dropfiles, require_subscription


@ensure_csrf_cookie
def home(request):
    if request.user.is_authenticated:
        return redirect('files')
    return render(request, 'home.html')

PAID_PLAN_PRICES = {
    "standard": Decimal("299"),
    "premium": Decimal("899"),
}


def _apply_discount(amount: Decimal, percent: int) -> int:
    discounted = amount * (Decimal(100) - Decimal(percent)) / Decimal(100)
    return int(discounted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def pricing(request):
    promo_form = PromoCodeApplyForm()
    redemptions = []
    discount_info = None
    standard_price = int(PAID_PLAN_PRICES["standard"])
    premium_price = int(PAID_PLAN_PRICES["premium"])
    discounted_standard_price = standard_price
    discounted_premium_price = premium_price
    if request.user.is_authenticated:
        user_redemptions = request.user.promo_redemptions.select_related("promo")
        redemptions = list(user_redemptions[:5])
        discount_redemption = (
            user_redemptions.filter(discount_percent__gt=0)
            .order_by("-discount_percent", "-redeemed_at")
            .first()
        )
        if discount_redemption:
            percent = discount_redemption.discount_percent
            discounted_standard_price = _apply_discount(
                PAID_PLAN_PRICES["standard"], percent
            )
            discounted_premium_price = _apply_discount(
                PAID_PLAN_PRICES["premium"], percent
            )
            discount_info = {
                "percent": percent,
                "standard_price": discounted_standard_price,
                "premium_price": discounted_premium_price,
                "code": discount_redemption.promo.code,
            }
    return render(request, 'pricing.html', {
        'active_menu': 'pricing',
        'promo_form': promo_form,
        'redemptions': redemptions,
        'standard_price': standard_price,
        'premium_price': premium_price,
        'discounted_standard_price': discounted_standard_price,
        'discounted_premium_price': discounted_premium_price,
        'discount_info': discount_info,
    })


@login_required
@require_POST
def apply_promo_code(request):
    form = PromoCodeApplyForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Введите корректный промокод.")
        return redirect('pricing')
    code = form.cleaned_data["code"].strip()
    try:
        promo = PromoCode.objects.get(code__iexact=code)
    except PromoCode.DoesNotExist:
        messages.error(request, "Такого промокода не существует.")
        return redirect('pricing')
    if not promo.is_available():
        messages.error(request, "Этот промокод уже недействителен.")
        return redirect('pricing')
    try:
        with transaction.atomic():
            redemption, created = PromoRedemption.objects.get_or_create(
                promo=promo,
                user=request.user,
                defaults={
                    "discount_percent": promo.discount_percent,
                    "extra_storage_bytes": promo.extra_storage_bytes,
                    "granted_subscription": promo.grant_subscription,
                },
            )
            if not created:
                messages.error(request, "Вы уже активировали этот промокод.")
                return redirect('pricing')
            notes = promo.apply_to_user(request.user)
            promo.register_use()
    except IntegrityError:
        messages.error(request, "Не удалось активировать промокод. Попробуйте ещё раз.")
        return redirect('pricing')
    effects = list(dict.fromkeys(notes))
    if promo.discount_percent:
        effects.append(f"скидка {promo.discount_percent}%")
    if effects:
        summary = ", ".join(effects)
        messages.success(request, f"Промокод активирован: {summary}.")
    else:
        messages.success(request, "Промокод активирован.")
    return redirect('pricing')


@login_required
@user_passes_test(lambda u: u.is_staff)
def generate_promocodes(request):
    generated_codes = []
    if request.method == "POST":
        form = PromoCodeGenerateForm(request.POST)
        if form.is_valid():
            expiry = form.build_expiry()
            quantity = form.cleaned_data["quantity"]
            prefix = form.cleaned_data.get("prefix") or ""
            discount = form.cleaned_data.get("discount_percent") or 0
            grant = form.cleaned_data.get("grant_subscription")
            extra_gb = form.cleaned_data.get("extra_storage_gb") or 0
            extra_bytes = extra_gb * 1024 * 1024 * 1024
            max_uses = form.cleaned_data.get("max_uses")
            description = form.cleaned_data.get("description") or ""
            length = form.cleaned_data["length"]
            with transaction.atomic():
                for _ in range(quantity):
                    code = PromoCode.generate_code(length=length, prefix=prefix)
                    PromoCode.objects.create(
                        code=code,
                        description=description,
                        discount_percent=discount,
                        grant_subscription=grant,
                        extra_storage_bytes=extra_bytes,
                        max_uses=max_uses,
                        valid_until=expiry,
                        created_by=request.user,
                    )
                    generated_codes.append(code)
            messages.success(request, f"Создано промокодов: {len(generated_codes)}")
    else:
        form = PromoCodeGenerateForm()
    return render(request, 'promo_generate.html', {
        'form': form,
        'generated_codes': generated_codes,
        'active_menu': 'pricing',
    })

@login_required
def files(request):
    qs = File.objects.filter(owner=request.user, is_deleted=False).order_by('-uploaded_at')
    used = qs.aggregate(s=Sum('size'))['s'] or 0
    quota = request.user.storage_quota
    percent = 0 if quota == 0 else min(int(used * 100 / quota), 100)
    recent = list(qs[:12])
    return render(request, 'files.html', {
        'recent': recent,
        'used': used,
        'quota': quota,
        'percent': percent,
        'active_menu': 'files',
    })

@login_required
@require_subscription
def upload(request):
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]
            obj = File(
                owner=request.user,
                file=f,
                name=getattr(f, "name", ""),
                size=getattr(f, "size", 0),
                content_type=getattr(f, "content_type", "") or "",
            )
            obj.save()
            messages.success(request, "Файл загружен.")
            return redirect('files')
    else:
        form = UploadForm()
    return render(request, 'upload.html', {"form": form})

@login_required
def download(request, pk: int):
    try:
        obj = File.objects.get(pk=pk, owner=request.user, is_deleted=False)
    except File.DoesNotExist:
        raise Http404("File not found")
    resp = FileResponse(obj.file.open("rb"), as_attachment=True, filename=obj.name)
    return resp


@login_required
def trash(request):
    qs = File.objects.filter(owner=request.user, is_deleted=True).order_by('-deleted_at')
    active_qs = File.objects.filter(owner=request.user, is_deleted=False)
    used = active_qs.aggregate(s=Sum('size'))['s'] or 0
    quota = request.user.storage_quota
    percent = 0 if quota == 0 else min(int(used * 100 / quota), 100)
    trashed = list(qs)
    return render(request, 'trash.html', {
        'items': trashed,
        'used': used,
        'quota': quota,
        'percent': percent,
        'active_menu': 'trash',
    })


@login_required
@require_POST
def delete_file(request, pk: int):
    try:
        obj = File.objects.get(pk=pk, owner=request.user, is_deleted=False)
    except File.DoesNotExist:
        raise Http404("File not found")
    obj.is_deleted = True
    obj.deleted_at = timezone.now()
    obj.save(update_fields=["is_deleted", "deleted_at"])
    return JsonResponse({"status": "ok"})


@require_POST
def drop_upload(request):
    cleanup_expired_dropfiles()
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "Файл не найден"}, status=400)
    obj = DropFile(
        file=uploaded,
        name=getattr(uploaded, "name", ""),
        size=getattr(uploaded, "size", 0),
        content_type=getattr(uploaded, "content_type", "") or "",
    )
    obj.save()
    download_url = request.build_absolute_uri(reverse('drop_download', args=[obj.token]))
    return JsonResponse({
        "url": download_url,
        "expires_at": obj.expires_at.isoformat(),
        "name": obj.name,
        "size": obj.size,
    })


def drop_download(request, token):
    cleanup_expired_dropfiles()
    try:
        obj = DropFile.objects.get(token=token)
    except DropFile.DoesNotExist:
        raise Http404("Ссылка не найдена")
    if obj.is_expired:
        obj.delete()
        raise Http404("Ссылка устарела")
    response = FileResponse(
        obj.file.open("rb"),
        as_attachment=True,
        filename=obj.name or obj.file.name,
    )
    if obj.content_type:
        response["Content-Type"] = obj.content_type
    return response


@login_required
@require_POST
def restore_file(request, pk: int):
    try:
        obj = File.objects.get(pk=pk, owner=request.user, is_deleted=True)
    except File.DoesNotExist:
        raise Http404("File not found")
    obj.is_deleted = False
    obj.deleted_at = None
    obj.save(update_fields=["is_deleted", "deleted_at"])
    return JsonResponse({"status": "ok"})


@login_required
@require_POST
def purge_file(request, pk: int):
    try:
        obj = File.objects.get(pk=pk, owner=request.user, is_deleted=True)
    except File.DoesNotExist:
        raise Http404("File not found")
    if obj.file:
        obj.file.delete(save=False)
    obj.delete()
    return JsonResponse({"status": "ok"})