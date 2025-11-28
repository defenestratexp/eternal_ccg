"""
Admin configuration for collection app.

Provides interface for viewing and managing the user's card collection.
"""

from django.contrib import admin
from .models import CollectionEntry, CollectionImport


@admin.register(CollectionEntry)
class CollectionEntryAdmin(admin.ModelAdmin):
    """Admin interface for collection entries."""

    list_display = [
        'card', 'quantity', 'premium_quantity', 'total_quantity', 'has_playset'
    ]

    list_filter = ['card__card_set', 'card__rarity']

    search_fields = ['card__name']

    # Allow inline editing of quantities
    list_editable = ['quantity', 'premium_quantity']

    ordering = ['card__card_set', 'card__eternal_id']

    list_per_page = 50

    def total_quantity(self, obj):
        return obj.total_quantity
    total_quantity.short_description = 'Total'

    def has_playset(self, obj):
        return obj.has_playset
    has_playset.boolean = True
    has_playset.short_description = 'Playset?'


@admin.register(CollectionImport)
class CollectionImportAdmin(admin.ModelAdmin):
    """Admin interface for collection import history."""

    list_display = ['imported_at', 'cards_added', 'cards_updated', 'notes']

    readonly_fields = ['imported_at', 'cards_added', 'cards_updated', 'raw_content']

    ordering = ['-imported_at']
