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
