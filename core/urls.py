from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('files', views.files, name='files'),
    path('upload', views.upload, name='upload'),
    path('d/<int:pk>', views.download, name='download'),
]
