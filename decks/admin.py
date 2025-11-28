"""
Admin configuration for decks app.

Provides interface for viewing and managing decks.
"""

from django.contrib import admin
from .models import Deck, DeckCard


class DeckCardInline(admin.TabularInline):
    """Inline editor for cards in a deck."""

    model = DeckCard
    extra = 1
    autocomplete_fields = ['card']

    fields = ['card', 'quantity', 'is_market']


@admin.register(Deck)
class DeckAdmin(admin.ModelAdmin):
    """Admin interface for decks."""

    list_display = [
        'name', 'format', 'main_deck_count', 'market_count',
        'is_valid', 'updated_at'
    ]

    list_filter = ['format']

    search_fields = ['name', 'description']

    readonly_fields = ['created_at', 'updated_at']

    inlines = [DeckCardInline]

    fieldsets = [
        (None, {
            'fields': ['name', 'format', 'description']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def main_deck_count(self, obj):
        return obj.main_deck_count
    main_deck_count.short_description = 'Main Deck'

    def market_count(self, obj):
        return obj.market_count
    market_count.short_description = 'Market'

    def is_valid(self, obj):
        """Check if deck passes validation."""
        validation = obj.validate_deck()
        return validation['valid']
    is_valid.boolean = True
    is_valid.short_description = 'Valid?'


@admin.register(DeckCard)
class DeckCardAdmin(admin.ModelAdmin):
    """Admin interface for deck cards (usually edited inline)."""

    list_display = ['deck', 'card', 'quantity', 'is_market']

    list_filter = ['deck', 'is_market']

    search_fields = ['card__name', 'deck__name']

    autocomplete_fields = ['card']
