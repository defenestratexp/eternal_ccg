"""
URL configuration for cards app.
"""

from django.urls import path
from . import views

app_name = 'cards'

urlpatterns = [
    path('', views.card_list, name='card_list'),
    path('<int:pk>/', views.card_detail, name='card_detail'),
]
