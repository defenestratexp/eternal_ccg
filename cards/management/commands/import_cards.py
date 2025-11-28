"""
Management command to import cards from EternalWarcry JSON.

Usage:
    python manage.py import_cards
    python manage.py import_cards --file /path/to/eternal-cards.json
    python manage.py import_cards --clear  # Clear existing cards first
"""

import json
from django.core.management.base import BaseCommand
from django.conf import settings
from cards.models import Card, CardSet


class Command(BaseCommand):
    help = 'Import cards from EternalWarcry JSON file'

    def add_arguments(self, parser):
        # Optional: specify a different JSON file
        parser.add_argument(
            '--file',
            type=str,
            default=str(settings.CARD_DATA_FILE),
            help='Path to the eternal-cards.json file'
        )
        # Optional: clear existing cards before import
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing cards before importing'
        )

    def handle(self, *args, **options):
        json_file = options['file']

        self.stdout.write(f"Loading cards from: {json_file}")

        # Load JSON data
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                cards_data = json.load(f)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {json_file}"))
            return
        except json.JSONDecodeError as e:
            self.stderr.write(self.style.ERROR(f"Invalid JSON: {e}"))
            return

        self.stdout.write(f"Found {len(cards_data)} cards in JSON")

        # Optionally clear existing data
        if options['clear']:
            self.stdout.write("Clearing existing cards...")
            Card.objects.all().delete()
            CardSet.objects.all().delete()

        # Track statistics
        sets_created = 0
        cards_created = 0
        cards_updated = 0
        cards_skipped = 0

        # Process each card
        for idx, card_data in enumerate(cards_data):
            try:
                result = self._import_card(card_data, index=idx)
                if result == 'created':
                    cards_created += 1
                elif result == 'updated':
                    cards_updated += 1
                elif result == 'set_created':
                    sets_created += 1
                    cards_created += 1
            except Exception as e:
                cards_skipped += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"Skipped card: {card_data.get('Name', 'Unknown')} - {e}"
                    )
                )

        # Count total sets
        total_sets = CardSet.objects.count()

        # Report results
        self.stdout.write(self.style.SUCCESS(
            f"\nImport complete!"
            f"\n  Sets: {total_sets} ({sets_created} new)"
            f"\n  Cards created: {cards_created}"
            f"\n  Cards updated: {cards_updated}"
            f"\n  Cards skipped: {cards_skipped}"
        ))

    def _import_card(self, data, index=0):
        """
        Import a single card from JSON data.

        Returns 'created', 'updated', or 'set_created' (if a new set was made).
        """
        # Get or create the set
        set_number = data.get('SetNumber', 0)
        set_name = data.get('SetName', '')
        card_set, set_created = CardSet.objects.get_or_create(
            number=set_number,
            defaults={'name': set_name}
        )
        # Update set name if we have it and set was missing it
        if set_name and not card_set.name:
            card_set.name = set_name
            card_set.save()

        # Extract card data with defaults
        # Use EternalID if present, otherwise generate from index
        eternal_id = data.get('EternalID')
        if eternal_id is None:
            # Generate a unique ID based on set and index
            eternal_id = set_number * 10000 + index

        # Map JSON fields to model fields
        card_data = {
            'name': data.get('Name', ''),
            'card_text': data.get('CardText', ''),
            'card_type': data.get('Type', 'Unknown'),
            'unit_types': data.get('UnitType', []) or [],
            'cost': data.get('Cost', 0) or 0,
            'influence': data.get('Influence', ''),
            'attack': data.get('Attack', 0) or 0,
            'health': data.get('Health', 0) or 0,
            'rarity': data.get('Rarity', 'Common') or 'Common',
            'deck_buildable': data.get('DeckBuildable', True),
            'image_url': data.get('ImageUrl', ''),
            'details_url': data.get('DetailsUrl', ''),
        }

        # Create or update the card
        card, created = Card.objects.update_or_create(
            card_set=card_set,
            eternal_id=eternal_id,
            defaults=card_data
        )

        if set_created:
            return 'set_created'
        elif created:
            return 'created'
        else:
            return 'updated'
