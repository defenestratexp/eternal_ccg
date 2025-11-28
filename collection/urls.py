"""
URL configuration for collection app.
"""

from django.urls import path
from . import views

app_name = 'collection'

urlpatterns = [
    path('', views.collection_view, name='collection_view'),
    path('upload/', views.collection_upload, name='collection_upload'),
]
