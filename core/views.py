from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

def home(request):
    if request.user.is_authenticated:
        return redirect('files')
    return render(request, 'home.html')

@login_required
def files(request):
    return render(request, 'files.html')
