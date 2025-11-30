"""
URL configuration for decks app.
"""

from django.urls import path
from . import views

app_name = 'decks'

urlpatterns = [
    path('', views.deck_list, name='deck_list'),
    path('create/', views.deck_create, name='deck_create'),
    path('<int:pk>/', views.deck_detail, name='deck_detail'),
    path('<int:pk>/edit/', views.deck_edit, name='deck_edit'),
    path('<int:pk>/delete/', views.deck_delete, name='deck_delete'),
    path('<int:pk>/export/', views.deck_export, name='deck_export'),
    path('<int:pk>/export/view/', views.deck_export_view, name='deck_export_view'),
    path('<int:pk>/image/', views.deck_image, name='deck_image'),
    path('<int:pk>/collection-check/', views.deck_collection_check, name='deck_collection_check'),
    # Versioning
    path('<int:pk>/versions/', views.deck_versions, name='deck_versions'),
    path('<int:pk>/versions/create/', views.deck_create_version, name='deck_create_version'),
    path('<int:pk>/versions/<int:version_number>/restore/', views.deck_restore_version, name='deck_restore_version'),
    # HTMX endpoints for deck editing
    path('<int:pk>/add-card/', views.deck_add_card, name='deck_add_card'),
    path('<int:pk>/remove-card/', views.deck_remove_card, name='deck_remove_card'),
]
