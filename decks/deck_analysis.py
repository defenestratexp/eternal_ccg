"""
Deck Analysis tools for Eternal Card Game decks.

Provides various analysis features:
- Mana curve analysis
- Card type distribution
- Influence requirements analysis
- Synergy detection
"""

from collections import defaultdict
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class CurveData:
    """Mana curve analysis results."""
    # Cards at each cost: {0: 4, 1: 8, 2: 12, ...}
    by_cost: Dict[int, int]
    # Cards at each cost excluding power
    non_power_by_cost: Dict[int, int]
    # Average cost (non-power cards only)
    average_cost: float
    # Curve peak (most common cost)
    peak_cost: int
    # Cards by cost with details
    cards_at_cost: Dict[int, List[dict]]


@dataclass
class TypeDistribution:
    """Card type distribution results."""
    # Count by type: {'Unit': 24, 'Spell': 8, ...}
    by_type: Dict[str, int]
    # Percentage by type
    percentages: Dict[str, float]
    # Cards grouped by type with details
    cards_by_type: Dict[str, List[dict]]
    # Total non-power cards
    total_non_power: int
    # Total power cards
    total_power: int


@dataclass
class InfluenceAnalysis:
    """Influence requirements analysis."""
    # Most demanding cards (sorted by difficulty)
    hardest_cards: List[dict]
    # Influence requirements summary per faction
    faction_demands: Dict[str, dict]
    # Cards that may be hard to cast on curve
    potential_bottlenecks: List[dict]
    # Total influence pips required across all cards
    total_pips: Dict[str, int]


