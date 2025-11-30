"""
Power Calculator for Eternal Card Game decks.

Calculates the probability of drawing enough power and influence
using hypergeometric distribution, similar to ShiftStoned's EPC.
"""

import math
from functools import lru_cache
from typing import Dict, List, Tuple
from dataclasses import dataclass


@lru_cache(maxsize=200)
def factorial(n: int) -> int:
    """Calculate factorial with memoization."""
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def binomial(n: int, k: int) -> float:
    """
    Calculate binomial coefficient (n choose k).

    Returns 0 if k > n.
    """
    if k > n or k < 0:
        return 0
    if k == 0 or k == n:
        return 1
    # Use the more numerically stable calculation for large numbers
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def hypergeometric_probability(
    population_size: int,
    success_in_population: int,
    draws: int,
    observed_successes: int
) -> float:
    """
    Calculate probability using hypergeometric distribution.

    P(X = k) = C(K,k) * C(N-K, n-k) / C(N, n)

    Where:
    - N = population_size (deck size)
    - K = success_in_population (cards that provide what we want)
    - n = draws (cards drawn)
    - k = observed_successes (successes we want to see)
    """
    if observed_successes > success_in_population:
        return 0.0
    if observed_successes > draws:
        return 0.0
    if draws - observed_successes > population_size - success_in_population:
        return 0.0

    numerator = binomial(success_in_population, observed_successes) * \
                binomial(population_size - success_in_population, draws - observed_successes)
    denominator = binomial(population_size, draws)

    if denominator == 0:
        return 0.0

    return numerator / denominator


def probability_at_least(
    population_size: int,
    success_in_population: int,
    draws: int,
    min_successes: int
) -> float:
    """
    Calculate probability of drawing at least min_successes.

    P(X >= k) = sum of P(X = i) for i from k to min(draws, success_in_population)
    """
    if min_successes <= 0:
        return 1.0

    total = 0.0
    max_possible = min(draws, success_in_population)

    for k in range(min_successes, max_possible + 1):
        total += hypergeometric_probability(
            population_size, success_in_population, draws, k
        )

    return total


@dataclass
class PowerSource:
    """Represents a power source in the deck."""
    card_name: str
    card_id: int
    quantity: int
    influence_provided: Dict[str, int]  # {'F': 1, 'T': 1} etc.
    is_depleted: bool
    is_conditional: bool
    power_provided: int = 1  # Most power cards provide 1 power


@dataclass
class InfluenceRequirement:
    """Represents influence needed for a card."""
    card_name: str
    power_cost: int
    influence: Dict[str, int]  # {'F': 2, 'S': 1} etc.


