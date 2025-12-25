"""
URL configuration for eternal_forge project.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.http import JsonResponse


def health_check(request):
    """Health check endpoint for Kubernetes probes."""
    return JsonResponse({'status': 'healthy'})


def home(request):
    """Home page with dashboard stats."""
    from cards.models import Card, CardSet
    from collection.models import CollectionEntry
    from decks.models import Deck

    context = {
        'total_cards': Card.objects.count(),
        'total_sets': CardSet.objects.count(),
        'collection_size': CollectionEntry.objects.count(),
        'total_owned': sum(e.total_quantity for e in CollectionEntry.objects.all()),
        'deck_count': Deck.objects.count(),
    }
    return render(request, 'home.html', context)


urlpatterns = [
    path('', home, name='home'),
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('cards/', include('cards.urls')),
    path('decks/', include('decks.urls')),
    path('collection/', include('collection.urls')),
]
