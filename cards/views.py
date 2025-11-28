"""
Views for the cards app.

Provides card browsing with search and filtering via HTMX.
"""

from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Card, CardSet


def card_list(request):
    """
    Main card browser view with filtering and search.

    Supports HTMX partial updates for live search.
    """
    cards = Card.objects.filter(deck_buildable=True).select_related('card_set')

    # Search by name, card text, or type
    search = request.GET.get('search', '').strip()
    if search:
        cards = cards.filter(
            Q(name__icontains=search) |
            Q(card_text__icontains=search) |
            Q(card_type__icontains=search)
        )

    # Filter by card type
    card_type = request.GET.get('type', '')
    if card_type:
        cards = cards.filter(card_type=card_type)

    # Filter by faction/influence
    faction = request.GET.get('faction', '')
    if faction:
        cards = cards.filter(influence__contains=faction)

    # Filter by cost
    cost = request.GET.get('cost', '')
    if cost:
        if cost == '7+':
            cards = cards.filter(cost__gte=7)
        else:
            cards = cards.filter(cost=int(cost))

    # Filter by rarity
    rarity = request.GET.get('rarity', '')
    if rarity:
        cards = cards.filter(rarity=rarity)

    # Filter by set
    set_number = request.GET.get('set', '')
    if set_number:
        cards = cards.filter(card_set__number=set_number)

    # Sorting
    sort = request.GET.get('sort', 'name')
    if sort == 'cost':
        cards = cards.order_by('cost', 'name')
    elif sort == 'type':
        cards = cards.order_by('card_type', 'name')
    elif sort == 'set':
        cards = cards.order_by('card_set', 'eternal_id')
    else:
        cards = cards.order_by('name')

    # Pagination
    paginator = Paginator(cards, 50)  # 50 cards per page
    page = request.GET.get('page', 1)
    cards_page = paginator.get_page(page)

    # Get filter options for dropdowns
    card_types = Card.objects.values_list('card_type', flat=True).distinct().order_by('card_type')
    rarities = Card.objects.values_list('rarity', flat=True).distinct().order_by('rarity')
    sets = CardSet.objects.all().order_by('number')

    context = {
        'cards': cards_page,
        'search': search,
        'card_type': card_type,
        'faction': faction,
        'cost': cost,
        'rarity': rarity,
        'set_number': set_number,
        'sort': sort,
        'card_types': card_types,
        'rarities': rarities,
        'sets': sets,
        'total_count': paginator.count,
    }

    # If HTMX request, return partial template
    if request.htmx:
        return render(request, 'cards/partials/card_grid.html', context)

    return render(request, 'cards/card_list.html', context)


def card_detail(request, pk):
    """
    Detailed view of a single card.
    """
    card = get_object_or_404(Card, pk=pk)

    # Check if user owns this card
    from collection.models import CollectionEntry
    try:
        collection_entry = CollectionEntry.objects.get(card=card)
        owned_count = collection_entry.total_quantity
    except CollectionEntry.DoesNotExist:
        owned_count = 0

    # Check if coming from a deck
    from decks.models import Deck
    from_deck_id = request.GET.get('from_deck')
    from_deck = None
    if from_deck_id:
        try:
            from_deck = Deck.objects.get(pk=from_deck_id)
        except Deck.DoesNotExist:
            pass

    # Get all decks containing this card
    decks_with_card = Deck.objects.filter(cards__card=card).distinct()

    context = {
        'card': card,
        'owned_count': owned_count,
        'from_deck': from_deck,
        'decks_with_card': decks_with_card,
    }

    # If HTMX request, return card popup partial
    if request.htmx:
        return render(request, 'cards/partials/card_popup.html', context)

    return render(request, 'cards/card_detail.html', context)
