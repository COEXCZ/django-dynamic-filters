from django.urls import path, reverse

from . import views

urlpatterns = [
    path('direct/<str:model_name>/add/', views.dynfilters_add, name='dynfilters_add'),
    path('direct/<int:expr_id>/change/', views.dynfilters_change, name='dynfilters_change'),
    path('direct/<int:expr_id>/delete/', views.dynfilters_delete, name='dynfilters_delete'),
]
