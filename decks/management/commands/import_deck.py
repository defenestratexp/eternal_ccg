"""
Management command to import a deck from Eternal's export format.

Usage:
    python manage.py import_deck deck_file.txt
    python manage.py import_deck deck_file.txt --name "My Deck"
"""

import re
from django.core.management.base import BaseCommand
from cards.models import Card, CardSet
from decks.models import Deck, DeckCard


class Command(BaseCommand):
    help = 'Import a deck from Eternal export format'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to deck file')
        parser.add_argument('--name', type=str, help='Deck name (default: from filename)')

    def handle(self, *args, **options):
        deck_file = options['file']

        with open(deck_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse format line
        format_match = re.search(r'FORMAT:(\w+)', content)
        deck_format = format_match.group(1) if format_match else 'Throne'

        # Determine deck name
        deck_name = options.get('name')
        if not deck_name:
            import os
            deck_name = os.path.splitext(os.path.basename(deck_file))[0].replace('_', ' ').title()

        # Create the deck
        deck = Deck.objects.create(name=deck_name, format=deck_format)
        self.stdout.write(f"Created deck: {deck_name} ({deck_format})")

        # Parse cards
        in_market = False
        cards_added = 0
        cards_skipped = 0

        # Pattern: "4 Card Name (Set1 #123)" or "4 Card Name (Set1085 #15)"
        card_pattern = re.compile(r'^(\d+)\s+(.+?)\s+\(Set(\d+)\s+#(\d+)\)')

        for line in content.split('\n'):
            line = line.strip()

            if not line or line.startswith('FORMAT:'):
                continue

            if 'MARKET' in line:
                in_market = True
                continue

            match = card_pattern.match(line)
            if not match:
                continue

            quantity = int(match.group(1))
            card_name = match.group(2)
            set_number = int(match.group(3))
            eternal_id = int(match.group(4))

            # Find the card
            try:
                card = Card.objects.get(
                    card_set__number=set_number,
                    eternal_id=eternal_id
                )
            except Card.DoesNotExist:
                # Try by name as fallback
                try:
                    card = Card.objects.get(name=card_name)
                except (Card.DoesNotExist, Card.MultipleObjectsReturned):
                    self.stderr.write(f"  Skipped: {card_name} (Set{set_number} #{eternal_id}) - not found")
                    cards_skipped += 1
                    continue

            # Add to deck
            DeckCard.objects.create(
                deck=deck,
                card=card,
                quantity=quantity,
                is_market=in_market
            )
            cards_added += 1
            self.stdout.write(f"  Added: {quantity}x {card.name} {'(Market)' if in_market else ''}")

        self.stdout.write(self.style.SUCCESS(
            f"\nImport complete! {cards_added} cards added, {cards_skipped} skipped"
        ))
        self.stdout.write(f"Deck ID: {deck.pk}")
