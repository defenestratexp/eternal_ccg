"""
Models for deck building and management.

This module handles deck creation, card slots, and deck validation
according to Eternal Card Game rules.
"""

from django.db import models
from django.conf import settings
from cards.models import Card


class Deck(models.Model):
    """
    Represents a constructed deck.

    A deck consists of a main deck (75-150 cards) and an optional market (up to 5 cards).
    """

    # Format choices
    FORMAT_CHOICES = [
        ('Throne', 'Throne'),      # All cards legal
        ('Expedition', 'Expedition'),  # Rotating format
    ]

    # Deck name
    name = models.CharField(max_length=200, help_text="Deck name")

    # Deck format
    format = models.CharField(
        max_length=20,
        choices=FORMAT_CHOICES,
        default='Throne',
        help_text="Game format (Throne or Expedition)"
    )

    # Optional description/notes
    description = models.TextField(blank=True, help_text="Deck description or notes")

    # Archetype/tags for categorization
    tags = models.ManyToManyField(
        'DeckTag',
        blank=True,
        related_name='decks',
        help_text="Tags/archetypes for this deck"
    )

    # Primary archetype (e.g., "Aggro", "Midrange", "Control", "Combo")
    archetype = models.CharField(
        max_length=50,
        blank=True,
        help_text="Primary archetype (Aggro, Midrange, Control, Combo)"
    )

    # === Timestamps ===
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.format})"

    @property
    def main_deck_cards(self):
        """Returns all cards in the main deck (not market)."""
        return self.cards.filter(is_market=False)

    @property
    def market_cards(self):
        """Returns all cards in the market."""
        return self.cards.filter(is_market=True)

    @property
    def main_deck_count(self):
        """Total number of cards in main deck."""
        return sum(dc.quantity for dc in self.main_deck_cards)

    @property
    def market_count(self):
        """Total number of cards in market."""
        return sum(dc.quantity for dc in self.market_cards)

    @property
    def power_count(self):
        """Number of power cards in main deck."""
        return sum(
            dc.quantity for dc in self.main_deck_cards
            if dc.card.is_power_card
        )

    @property
    def non_power_count(self):
        """Number of non-power cards in main deck."""
        return sum(
            dc.quantity for dc in self.main_deck_cards
            if not dc.card.is_power_card
        )

    def validate_deck(self):
        """
        Validates the deck against Eternal deck building rules.

        Returns a dict with:
            - 'valid': bool - whether deck is valid
            - 'errors': list - list of validation error messages
            - 'warnings': list - list of warnings (not blocking)
        """
        rules = settings.DECK_RULES
        errors = []
        warnings = []

        main_count = self.main_deck_count
        market_count = self.market_count
        power_count = self.power_count
        non_power_count = self.non_power_count

        # === Main deck size ===
        if main_count < rules['MIN_DECK_SIZE']:
            errors.append(
                f"Main deck has {main_count} cards (minimum {rules['MIN_DECK_SIZE']})"
            )
        if main_count > rules['MAX_DECK_SIZE']:
            errors.append(
                f"Main deck has {main_count} cards (maximum {rules['MAX_DECK_SIZE']})"
            )

        # === Power ratio (at least 1/3 power) ===
        min_power = (main_count + 2) // 3  # Rounded up
        if power_count < min_power:
            errors.append(
                f"Need at least {min_power} power cards (have {power_count})"
            )

        # === Non-power ratio (at least 1/3 non-power) ===
        min_non_power = (main_count + 2) // 3  # Rounded up
        if non_power_count < min_non_power:
            errors.append(
                f"Need at least {min_non_power} non-power cards (have {non_power_count})"
            )

        # === Market size ===
        if market_count > rules['MAX_MARKET_SIZE']:
            errors.append(
                f"Market has {market_count} cards (maximum {rules['MAX_MARKET_SIZE']})"
            )

        # === Card copy limits ===
        # Check main deck card counts (max 4 of any non-sigil)
        card_counts = {}  # card_id -> total count
        for dc in self.main_deck_cards:
            card_counts[dc.card_id] = card_counts.get(dc.card_id, 0) + dc.quantity

        for dc in self.main_deck_cards:
            count = card_counts.get(dc.card_id, 0)
            if count > rules['MAX_COPIES_PER_CARD'] and not dc.card.is_sigil:
                errors.append(
                    f"Too many copies of {dc.card.name}: {count} (max {rules['MAX_COPIES_PER_CARD']})"
                )

        # === Market rules ===
        # Only 1 copy of each card in market
        for dc in self.market_cards:
            if dc.quantity > rules['MAX_COPIES_IN_MARKET']:
                errors.append(
                    f"Market can only have 1 copy of {dc.card.name}"
                )

        # No card in both deck and market (except sigils and bargain)
        main_card_ids = set(dc.card_id for dc in self.main_deck_cards)
        for dc in self.market_cards:
            if dc.card_id in main_card_ids:
                if not dc.card.is_sigil and not dc.card.has_bargain:
                    errors.append(
                        f"{dc.card.name} cannot be in both main deck and market"
                    )

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
        }

    def export_to_eternal_format(self):
        """
        Exports the deck in Eternal's import/export format.

        Format:
            FORMAT:Throne
            4 Card Name (Set# #CardNumber)
            ...
            ---------------MARKET---------------
            1 Market Card (Set# #CardNumber)
        """
        lines = [f"FORMAT:{self.format}"]

        # Main deck cards, sorted by cost then name
        main_cards = sorted(
            self.main_deck_cards,
            key=lambda dc: (dc.card.cost, dc.card.name)
        )
        for dc in main_cards:
            lines.append(
                f"{dc.quantity} {dc.card.name} ({dc.card.set_card_id})"
            )

        # Market
        if self.market_count > 0:
            lines.append("---------------MARKET---------------")
            for dc in self.market_cards:
                lines.append(
                    f"{dc.quantity} {dc.card.name} ({dc.card.set_card_id})"
                )

        return "\n".join(lines)

    def create_version_snapshot(self, notes=""):
        """
        Creates a snapshot of the current deck state.

        Returns the created DeckVersion instance.
        """
        # Import here to avoid circular import
        from .models import DeckVersion, DeckVersionCard

        # Determine next version number
        last_version = self.versions.order_by('-version_number').first()
        next_version = (last_version.version_number + 1) if last_version else 1

        # Create version record
        version = DeckVersion.objects.create(
            deck=self,
            version_number=next_version,
            notes=notes
        )

        # Copy all current cards to version
        for dc in self.cards.all():
            DeckVersionCard.objects.create(
                deck_version=version,
                card=dc.card,
                quantity=dc.quantity,
                is_market=dc.is_market
            )

        return version

    def restore_version(self, version_number):
        """
        Restores the deck to a previous version.

        Creates a snapshot of current state first, then replaces cards.
        Returns the restored DeckVersion.
        """
        # Get the version to restore
        version = self.versions.get(version_number=version_number)

        # Create snapshot of current state before restoring
        self.create_version_snapshot(notes=f"Auto-snapshot before restoring to v{version_number}")

        # Clear current cards
        self.cards.all().delete()

        # Copy cards from version
        for vc in version.cards.all():
            DeckCard.objects.create(
                deck=self,
                card=vc.card,
                quantity=vc.quantity,
                is_market=vc.is_market
            )

        return version

    @property
    def current_version_number(self):
        """Returns the next version number (current working state)."""
        last_version = self.versions.order_by('-version_number').first()
        return (last_version.version_number + 1) if last_version else 1


