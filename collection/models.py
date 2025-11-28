"""
Models for tracking the user's card collection.

This module handles which cards the user owns and in what quantities,
including premium (foil) versions.
"""

from django.db import models
from cards.models import Card


class CollectionEntry(models.Model):
    """
    Represents the user's ownership of a specific card.

    Tracks both regular and premium copies separately.
    """

    # The card being owned
    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name='collection_entries',
        help_text="The card in the collection"
    )

    # Number of regular (non-premium) copies owned
    quantity = models.PositiveIntegerField(
        default=0,
        help_text="Number of regular copies owned"
    )

    # Number of premium (foil) copies owned
    premium_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Number of premium (foil) copies owned"
    )

    # === Timestamps ===
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Only one entry per card
        unique_together = ['card']
        verbose_name = "Collection Entry"
        verbose_name_plural = "Collection Entries"
        ordering = ['card__card_set', 'card__eternal_id']

    def __str__(self):
        parts = []
        if self.quantity > 0:
            parts.append(f"{self.quantity}x")
        if self.premium_quantity > 0:
            parts.append(f"{self.premium_quantity}x premium")
        return f"{self.card.name}: {', '.join(parts)}"

    @property
    def total_quantity(self):
        """Total copies owned (regular + premium)."""
        return self.quantity + self.premium_quantity

    @property
    def has_playset(self):
        """
        Returns True if user owns a full playset (4 copies).

        Note: Sigils don't have a max, so this is only meaningful for non-sigils.
        """
        return self.total_quantity >= 4


class CollectionImport(models.Model):
    """
    Tracks collection import history.

    Useful for seeing when collections were updated and what changed.
    """

    # When the import occurred
    imported_at = models.DateTimeField(auto_now_add=True)

    # Number of cards added/updated
    cards_added = models.PositiveIntegerField(default=0)
    cards_updated = models.PositiveIntegerField(default=0)

    # The raw import file content (for debugging/reprocessing)
    raw_content = models.TextField(
        blank=True,
        help_text="Original import file content"
    )

    # Any notes about this import
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-imported_at']
        verbose_name = "Collection Import"
        verbose_name_plural = "Collection Imports"

    def __str__(self):
        return f"Import on {self.imported_at.strftime('%Y-%m-%d %H:%M')}: +{self.cards_added}, ~{self.cards_updated}"