class DeckPowerAnalyzer:
    """
    Analyzes a deck's power base and calculates draw probabilities.
    """

    FACTIONS = {'F': 'Fire', 'T': 'Time', 'J': 'Justice', 'P': 'Primal', 'S': 'Shadow'}

    def __init__(self, deck):
        """
        Initialize analyzer with a Deck instance.

        Args:
            deck: A Deck model instance
        """
        self.deck = deck
        self.power_sources: List[PowerSource] = []
        self.total_cards = 0
        self._analyze_power_sources()

    def _parse_influence(self, influence_str: str) -> Dict[str, int]:
        """Parse influence string like '{F}{F}{S}' into {'F': 2, 'S': 1}."""
        result = {}
        for char in influence_str:
            if char in self.FACTIONS:
                result[char] = result.get(char, 0) + 1
        return result

    def _is_depleted(self, card_text: str) -> bool:
        """Check if card enters play depleted."""
        if not card_text:
            return False
        text = card_text.strip()
        # Cards that say "Depleted;" at start are always depleted
        return text.startswith("Depleted;") or text.startswith("Depleted.")

    def _is_conditional(self, card_text: str) -> bool:
        """Check if card has conditional depleted status."""
        if not card_text:
            return False
        return "Depleted unless" in card_text

    def _analyze_power_sources(self):
        """Analyze all power sources in the deck."""
        self.power_sources = []
        self.total_cards = 0

        for deck_card in self.deck.cards.select_related('card').all():
            card = deck_card.card
            quantity = deck_card.quantity
            self.total_cards += quantity

            # Only analyze power-type cards
            if card.card_type not in ['Power', 'Sigil']:
                continue

            influence_provided = self._parse_influence(card.influence)

            # Skip if no influence provided
            if not influence_provided:
                continue

            power_source = PowerSource(
                card_name=card.name,
                card_id=card.id,
                quantity=quantity,
                influence_provided=influence_provided,
                is_depleted=self._is_depleted(card.card_text),
                is_conditional=self._is_conditional(card.card_text),
            )
            self.power_sources.append(power_source)

    def get_total_power_count(self) -> int:
        """Get total number of power cards in deck."""
        return sum(ps.quantity for ps in self.power_sources)

    def get_undepleted_count(self) -> int:
        """Get count of power sources that enter undepleted."""
        return sum(
            ps.quantity for ps in self.power_sources
            if not ps.is_depleted and not ps.is_conditional
        )

    def get_depleted_count(self) -> int:
        """Get count of power sources that always enter depleted."""
        return sum(
            ps.quantity for ps in self.power_sources
            if ps.is_depleted
        )

    def get_conditional_count(self) -> int:
        """Get count of power sources with conditional depleted."""
        return sum(
            ps.quantity for ps in self.power_sources
            if ps.is_conditional
        )

    def get_influence_sources(self) -> Dict[str, int]:
        """
        Get count of sources for each faction.

        Returns dict like {'F': 12, 'T': 8, 'J': 4}
        """
        sources = {faction: 0 for faction in self.FACTIONS}

        for ps in self.power_sources:
            for faction, count in ps.influence_provided.items():
                # Each copy of the card provides sources
                sources[faction] += ps.quantity

        return sources

    def get_power_sources_by_category(self) -> Dict[str, List[PowerSource]]:
        """
        Categorize power sources.

        Returns dict with keys: 'undepleted', 'depleted', 'conditional'
        """
        categories = {
            'undepleted': [],
            'depleted': [],
            'conditional': [],
        }

        for ps in self.power_sources:
            if ps.is_conditional:
                categories['conditional'].append(ps)
            elif ps.is_depleted:
                categories['depleted'].append(ps)
            else:
                categories['undepleted'].append(ps)

        return categories

    def calculate_power_odds(self, power_needed: int, by_turn: int) -> float:
        """
        Calculate odds of having at least power_needed power by a given turn.

        Args:
            power_needed: Minimum power required
            by_turn: Turn number (cards drawn = 7 + turn - 1 = 6 + turn)

        Returns:
            Probability as float (0.0 to 1.0)
        """
        total_power = self.get_total_power_count()
        # Opening hand is 7, then draw 1 per turn
        cards_drawn = 6 + by_turn

        if cards_drawn > self.total_cards:
            cards_drawn = self.total_cards

        return probability_at_least(
            population_size=self.total_cards,
            success_in_population=total_power,
            draws=cards_drawn,
            min_successes=power_needed
        )

    def calculate_influence_odds(
        self,
        faction: str,
        influence_needed: int,
        by_turn: int
    ) -> float:
        """
        Calculate odds of having enough influence of a specific faction.

        Args:
            faction: Single letter faction code ('F', 'T', 'J', 'P', 'S')
            influence_needed: How many of that faction needed
            by_turn: Turn number

        Returns:
            Probability as float (0.0 to 1.0)
        """
        influence_sources = self.get_influence_sources()
        sources = influence_sources.get(faction, 0)

        cards_drawn = 6 + by_turn
        if cards_drawn > self.total_cards:
            cards_drawn = self.total_cards

        return probability_at_least(
            population_size=self.total_cards,
            success_in_population=sources,
            draws=cards_drawn,
            min_successes=influence_needed
        )

    def calculate_combined_odds(
        self,
        power_needed: int,
        influence_needed: Dict[str, int],
        by_turn: int
    ) -> float:
        """
        Calculate odds of having both power AND all influence requirements.

        This is a simplification that multiplies independent probabilities.
        The actual calculation is more complex due to overlapping sources.

        Args:
            power_needed: Minimum power required
            influence_needed: Dict of faction -> count needed
            by_turn: Turn number

        Returns:
            Probability as float (0.0 to 1.0)
        """
        # Start with power odds
        odds = self.calculate_power_odds(power_needed, by_turn)

        # Multiply by each faction's influence odds
        # Note: This assumes independence which isn't quite right
        # but is a reasonable approximation
        for faction, count in influence_needed.items():
            if count > 0:
                faction_odds = self.calculate_influence_odds(faction, count, by_turn)
                odds *= faction_odds

        return odds

    def generate_power_table(self, max_turns: int = 10) -> List[Dict]:
        """
        Generate a table of power odds by turn.

        Returns list of dicts with turn number and probability.
        """
        table = []
        for turn in range(1, max_turns + 1):
            row = {'turn': turn}
            for power in range(1, min(turn + 1, 8)):  # Reasonable power range
                row[f'power_{power}'] = self.calculate_power_odds(power, turn)
            table.append(row)
        return table

    def generate_influence_table(self, max_turns: int = 10) -> Dict[str, List[Dict]]:
        """
        Generate influence odds tables for each faction in the deck.

        Returns dict of faction -> list of turn/odds data.
        """
        influence_sources = self.get_influence_sources()
        tables = {}

        for faction, source_count in influence_sources.items():
            if source_count == 0:
                continue

            table = []
            for turn in range(1, max_turns + 1):
                row = {'turn': turn}
                for inf in range(1, 5):  # 1-4 influence typically needed
                    row[f'inf_{inf}'] = self.calculate_influence_odds(faction, inf, turn)
                table.append(row)
            tables[faction] = table

        return tables

    def get_key_cards_analysis(self) -> List[Dict]:
        """
        Analyze key expensive cards and their castability.

        Returns list of cards with their influence requirements
        and odds of casting by relevant turns.
        """
        analysis = []

        for deck_card in self.deck.cards.select_related('card').all():
            card = deck_card.card

            # Skip power cards and cheap cards
            if card.card_type in ['Power', 'Sigil'] or card.cost < 3:
                continue

            influence_needed = self._parse_influence(card.influence)
            if not influence_needed:
                continue

            # Calculate odds for the turn you'd want to play it
            target_turn = card.cost
            odds = self.calculate_combined_odds(
                power_needed=card.cost,
                influence_needed=influence_needed,
                by_turn=target_turn
            )

            analysis.append({
                'card': card,
                'quantity': deck_card.quantity,
                'cost': card.cost,
                'influence': influence_needed,
                'target_turn': target_turn,
                'odds_on_curve': odds,
            })

        # Sort by cost
        analysis.sort(key=lambda x: x['cost'])
        return analysis