class DeckVersion(models.Model):
    """
    Represents a snapshot of a deck at a point in time.

    Used for version history and rollback functionality.
    """

    # The deck this version belongs to
    deck = models.ForeignKey(
        Deck,
        on_delete=models.CASCADE,
        related_name='versions',
        help_text="The deck this version belongs to"
    )

    # Version number (1, 2, 3...)
    version_number = models.PositiveIntegerField(
        help_text="Version number"
    )

    # When this version was created
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional notes about this version
    notes = models.CharField(
        max_length=500,
        blank=True,
        help_text="Notes about what changed in this version"
    )

    class Meta:
        ordering = ['-version_number']
        unique_together = ['deck', 'version_number']

    def __str__(self):
        return f"{self.deck.name} v{self.version_number}"

    @property
    def main_deck_count(self):
        """Total number of cards in main deck for this version."""
        return sum(vc.quantity for vc in self.cards.filter(is_market=False))

    @property
    def market_count(self):
        """Total number of cards in market for this version."""
        return sum(vc.quantity for vc in self.cards.filter(is_market=True))


class DeckVersionCard(models.Model):
    """
    Represents a card slot in a deck version snapshot.
    """

    # The version this card belongs to
    deck_version = models.ForeignKey(
        DeckVersion,
        on_delete=models.CASCADE,
        related_name='cards',
        help_text="The deck version containing this card"
    )

    # The card
    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name='version_entries',
        help_text="The card in this version"
    )

    # Number of copies
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Number of copies in this slot"
    )

    # Is this card in the market?
    is_market = models.BooleanField(
        default=False,
        help_text="True if this card is in the market"
    )

    class Meta:
        ordering = ['is_market', 'card__cost', 'card__name']

    def __str__(self):
        location = "Market" if self.is_market else "Main"
        return f"{self.quantity}x {self.card.name} [{location}]"


