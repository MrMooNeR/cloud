from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('files', views.files, name='files'),  # без слеша, как ты и дергаешь
]
