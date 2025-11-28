"""
Views for the collection app.

Provides collection viewing and upload functionality.
"""

import re
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from cards.models import Card, CardSet
from .models import CollectionEntry, CollectionImport


def collection_view(request):
    """
    View the user's card collection.
    """
    entries = CollectionEntry.objects.select_related('card__card_set').order_by(
        'card__name'
    )

    # Search/filter
    search = request.GET.get('search', '').strip()
    if search:
        entries = entries.filter(card__name__icontains=search)

    # Filter by owned status
    owned_filter = request.GET.get('owned', '')
    if owned_filter == 'playset':
        # Cards with 4+ copies
        entries = [e for e in entries if e.total_quantity >= 4]
    elif owned_filter == 'incomplete':
        # Cards with less than 4 copies
        entries = [e for e in entries if e.total_quantity < 4]

    # Stats
    total_entries = CollectionEntry.objects.count()
    total_cards = sum(e.total_quantity for e in CollectionEntry.objects.all())
    total_unique = CollectionEntry.objects.count()

    context = {
        'entries': entries,
        'search': search,
        'owned_filter': owned_filter,
        'total_entries': total_entries,
        'total_cards': total_cards,
        'total_unique': total_unique,
    }
    return render(request, 'collection/collection_view.html', context)


def collection_upload(request):
    """
    Upload a collection export file.
    """
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if not content:
            # Try file upload
            uploaded_file = request.FILES.get('file')
            if uploaded_file:
                content = uploaded_file.read().decode('utf-8')

        if not content:
            messages.error(request, 'No content provided.')
            return redirect('collection:collection_upload')

        # Parse and import
        result = import_collection_content(content)

        messages.success(
            request,
            f"Import complete: {result['added']} cards added, "
            f"{result['updated']} updated, {result['skipped']} skipped."
        )
        return redirect('collection:collection_view')

    return render(request, 'collection/collection_upload.html')


def collection_analysis(request):
    """
    Analyze collection completeness - what's missing by rarity and set.
    """
    from collections import defaultdict

    # Get all owned card IDs
    owned_card_ids = set(CollectionEntry.objects.values_list('card_id', flat=True))

    # All cards and missing cards
    all_cards = Card.objects.select_related('card_set').all()
    total_cards = all_cards.count()
    cards_owned = len(owned_card_ids)

    # Separate missing cards
    missing_cards = [c for c in all_cards if c.pk not in owned_card_ids]

    # Group by rarity
    by_rarity = defaultdict(list)
    for card in missing_cards:
        rarity = card.rarity or 'None'
        by_rarity[rarity].append(card)

    # Sort rarities in logical order
    rarity_order = ['Legendary', 'Rare', 'Uncommon', 'Common', 'Promo', 'None']
    rarity_stats = []
    for rarity in rarity_order:
        if rarity in by_rarity:
            rarity_stats.append({
                'name': rarity,
                'count': len(by_rarity[rarity]),
                'cards': sorted(by_rarity[rarity], key=lambda c: c.name),
            })

    # Group by set
    by_set = defaultdict(list)
    for card in missing_cards:
        set_name = card.card_set.name if card.card_set else 'Unknown'
        by_set[set_name].append(card)

    # Sort sets by count descending
    set_stats = []
    for set_name, cards in sorted(by_set.items(), key=lambda x: -len(x[1])):
        set_stats.append({
            'name': set_name,
            'count': len(cards),
            'cards': sorted(cards, key=lambda c: c.name),
        })

    # Collection completeness by set (for all sets)
    all_sets = CardSet.objects.all().order_by('number')
    set_completeness = []
    for card_set in all_sets:
        set_cards = Card.objects.filter(card_set=card_set)
        set_total = set_cards.count()
        if set_total == 0:
            continue
        set_owned = set_cards.filter(pk__in=owned_card_ids).count()
        set_completeness.append({
            'name': card_set.name,
            'owned': set_owned,
            'total': set_total,
            'missing': set_total - set_owned,
            'percent': round(set_owned / set_total * 100, 1) if set_total else 0,
        })

    context = {
        'total_cards': total_cards,
        'cards_owned': cards_owned,
        'cards_missing': len(missing_cards),
        'coverage_percent': round(cards_owned / total_cards * 100, 1) if total_cards else 0,
        'rarity_stats': rarity_stats,
        'set_stats': set_stats,
        'set_completeness': set_completeness,
    }
    return render(request, 'collection/collection_analysis.html', context)


def import_collection_content(content):
    """
    Parse collection export content and update database.

    Returns dict with counts: added, updated, skipped.
    """
    # Regex for collection lines
    # Format: "4 Card Name (Set# #CardNumber)" or "4 Card Name *Premium* (Set# #CardNumber)"
    pattern = re.compile(
        r'^(\d+)\s+'           # Quantity
        r'(.+?)\s+'            # Card name
        r'(\*Premium\*\s+)?'   # Optional premium marker
        r'\(Set(\d+)\s+#(\d+)\)$'  # Set and card number
    )

    added = 0
    updated = 0
    skipped = 0

    lines = content.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = pattern.match(line)
        if not match:
            # Skip non-card lines
            skipped += 1
            continue

        quantity = int(match.group(1))
        is_premium = match.group(3) is not None
        set_number = int(match.group(4))
        card_number = int(match.group(5))

        # Find the card
        try:
            card_set = CardSet.objects.get(number=set_number)
            card = Card.objects.get(card_set=card_set, eternal_id=card_number)
        except (CardSet.DoesNotExist, Card.DoesNotExist):
            skipped += 1
            continue

        # Update collection entry
        entry, created = CollectionEntry.objects.get_or_create(card=card)

        if is_premium:
            entry.premium_quantity = quantity
        else:
            entry.quantity = quantity

        entry.save()

        if created:
            added += 1
        else:
            updated += 1

    # Record the import
    CollectionImport.objects.create(
        cards_added=added,
        cards_updated=updated,
        raw_content=content,
        notes='Web upload'
    )

    return {
        'added': added,
        'updated': updated,
        'skipped': skipped,
    }