class DeckTag(models.Model):
    """
    Represents a tag or archetype label for categorizing decks.
    """
    name = models.CharField(max_length=50, unique=True, help_text="Tag name")
    color = models.CharField(
        max_length=20,
        default='gray',
        help_text="Tailwind color class (e.g., 'red', 'blue', 'green')"
    )
    description = models.CharField(max_length=200, blank=True, help_text="Tag description")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class DeckMatchup(models.Model):
    """
    Represents matchup information between two decks or deck archetypes.
    """
    MATCHUP_CHOICES = [
        ('favorable', 'Favorable'),
        ('even', 'Even'),
        ('unfavorable', 'Unfavorable'),
        ('unknown', 'Unknown'),
    ]

    # The deck this matchup is for
    deck = models.ForeignKey(
        'Deck',
        on_delete=models.CASCADE,
        related_name='matchups',
        help_text="The deck this matchup is recorded for"
    )

    # Opponent - can be another deck or just a tag/archetype name
    opponent_deck = models.ForeignKey(
        'Deck',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matchups_against',
        help_text="Specific opponent deck (optional)"
    )

    opponent_archetype = models.CharField(
        max_length=100,
        blank=True,
        help_text="Opponent archetype name (e.g., 'Aggro', 'FJS Midrange')"
    )

    # Matchup assessment
    assessment = models.CharField(
        max_length=20,
        choices=MATCHUP_CHOICES,
        default='unknown',
        help_text="How favorable is this matchup"
    )

    # Win rate tracking
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)

    # Notes about the matchup
    notes = models.TextField(
        blank=True,
        help_text="Strategy notes for this matchup"
    )

    # Key cards to look for
    key_cards = models.CharField(
        max_length=500,
        blank=True,
        help_text="Important cards in this matchup (comma-separated)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        opponent = self.opponent_deck.name if self.opponent_deck else self.opponent_archetype
        return f"{self.deck.name} vs {opponent}"

    @property
    def win_rate(self):
        """Calculate win rate percentage."""
        total = self.wins + self.losses
        if total == 0:
            return None
        return round(self.wins / total * 100, 1)

    @property
    def total_games(self):
        return self.wins + self.losses


class DeckCard(models.Model):
    """
    Represents a card slot in a deck.

    Links a card to a deck with a quantity, and tracks whether
    it's in the main deck or market.
    """

    # The deck this card belongs to
    deck = models.ForeignKey(
        Deck,
        on_delete=models.CASCADE,
        related_name='cards',
        help_text="The deck containing this card"
    )

    # The card
    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name='deck_entries',
        help_text="The card in the deck"
    )

    # Number of copies
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Number of copies in this slot"
    )

    # Is this card in the market (sideboard)?
    is_market = models.BooleanField(
        default=False,
        help_text="True if this card is in the market, False if main deck"
    )

    class Meta:
        # A card can only appear once per deck (in main or market)
        unique_together = ['deck', 'card', 'is_market']
        ordering = ['is_market', 'card__cost', 'card__name']

    def __str__(self):
        location = "Market" if self.is_market else "Main"
        return f"{self.quantity}x {self.card.name} [{location}]"
