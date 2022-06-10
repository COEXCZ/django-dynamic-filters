from django.urls import path

from . import views

urlpatterns = [
    path('<str:name>/add/', views.dynfilters_add, name='dynfilters_add'),
    path('<int:id>/share/', views.dynfilters_share, name='dynfilters_share'),
    path('<int:id>/delete/', views.dynfilters_delete, name='dynfilters_delete'),
]
