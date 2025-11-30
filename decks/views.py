"""
Views for the decks app.

Provides deck listing, creation, editing, and export functionality.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from cards.models import Card
from .models import Deck, DeckCard, DeckVersion, DeckVersionCard
from .image_generator import generate_deck_image
from .power_calculator import DeckPowerAnalyzer
from .draw_simulator import DrawSimulator
from .deck_analysis import DeckAnalyzer


def deck_list(request):
    """
    List all decks with summary info.
    """
    from django.db.models import Q

    decks = Deck.objects.all().prefetch_related('cards__card')

    # Search by deck name or card name
    search = request.GET.get('search', '').strip()
    if search:
        # Find decks matching name OR containing a card with that name
        decks = decks.filter(
            Q(name__icontains=search) |
            Q(cards__card__name__icontains=search)
        ).distinct()

    context = {
        'decks': decks,
        'search': search,
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


def deck_image(request, pk):
    """
    Generate and return a PNG image of the deck.
    """
    deck = get_object_or_404(Deck.objects.prefetch_related('cards__card'), pk=pk)

    # Generate the image
    image_data = generate_deck_image(deck)

    response = HttpResponse(image_data.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="{deck.name}_deck.png"'
    return response


def deck_collection_check(request, pk):
    """
    Compare deck cards against user's collection to show missing cards.
    """
    from collection.models import CollectionEntry

    deck = get_object_or_404(Deck.objects.prefetch_related('cards__card'), pk=pk)

    # Get all deck cards
    deck_cards = list(deck.cards.select_related('card', 'card__card_set'))

    # Build collection lookup
    collection = {}
    for entry in CollectionEntry.objects.select_related('card'):
        collection[entry.card_id] = entry.total_quantity

    # Analyze each card
    card_status = []
    total_missing = 0
    total_needed = 0

    for dc in deck_cards:
        owned = collection.get(dc.card_id, 0)
        needed = dc.quantity
        missing = max(0, needed - owned)
        total_needed += needed
        total_missing += missing

        card_status.append({
            'card': dc.card,
            'needed': needed,
            'owned': owned,
            'missing': missing,
            'is_market': dc.is_market,
            'complete': missing == 0,
        })

    # Sort: missing cards first, then by name
    card_status.sort(key=lambda x: (-x['missing'], x['card'].name))

    # Summary stats
    complete_cards = sum(1 for c in card_status if c['complete'])
    missing_cards = [c for c in card_status if not c['complete']]

    context = {
        'deck': deck,
        'card_status': card_status,
        'missing_cards': missing_cards,
        'total_needed': total_needed,
        'total_missing': total_missing,
        'complete_cards': complete_cards,
        'total_card_types': len(card_status),
        'deck_complete': total_missing == 0,
    }
    return render(request, 'decks/deck_collection_check.html', context)


def deck_versions(request, pk):
    """
    List all versions of a deck.
    """
    deck = get_object_or_404(Deck, pk=pk)
    versions = deck.versions.all()

    context = {
        'deck': deck,
        'versions': versions,
    }
    return render(request, 'decks/deck_versions.html', context)


@require_POST
def deck_create_version(request, pk):
    """
    Create a snapshot of the current deck state.
    """
    deck = get_object_or_404(Deck, pk=pk)
    notes = request.POST.get('notes', '').strip()

    version = deck.create_version_snapshot(notes=notes)
    messages.success(request, f'Version {version.version_number} created!')

    return redirect('decks:deck_detail', pk=deck.pk)


@require_POST
def deck_restore_version(request, pk, version_number):
    """
    Restore a deck to a previous version.
    """
    deck = get_object_or_404(Deck, pk=pk)

    try:
        version = deck.restore_version(version_number)
        messages.success(request, f'Deck restored to version {version.version_number}!')
    except DeckVersion.DoesNotExist:
        messages.error(request, 'Version not found.')

    return redirect('decks:deck_detail', pk=deck.pk)


def deck_power_calculator(request, pk):
    """
    Power calculator view - analyze deck's power base and influence odds.
    """
    deck = get_object_or_404(Deck.objects.prefetch_related('cards__card'), pk=pk)

    # Initialize the power analyzer
    analyzer = DeckPowerAnalyzer(deck)

    # Get power source breakdown
    power_sources = analyzer.get_power_sources_by_category()
    influence_sources = analyzer.get_influence_sources()

    # Filter to only factions with sources
    active_factions = {
        k: v for k, v in influence_sources.items() if v > 0
    }

    # Generate odds tables
    power_table = []
    for turn in range(1, 11):
        row = {
            'turn': turn,
            'cards_seen': 6 + turn,
        }
        for power in range(1, 8):
            odds = analyzer.calculate_power_odds(power, turn)
            row[f'power_{power}'] = round(odds * 100, 1)
        power_table.append(row)

    # Generate influence tables for each active faction
    influence_tables = {}
    faction_names = {'F': 'Fire', 'T': 'Time', 'J': 'Justice', 'P': 'Primal', 'S': 'Shadow'}

    for faction, count in active_factions.items():
        table = []
        for turn in range(1, 11):
            row = {'turn': turn}
            for inf in range(1, 5):
                odds = analyzer.calculate_influence_odds(faction, inf, turn)
                row[f'inf_{inf}'] = round(odds * 100, 1)
            table.append(row)
        influence_tables[faction] = {
            'name': faction_names.get(faction, faction),
            'sources': count,
            'table': table,
        }

    # Analyze key cards
    key_cards = analyzer.get_key_cards_analysis()

    context = {
        'deck': deck,
        'analyzer': analyzer,
        'power_sources': power_sources,
        'influence_sources': active_factions,
        'faction_names': faction_names,
        'total_power': analyzer.get_total_power_count(),
        'total_cards': analyzer.total_cards,
        'undepleted_count': analyzer.get_undepleted_count(),
        'depleted_count': analyzer.get_depleted_count(),
        'conditional_count': analyzer.get_conditional_count(),
        'colorless_count': analyzer.get_colorless_count(),
        'power_table': power_table,
        'influence_tables': influence_tables,
        'key_cards': key_cards,
    }
    return render(request, 'decks/deck_power_calculator.html', context)


def deck_draw_simulator(request, pk):
    """
    Draw simulator view - test opening hands with mulligan mechanics.
    """
    deck = get_object_or_404(Deck.objects.prefetch_related('cards__card'), pk=pk)

    # Check for existing simulator in session
    session_key = f'draw_sim_{pk}'

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'new_game':
            # Start fresh
            simulator = DrawSimulator.from_deck(deck)
            request.session[session_key] = simulator.to_dict()

        elif action == 'mulligan':
            # Take a mulligan
            sim_data = request.session.get(session_key)
            if sim_data:
                simulator = DrawSimulator.from_dict(sim_data)
                simulator.mulligan()
                request.session[session_key] = simulator.to_dict()
            else:
                simulator = DrawSimulator.from_deck(deck)
                request.session[session_key] = simulator.to_dict()

        elif action == 'draw':
            # Draw a card
            sim_data = request.session.get(session_key)
            if sim_data:
                simulator = DrawSimulator.from_dict(sim_data)
                simulator.draw_card()
                request.session[session_key] = simulator.to_dict()
            else:
                simulator = DrawSimulator.from_deck(deck)
                request.session[session_key] = simulator.to_dict()
        else:
            # Unknown action, start fresh
            simulator = DrawSimulator.from_deck(deck)
            request.session[session_key] = simulator.to_dict()
    else:
        # GET request - check for existing or start new
        sim_data = request.session.get(session_key)
        if sim_data:
            simulator = DrawSimulator.from_dict(sim_data)
        else:
            simulator = DrawSimulator.from_deck(deck)
            request.session[session_key] = simulator.to_dict()

    # Get hand stats
    hand_stats = simulator.get_hand_stats()

    context = {
        'deck': deck,
        'hand': simulator.current_hand,
        'hand_stats': hand_stats,
        'mulligan_count': simulator.mulligan_count,
        'can_mulligan': simulator.mulligan_count < simulator.max_mulligans,
        'deck_remaining': len(simulator.remaining_deck),
    }
    return render(request, 'decks/deck_draw_simulator.html', context)


def deck_analysis(request, pk):
    """
    Comprehensive deck analysis view - curve, types, influence requirements, synergies.
    """
    deck = get_object_or_404(Deck.objects.prefetch_related('cards__card'), pk=pk)

    # Run analysis
    analyzer = DeckAnalyzer(deck)
    curve = analyzer.analyze_curve()
    types = analyzer.analyze_type_distribution()
    influence = analyzer.analyze_influence_requirements()
    synergies = analyzer.analyze_synergies()

    # Prepare curve data for chart (costs 0-10+)
    curve_chart_data = []
    for cost in range(11):
        curve_chart_data.append(curve.non_power_by_cost.get(cost, 0))
    # Add 10+ bucket
    high_cost = sum(v for k, v in curve.non_power_by_cost.items() if k > 10)
    if high_cost:
        curve_chart_data.append(high_cost)

    context = {
        'deck': deck,
        'curve': curve,
        'types': types,
        'influence': influence,
        'synergies': synergies,
        'curve_chart_data': curve_chart_data,
        'total_cards': len(analyzer.cards),
        'power_count': len(analyzer.power_cards),
        'non_power_count': len(analyzer.non_power_cards),
        'faction_names': DeckAnalyzer.FACTIONS,
    }
    return render(request, 'decks/deck_analysis.html', context)
