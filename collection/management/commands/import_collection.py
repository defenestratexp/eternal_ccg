"""
Management command to import collection from Eternal export format.

Usage:
    python manage.py import_collection /path/to/collection.txt
    python manage.py import_collection --clear  # Clear existing collection first
"""

import re
from django.core.management.base import BaseCommand
from cards.models import Card, CardSet
from collection.models import CollectionEntry, CollectionImport


class Command(BaseCommand):
    help = 'Import collection from Eternal export file'

    def add_arguments(self, parser):
        # Required: path to collection file
        parser.add_argument(
            'file',
            type=str,
            help='Path to the collection export file'
        )
        # Optional: clear existing collection before import
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing collection before importing'
        )

    def handle(self, *args, **options):
        file_path = options['file']

        self.stdout.write(f"Loading collection from: {file_path}")

        # Load file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.strip().split('\n')
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        # Optionally clear existing collection
        if options['clear']:
            self.stdout.write("Clearing existing collection...")
            CollectionEntry.objects.all().delete()

        # Track statistics
        cards_added = 0
        cards_updated = 0
        cards_skipped = 0

        # Regex to parse collection lines
        # Format: "4 Card Name (Set# #CardNumber)" or "4 Card Name *Premium* (Set# #CardNumber)"
        pattern = re.compile(
            r'^(\d+)\s+'           # Quantity
            r'(.+?)\s+'            # Card name
            r'(\*Premium\*\s+)?'   # Optional premium marker
            r'\(Set(\d+)\s+#(\d+)\)$'  # Set and card number
        )

        for line in lines:
            line = line.strip()
            if not line:
                continue

            match = pattern.match(line)
            if not match:
                # Skip non-card lines (like format headers)
                if line.startswith('FORMAT:') or line.startswith('---'):
                    continue
                self.stdout.write(
                    self.style.WARNING(f"Could not parse line: {line}")
                )
                cards_skipped += 1
                continue

            quantity = int(match.group(1))
            card_name = match.group(2)
            is_premium = match.group(3) is not None
            set_number = int(match.group(4))
            card_number = int(match.group(5))

            # Find the card in the database
            try:
                card_set = CardSet.objects.get(number=set_number)
                card = Card.objects.get(card_set=card_set, eternal_id=card_number)
            except CardSet.DoesNotExist:
                self.stderr.write(
                    self.style.WARNING(
                        f"Set {set_number} not found for: {card_name}"
                    )
                )
                cards_skipped += 1
                continue
            except Card.DoesNotExist:
                self.stderr.write(
                    self.style.WARNING(
                        f"Card not found: {card_name} (Set{set_number} #{card_number})"
                    )
                )
                cards_skipped += 1
                continue

            # Get or create collection entry
            entry, created = CollectionEntry.objects.get_or_create(card=card)

            # Update quantities
            if is_premium:
                entry.premium_quantity = quantity
            else:
                entry.quantity = quantity

            entry.save()

            if created:
                cards_added += 1
            else:
                cards_updated += 1

        # Record the import
        CollectionImport.objects.create(
            cards_added=cards_added,
            cards_updated=cards_updated,
            raw_content=content,
            notes=f"Imported from {file_path}"
        )

        # Report results
        self.stdout.write(self.style.SUCCESS(
            f"\nImport complete!"
            f"\n  Cards added: {cards_added}"
            f"\n  Cards updated: {cards_updated}"
            f"\n  Cards skipped: {cards_skipped}"
        ))
