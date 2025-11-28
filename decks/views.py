"""
Views for the decks app.

Provides deck listing, creation, editing, and export functionality.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from cards.models import Card
from .models import Deck, DeckCard


def deck_list(request):
    """
    List all decks with summary info.
    """
    decks = Deck.objects.all().prefetch_related('cards__card')

    context = {
        'decks': decks,
    }
    return render(request, 'decks/deck_list.html', context)


def deck_detail(request, pk):
    """
    View a single deck with all cards and validation status.
    """
    deck = get_object_or_404(Deck.objects.prefetch_related('cards__card'), pk=pk)
    validation = deck.validate_deck()

    # Group cards by type for display
    main_cards = deck.main_deck_cards.select_related('card')
    market_cards = deck.market_cards.select_related('card')

    # Group main deck by card type
    cards_by_type = {}
    for dc in main_cards:
        card_type = dc.card.card_type
        if card_type not in cards_by_type:
            cards_by_type[card_type] = []
        cards_by_type[card_type].append(dc)

    context = {
        'deck': deck,
        'validation': validation,
        'cards_by_type': cards_by_type,
        'market_cards': market_cards,
    }
    return render(request, 'decks/deck_detail.html', context)


def deck_create(request):
    """
    Create a new deck.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        format_choice = request.POST.get('format', 'Throne')
        description = request.POST.get('description', '').strip()

        if not name:
            messages.error(request, 'Deck name is required.')
            return redirect('decks:deck_create')

        deck = Deck.objects.create(
            name=name,
            format=format_choice,
            description=description
        )
        messages.success(request, f'Deck "{name}" created!')
        return redirect('decks:deck_edit', pk=deck.pk)

    return render(request, 'decks/deck_create.html')


def deck_edit(request, pk):
    """
    Edit a deck - add/remove cards.
    """
    deck = get_object_or_404(Deck.objects.prefetch_related('cards__card'), pk=pk)

    if request.method == 'POST':
        # Update deck metadata
        deck.name = request.POST.get('name', deck.name).strip()
        deck.format = request.POST.get('format', deck.format)
        deck.description = request.POST.get('description', '').strip()
        deck.save()
        messages.success(request, 'Deck updated!')
        return redirect('decks:deck_detail', pk=deck.pk)

    # Get validation for display
    validation = deck.validate_deck()

    # Get all deck-buildable cards for the card picker
    cards = Card.objects.filter(deck_buildable=True).select_related('card_set').order_by('name')

    context = {
        'deck': deck,
        'validation': validation,
        'cards': cards,
    }
    return render(request, 'decks/deck_edit.html', context)


@require_POST
def deck_add_card(request, pk):
    """
    Add a card to a deck (HTMX endpoint).
    """
    deck = get_object_or_404(Deck, pk=pk)
    card_id = request.POST.get('card_id')
    is_market = request.POST.get('is_market', 'false') == 'true'

    card = get_object_or_404(Card, pk=card_id)

    # Get or create deck card entry
    deck_card, created = DeckCard.objects.get_or_create(
        deck=deck,
        card=card,
        is_market=is_market,
        defaults={'quantity': 1}
    )

    if not created:
        # Increment quantity (respecting limits)
        max_qty = 1 if is_market else (999 if card.is_sigil else 4)
        if deck_card.quantity < max_qty:
            deck_card.quantity += 1
            deck_card.save()

    # Return updated deck summary partial
    validation = deck.validate_deck()
    context = {
        'deck': deck,
        'validation': validation,
    }
    return render(request, 'decks/partials/deck_summary.html', context)


@require_POST
def deck_remove_card(request, pk):
    """
    Remove a card from a deck (HTMX endpoint).
    """
    deck = get_object_or_404(Deck, pk=pk)
    card_id = request.POST.get('card_id')
    is_market = request.POST.get('is_market', 'false') == 'true'

    try:
        deck_card = DeckCard.objects.get(
            deck=deck,
            card_id=card_id,
            is_market=is_market
        )
        deck_card.quantity -= 1
        if deck_card.quantity <= 0:
            deck_card.delete()
        else:
            deck_card.save()
    except DeckCard.DoesNotExist:
        pass

    # Return updated deck summary partial
    validation = deck.validate_deck()
    context = {
        'deck': deck,
        'validation': validation,
    }
    return render(request, 'decks/partials/deck_summary.html', context)


def deck_export(request, pk):
    """
    Export deck in Eternal format (downloadable text file).
    """
    deck = get_object_or_404(Deck, pk=pk)
    content = deck.export_to_eternal_format()

    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{deck.name}_eternaldeck.txt"'
    return response


def deck_export_view(request, pk):
    """
    View the exportable deck text (for copy/paste).
    """
    deck = get_object_or_404(Deck, pk=pk)
    content = deck.export_to_eternal_format()

    context = {
        'deck': deck,
        'export_content': content,
    }
    return render(request, 'decks/deck_export.html', context)


@require_POST
def deck_delete(request, pk):
    """
    Delete a deck.
    """
    deck = get_object_or_404(Deck, pk=pk)
    name = deck.name
    deck.delete()
    messages.success(request, f'Deck "{name}" deleted.')
    return redirect('decks:deck_list')