class DeckAnalyzer:
    """
    Comprehensive deck analysis tool.
    """

    FACTIONS = {'F': 'Fire', 'T': 'Time', 'J': 'Justice', 'P': 'Primal', 'S': 'Shadow'}

    def __init__(self, deck):
        """
        Initialize analyzer with a Deck model instance.

        Args:
            deck: A Deck model instance
        """
        self.deck = deck
        self.cards = []
        self.power_cards = []
        self.non_power_cards = []
        self._load_cards()

    def _load_cards(self):
        """Load and categorize all cards from the deck."""
        for deck_card in self.deck.cards.select_related('card').all():
            if deck_card.is_market:
                continue  # Skip market cards for main deck analysis

            card = deck_card.card
            card_info = {
                'id': card.id,
                'name': card.name,
                'cost': card.cost,
                'card_type': card.card_type,
                'influence': card.influence,
                'attack': card.attack,
                'health': card.health,
                'card_text': card.card_text,
                'unit_types': card.unit_types,
                'image_url': card.image_url,
                'quantity': deck_card.quantity,
                'is_power': card.card_type in ['Power', 'Sigil'],
            }

            for _ in range(deck_card.quantity):
                self.cards.append(card_info)
                if card_info['is_power']:
                    self.power_cards.append(card_info)
                else:
                    self.non_power_cards.append(card_info)

    def _parse_influence(self, influence_str: str) -> Dict[str, int]:
        """Parse influence string into faction counts."""
        result = {}
        for char in influence_str:
            if char in self.FACTIONS:
                result[char] = result.get(char, 0) + 1
        return result

    def analyze_curve(self) -> CurveData:
        """
        Analyze the mana curve of the deck.

        Returns:
            CurveData with curve statistics
        """
        by_cost = defaultdict(int)
        non_power_by_cost = defaultdict(int)
        cards_at_cost = defaultdict(list)

        total_cost = 0
        non_power_count = 0

        # Count unique cards (not copies)
        seen_at_cost = defaultdict(set)

        for card in self.cards:
            cost = card['cost']
            by_cost[cost] += 1

            if not card['is_power']:
                non_power_by_cost[cost] += 1
                total_cost += cost
                non_power_count += 1

            # Add to cards_at_cost if not already there
            if card['name'] not in seen_at_cost[cost]:
                seen_at_cost[cost].add(card['name'])
                cards_at_cost[cost].append(card)

        # Calculate average cost
        average_cost = total_cost / non_power_count if non_power_count > 0 else 0

        # Find peak
        peak_cost = 0
        peak_count = 0
        for cost, count in non_power_by_cost.items():
            if count > peak_count:
                peak_count = count
                peak_cost = cost

        return CurveData(
            by_cost=dict(by_cost),
            non_power_by_cost=dict(non_power_by_cost),
            average_cost=round(average_cost, 2),
            peak_cost=peak_cost,
            cards_at_cost=dict(cards_at_cost),
        )

    def analyze_type_distribution(self) -> TypeDistribution:
        """
        Analyze card type distribution.

        Returns:
            TypeDistribution with type statistics
        """
        by_type = defaultdict(int)
        cards_by_type = defaultdict(list)
        seen_by_type = defaultdict(set)

        total_power = 0
        total_non_power = 0

        for card in self.cards:
            card_type = card['card_type']
            by_type[card_type] += 1

            if card['is_power']:
                total_power += 1
            else:
                total_non_power += 1

            if card['name'] not in seen_by_type[card_type]:
                seen_by_type[card_type].add(card['name'])
                cards_by_type[card_type].append(card)

        # Calculate percentages (of non-power cards)
        percentages = {}
        for card_type, count in by_type.items():
            if card_type not in ['Power', 'Sigil']:
                percentages[card_type] = round(count / total_non_power * 100, 1) if total_non_power > 0 else 0

        return TypeDistribution(
            by_type=dict(by_type),
            percentages=percentages,
            cards_by_type=dict(cards_by_type),
            total_non_power=total_non_power,
            total_power=total_power,
        )

    def analyze_influence_requirements(self, power_sources: Dict[str, int] = None) -> InfluenceAnalysis:
        """
        Analyze influence requirements and identify potential issues.

        Args:
            power_sources: Optional dict of faction -> source count from power calculator

        Returns:
            InfluenceAnalysis with requirement statistics
        """
        # Track influence demands
        faction_demands = {f: {'cards': 0, 'max_pips': 0, 'total_pips': 0} for f in self.FACTIONS}
        total_pips = {f: 0 for f in self.FACTIONS}

        card_difficulties = []

        for card in self.non_power_cards:
            influence = self._parse_influence(card['influence'])
            if not influence:
                continue

            # Calculate difficulty score
            # Higher cost + more pips + more factions = harder to cast
            total_influence_pips = sum(influence.values())
            num_factions = len(influence)
            difficulty = card['cost'] + (total_influence_pips * 2) + (num_factions * 3)

            card_difficulties.append({
                'name': card['name'],
                'cost': card['cost'],
                'influence': influence,
                'influence_str': card['influence'],
                'difficulty': difficulty,
                'card_type': card['card_type'],
                'quantity': card['quantity'],
            })

            # Update faction demands
            for faction, pips in influence.items():
                faction_demands[faction]['cards'] += 1
                faction_demands[faction]['max_pips'] = max(faction_demands[faction]['max_pips'], pips)
                faction_demands[faction]['total_pips'] += pips
                total_pips[faction] += pips

        # Sort by difficulty (hardest first)
        card_difficulties.sort(key=lambda x: x['difficulty'], reverse=True)
        hardest_cards = card_difficulties[:10]  # Top 10 hardest

        # Identify potential bottlenecks
        # Cards where influence requirement >= cost (hard to cast on curve)
        potential_bottlenecks = []
        for card in card_difficulties:
            influence = card['influence']
            max_single_faction = max(influence.values()) if influence else 0
            # If you need 3+ of one faction, or need more pips than your cost
            if max_single_faction >= 3 or sum(influence.values()) > card['cost']:
                potential_bottlenecks.append(card)

        # Filter faction_demands to only factions with cards
        faction_demands = {f: d for f, d in faction_demands.items() if d['cards'] > 0}
        total_pips = {f: p for f, p in total_pips.items() if p > 0}

        return InfluenceAnalysis(
            hardest_cards=hardest_cards,
            faction_demands=faction_demands,
            potential_bottlenecks=potential_bottlenecks[:10],
            total_pips=total_pips,
        )

    def get_full_analysis(self) -> dict:
        """
        Run all analyses and return combined results.

        Returns:
            Dict with all analysis results
        """
        return {
            'curve': self.analyze_curve(),
            'types': self.analyze_type_distribution(),
            'influence': self.analyze_influence_requirements(),
            'total_cards': len(self.cards),
            'power_count': len(self.power_cards),
            'non_power_count': len(self.non_power_cards),
        }
