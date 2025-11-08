from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('files', views.files, name='files'),
    path('trash', views.trash, name='trash'),
    path('pricing', views.pricing, name='pricing'),
    path('pricing/apply-promo', views.apply_promo_code, name='apply_promo_code'),
    path('upload', views.upload, name='upload'),
    path('d/<int:pk>', views.download, name='download'),
    path('f/<int:pk>/delete', views.delete_file, name='file_delete'),
    path('f/<int:pk>/restore', views.restore_file, name='file_restore'),
    path('f/<int:pk>/purge', views.purge_file, name='file_purge'),
    path('drop/upload/', views.drop_upload, name='drop_upload'),
    path('s/<str:token>/', views.drop_download, name='drop_download'),
    path('promo/generate', views.generate_promocodes, name='generate_promocodes'),
]