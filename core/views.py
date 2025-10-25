from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, redirect
from django.http import FileResponse, Http404

from .models import File
from .forms import UploadForm
from .utils import require_subscription

def home(request):
    if request.user.is_authenticated:
        return redirect('files')
    return render(request, 'home.html')

@login_required
def files(request):
    qs = File.objects.filter(owner=request.user).order_by('-uploaded_at')
    used = qs.aggregate(s=Sum('size'))['s'] or 0
    quota = request.user.storage_quota
    percent = 0 if quota == 0 else min(int(used * 100 / quota), 100)
    recent = list(qs[:12])
    return render(request, 'files.html', {
        'recent': recent,
        'used': used,
        'quota': quota,
        'percent': percent,
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
        obj = File.objects.get(pk=pk, owner=request.user)
    except File.DoesNotExist:
        raise Http404("File not found")
    resp = FileResponse(obj.file.open("rb"), as_attachment=True, filename=obj.name)
    return resp