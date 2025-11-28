"""
Admin configuration for cards app.

Provides a searchable, filterable interface for browsing all cards.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import CardSet, Card


@admin.register(CardSet)
class CardSetAdmin(admin.ModelAdmin):
    """Admin interface for card sets."""

    list_display = ['number', 'name', 'card_count']
    search_fields = ['name']
    ordering = ['number']

    def card_count(self, obj):
        """Show number of cards in this set."""
        return obj.cards.count()
    card_count.short_description = 'Cards'


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    """Admin interface for individual cards."""

    # Fields to show in list view
    list_display = [
        'name', 'card_set', 'card_type', 'cost', 'influence',
        'attack', 'health', 'rarity', 'deck_buildable', 'card_image'
    ]

    # Fields to enable filtering
    list_filter = [
        'card_type', 'rarity', 'deck_buildable', 'card_set'
    ]

    # Fields to enable searching
    search_fields = ['name', 'card_text', 'unit_types']

    # Fields to show in detail view
    fieldsets = [
        ('Identity', {
            'fields': ['name', 'card_set', 'eternal_id']
        }),
        ('Card Details', {
            'fields': ['card_type', 'unit_types', 'card_text']
        }),
        ('Cost & Stats', {
            'fields': ['cost', 'influence', 'attack', 'health']
        }),
        ('Metadata', {
            'fields': ['rarity', 'deck_buildable']
        }),
        ('Links', {
            'fields': ['image_url', 'details_url'],
            'classes': ['collapse']
        }),
    ]

    # Read-only fields
    readonly_fields = ['created_at', 'updated_at']

    # Default ordering
    ordering = ['card_set', 'eternal_id']

    # Pagination
    list_per_page = 50

    def card_image(self, obj):
        """Display a thumbnail of the card image."""
        if obj.image_url:
            return format_html(
                '<img src="{}" style="max-height: 60px; max-width: 45px;" />',
                obj.image_url
            )
        return '-'
    card_image.short_description = 'Image'
