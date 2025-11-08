from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, redirect
from django.http import FileResponse, Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import DropFile, File
from .forms import UploadForm
from .utils import cleanup_expired_dropfiles, require_subscription


@ensure_csrf_cookie
def home(request):
    if request.user.is_authenticated:
        return redirect('files')
    return render(request, 'home.html')

def pricing(request):
    return render(request, 'pricing.html', {
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