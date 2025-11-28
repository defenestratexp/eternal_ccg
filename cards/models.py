"""
Models for Eternal Card Game cards and sets.

This module defines the database schema for storing card information
imported from the EternalWarcry card database.
"""

from django.db import models


class CardSet(models.Model):
    """
    Represents an Eternal Card Game expansion set.

    Examples: "The Empty Throne" (Set 1), "Omens of the Past" (Set 2), etc.
    """
    # Set number as used in card identifiers (e.g., Set1, Set2)
    number = models.IntegerField(unique=True, help_text="Set number (e.g., 1 for Set1)")

    # Human-readable name (populated if we can find set names)
    name = models.CharField(max_length=100, blank=True, help_text="Set name (e.g., 'The Empty Throne')")

    class Meta:
        ordering = ['number']
        verbose_name = "Card Set"
        verbose_name_plural = "Card Sets"

    def __str__(self):
        if self.name:
            return f"Set {self.number}: {self.name}"
        return f"Set {self.number}"


class Card(models.Model):
    """
    Represents an individual Eternal card.

    Contains all card attributes needed for display and deck building validation.
    """

    # Card type choices
    TYPE_CHOICES = [
        ('Unit', 'Unit'),
        ('Spell', 'Spell'),
        ('Fast Spell', 'Fast Spell'),
        ('Attachment', 'Attachment'),
        ('Weapon', 'Weapon'),
        ('Relic', 'Relic'),
        ('Relic Weapon', 'Relic Weapon'),
        ('Curse', 'Curse'),
        ('Power', 'Power'),
        ('Sigil', 'Sigil'),
        ('Site', 'Site'),
        ('Curse Weapon', 'Curse Weapon'),
    ]

    # Rarity choices
    RARITY_CHOICES = [
        ('Common', 'Common'),
        ('Uncommon', 'Uncommon'),
        ('Rare', 'Rare'),
        ('Legendary', 'Legendary'),
        ('Promo', 'Promo'),
        ('Basic', 'Basic'),  # For basic sigils
        ('None', 'None'),
    ]

    # === Identity fields ===
    # Eternal's internal ID for this card
    eternal_id = models.IntegerField(help_text="Eternal's internal card ID")

    # The set this card belongs to
    card_set = models.ForeignKey(
        CardSet,
        on_delete=models.CASCADE,
        related_name='cards',
        help_text="The expansion set this card belongs to"
    )

    # Card name
    name = models.CharField(max_length=200, help_text="Card name")

    # === Card text and type ===
    # The card's rules text
    card_text = models.TextField(blank=True, help_text="Card rules text")

    # Card type (Unit, Spell, etc.)
    card_type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        help_text="Primary card type"
    )

    # Unit subtypes (e.g., "Gunslinger", "Dinosaur") - stored as JSON array
    unit_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Unit subtypes as a list (e.g., ['Gunslinger', 'Rebel'])"
    )

    # === Cost and influence ===
    # Power cost to play the card
    cost = models.IntegerField(default=0, help_text="Power cost")

    # Influence requirements as string (e.g., "{F}{F}" for 2 Fire)
    influence = models.CharField(
        max_length=50,
        blank=True,
        help_text="Influence requirement string (e.g., '{F}{F}')"
    )

    # === Combat stats (for units/weapons) ===
    attack = models.IntegerField(default=0, help_text="Attack value (units/weapons)")
    health = models.IntegerField(default=0, help_text="Health value (units) or armor (weapons)")

    # === Metadata ===
    rarity = models.CharField(
        max_length=20,
        choices=RARITY_CHOICES,
        default='Common',
        help_text="Card rarity"
    )

    # Can this card be added to decks? (Some promos/tokens cannot)
    deck_buildable = models.BooleanField(
        default=True,
        help_text="Whether this card can be added to constructed decks"
    )

    # === Images and links ===
    image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL to card image on EternalWarcry"
    )

    details_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL to card details page on EternalWarcry"
    )

    # === Timestamps ===
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # A card is unique by its set and eternal_id
        unique_together = ['card_set', 'eternal_id']
        ordering = ['card_set', 'eternal_id']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['card_type']),
            models.Index(fields=['rarity']),
            models.Index(fields=['cost']),
            models.Index(fields=['deck_buildable']),
        ]

    def __str__(self):
        return f"{self.name} (Set{self.card_set.number} #{self.eternal_id})"

    @property
    def set_card_id(self):
        """Returns the standard card identifier like 'Set1 #2'."""
        return f"Set{self.card_set.number} #{self.eternal_id}"

    @property
    def is_power_card(self):
        """Returns True if this card counts as a power card for deck building."""
        return self.card_type in ['Power', 'Sigil']

    @property
    def is_sigil(self):
        """Returns True if this is a basic Sigil (unlimited copies allowed)."""
        return self.card_type == 'Sigil' or 'Sigil' in self.name

    @property
    def has_bargain(self):
        """Returns True if this card has the Bargain keyword."""
        return 'Bargain' in self.card_text

    def get_influence_dict(self):
        """
        Parse influence string into a dictionary.

        Example: "{F}{F}{S}" -> {'F': 2, 'S': 1}
        """
        influence_count = {}
        for char in self.influence:
            if char in 'FTJPS':
                influence_count[char] = influence_count.get(char, 0) + 1
        return influence_count

    def get_factions(self):
        """
        Returns a list of faction names this card belongs to.

        Example: "{F}{S}" -> ['Fire', 'Shadow']
        """
        from django.conf import settings
        factions = []
        for code, name in settings.FACTIONS.items():
            if code in self.influence:
                factions.append(name)
        return factions
