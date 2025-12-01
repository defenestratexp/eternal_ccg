"""
Draw Simulator for Eternal Card Game decks.

Simulates drawing opening hands with the game's mulligan mechanics:
- First hand: 7 cards, random
- First redraw: 7 cards, guaranteed 2-4 power
- Second redraw: 6 cards, guaranteed 2-4 power
- After that, must keep

ARCHITECTURE OVERVIEW
=====================
This module simulates the opening hand experience in Eternal. Unlike the power
calculator (which uses math), this uses actual randomization to let users
"feel" their deck's opening hands.

Two Modes of Operation:
1. INTERACTIVE DRAW - User draws hands and decides to keep/mulligan
   - Used in the Draw Sim page
   - State persisted in Django session via to_dict()/from_dict()
   - Shows actual card images from hand

2. MONTE CARLO SIMULATION - Run 1000+ hands to get statistics
   - Used in the Hand Stats page
   - Automated mulligan decisions (mulligan if <2 or >4 power)
   - Tracks: power distribution, mulligan rates, card appearance rates, playability

Eternal's Mulligan System:
- First hand: Completely random 7 cards
- First redraw: 7 cards with GUARANTEED 2-4 power (game forces this)
- Second redraw: Only 6 cards with guaranteed 2-4 power (penalty)
- No more mulligans after that

USAGE
=====
    # Interactive mode
    sim = DrawSimulator.from_deck(deck)
    hand = sim.current_hand  # Initial 7 cards
    new_hand, can_mulligan = sim.mulligan()  # Take a mulligan
    stats = sim.get_hand_stats()  # Analyze current hand

    # Monte Carlo mode
    results = DrawSimulator.run_opening_hand_simulation(deck, num_simulations=1000)
    print(results['keep_rate_pct'])  # How often we keep first hand
    print(results['hands_screw_pct'])  # % of hands with 0-1 power

SESSION PERSISTENCE
==================
The simulator state is serialized to JSON for Django session storage:
- to_dict(): Convert state to JSON-serializable dict
- from_dict(): Reconstruct simulator from stored dict
This allows the user to mulligan across page refreshes.

DESIGN DECISIONS
================
1. Market cards excluded (main deck only, as in actual game)
2. Card identity preserved via object id() for tracking through shuffles
3. Mulligan logic matches game: 2-4 power guaranteed, not 2-3 or 3-4
4. Monte Carlo uses simple heuristic: always mulligan if power outside 2-4 range
5. Statistics include both initial hand and post-mulligan distributions
"""

import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class SimCard:
    """Represents a card in the simulation."""
    id: int
    name: str
    card_type: str
    cost: int
    influence: str
    image_url: str
    is_power: bool

    def __hash__(self):
        return hash(self.id)


@dataclass
class DrawSimulator:
    """
    Simulates drawing hands from a deck with Eternal's mulligan rules.
    """
    deck_cards: List[SimCard] = field(default_factory=list)
    current_hand: List[SimCard] = field(default_factory=list)
    remaining_deck: List[SimCard] = field(default_factory=list)
    mulligan_count: int = 0
    max_mulligans: int = 2

    @classmethod
    def from_deck(cls, deck) -> 'DrawSimulator':
        """
        Create a simulator from a Deck model instance.

        Args:
            deck: A Deck model instance with cards

        Returns:
            DrawSimulator instance
        """
        deck_cards = []

        for deck_card in deck.cards.select_related('card').all():
            card = deck_card.card

            # Skip market cards - only main deck
            if deck_card.is_market:
                continue

            is_power = card.card_type in ['Power', 'Sigil']

            # Add the card quantity times
            for _ in range(deck_card.quantity):
                sim_card = SimCard(
                    id=card.id,
                    name=card.name,
                    card_type=card.card_type,
                    cost=card.cost,
                    influence=card.influence,
                    image_url=card.image_url,
                    is_power=is_power,
                )
                deck_cards.append(sim_card)

        simulator = cls(deck_cards=deck_cards)
        simulator.shuffle_and_draw()
        return simulator

    def shuffle_and_draw(self) -> List[SimCard]:
        """
        Shuffle deck and draw initial 7-card hand.

        Returns:
            The drawn hand
        """
        self.mulligan_count = 0
        self.remaining_deck = self.deck_cards.copy()
        random.shuffle(self.remaining_deck)

        # Draw 7 cards
        self.current_hand = self.remaining_deck[:7]
        self.remaining_deck = self.remaining_deck[7:]

        return self.current_hand

    def mulligan(self) -> Tuple[List[SimCard], bool]:
        """
        Take a mulligan according to Eternal's rules.

        - First mulligan: 7 cards with 2-4 power guaranteed
        - Second mulligan: 6 cards with 2-4 power guaranteed
        - No more mulligans after that

        Returns:
            Tuple of (new hand, can_mulligan_again)
        """
        if self.mulligan_count >= self.max_mulligans:
            # Can't mulligan anymore
            return self.current_hand, False

        self.mulligan_count += 1

        # Determine hand size
        if self.mulligan_count == 1:
            hand_size = 7
        else:
            hand_size = 6

        # Shuffle entire deck back together
        full_deck = self.deck_cards.copy()
        random.shuffle(full_deck)

        # Separate power and non-power cards
        power_cards = [c for c in full_deck if c.is_power]
        non_power_cards = [c for c in full_deck if not c.is_power]

        random.shuffle(power_cards)
        random.shuffle(non_power_cards)

        # Guarantee 2-4 power cards
        # Pick a random number between 2 and 4
        power_count = random.randint(2, min(4, len(power_cards), hand_size - 1))
        non_power_count = hand_size - power_count

        # Make sure we have enough cards
        power_count = min(power_count, len(power_cards))
        non_power_count = min(non_power_count, len(non_power_cards))

        # If we don't have enough non-power, add more power
        if power_count + non_power_count < hand_size:
            additional_power = min(
                hand_size - power_count - non_power_count,
                len(power_cards) - power_count
            )
            power_count += additional_power

        # Draw the hand
        hand_power = power_cards[:power_count]
        hand_non_power = non_power_cards[:non_power_count]

        self.current_hand = hand_power + hand_non_power
        random.shuffle(self.current_hand)

        # Remaining deck is everything not in hand
        hand_set = set(id(c) for c in self.current_hand)
        self.remaining_deck = [c for c in full_deck if id(c) not in hand_set]

        can_mulligan = self.mulligan_count < self.max_mulligans
        return self.current_hand, can_mulligan

    def draw_card(self) -> Optional[SimCard]:
        """
        Draw a single card from the remaining deck.

        Returns:
            The drawn card, or None if deck is empty
        """
        if not self.remaining_deck:
            return None

        card = self.remaining_deck.pop(0)
        self.current_hand.append(card)
        return card

    def get_hand_stats(self) -> dict:
        """
        Get statistics about the current hand.

        Returns:
            Dict with hand analysis
        """
        power_cards = [c for c in self.current_hand if c.is_power]
        non_power_cards = [c for c in self.current_hand if not c.is_power]

        # Count influence
        influence_count = {'F': 0, 'T': 0, 'J': 0, 'P': 0, 'S': 0}
        for card in power_cards:
            for char in card.influence:
                if char in influence_count:
                    influence_count[char] += 1

        # Get playable cards (cards we have influence for)
        # Simplified: just count by cost
        by_cost = {}
        for card in non_power_cards:
            cost = card.cost
            if cost not in by_cost:
                by_cost[cost] = []
            by_cost[cost].append(card)

        return {
            'total_cards': len(self.current_hand),
            'power_count': len(power_cards),
            'non_power_count': len(non_power_cards),
            'power_cards': power_cards,
            'non_power_cards': non_power_cards,
            'influence': {k: v for k, v in influence_count.items() if v > 0},
            'by_cost': by_cost,
            'deck_remaining': len(self.remaining_deck),
            'mulligan_count': self.mulligan_count,
            'can_mulligan': self.mulligan_count < self.max_mulligans,
        }

    def to_dict(self) -> dict:
        """
        Serialize simulator state for session storage.
        """
        return {
            'deck_cards': [
                {
                    'id': c.id,
                    'name': c.name,
                    'card_type': c.card_type,
                    'cost': c.cost,
                    'influence': c.influence,
                    'image_url': c.image_url,
                    'is_power': c.is_power,
                }
                for c in self.deck_cards
            ],
            'current_hand': [
                {
                    'id': c.id,
                    'name': c.name,
                    'card_type': c.card_type,
                    'cost': c.cost,
                    'influence': c.influence,
                    'image_url': c.image_url,
                    'is_power': c.is_power,
                }
                for c in self.current_hand
            ],
            'remaining_deck': [
                {
                    'id': c.id,
                    'name': c.name,
                    'card_type': c.card_type,
                    'cost': c.cost,
                    'influence': c.influence,
                    'image_url': c.image_url,
                    'is_power': c.is_power,
                }
                for c in self.remaining_deck
            ],
            'mulligan_count': self.mulligan_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DrawSimulator':
        """
        Deserialize simulator state from session storage.
        """
        def make_card(d):
            return SimCard(
                id=d['id'],
                name=d['name'],
                card_type=d['card_type'],
                cost=d['cost'],
                influence=d['influence'],
                image_url=d['image_url'],
                is_power=d['is_power'],
            )

        simulator = cls()
        simulator.deck_cards = [make_card(c) for c in data['deck_cards']]
        simulator.current_hand = [make_card(c) for c in data['current_hand']]
        simulator.remaining_deck = [make_card(c) for c in data['remaining_deck']]
        simulator.mulligan_count = data['mulligan_count']
        return simulator

    @classmethod
    def run_opening_hand_simulation(cls, deck, num_simulations: int = 1000) -> dict:
        """
        Run multiple simulations to get statistical data about opening hands.

        Args:
            deck: A Deck model instance
            num_simulations: Number of hands to simulate (default 1000)

        Returns:
            Dict with statistical analysis
        """
        results = {
            'num_simulations': num_simulations,
            # Power distribution in initial hand
            'power_distribution': {i: 0 for i in range(8)},
            # Power distribution after mulligans
            'mulligan_power_dist': {i: 0 for i in range(8)},
            # Average power in opening hand
            'avg_power_initial': 0,
            'avg_power_after_mull': 0,
            # Keep/mulligan decisions
            'keep_rate': 0,
            'mulligan_once': 0,
            'mulligan_twice': 0,
            # Card appearance rates
            'card_appearance': {},
            # Hands with specific power counts
            'hands_with_2_4_power': 0,
            'hands_screw': 0,  # 0-1 power
            'hands_flood': 0,  # 5+ power
            # Curve analysis
            'playable_turn_1': 0,
            'playable_turn_2': 0,
            'playable_turn_3': 0,
            # Influence availability
            'influence_in_hand': {'F': 0, 'T': 0, 'J': 0, 'P': 0, 'S': 0},
        }

        total_power_initial = 0
        total_power_final = 0

        for _ in range(num_simulations):
            sim = cls.from_deck(deck)

            # Check initial hand
            initial_stats = sim.get_hand_stats()
            initial_power = initial_stats['power_count']
            total_power_initial += initial_power
            results['power_distribution'][min(initial_power, 7)] += 1

            # Track card appearances
            for card in sim.current_hand:
                if card.name not in results['card_appearance']:
                    results['card_appearance'][card.name] = 0
                results['card_appearance'][card.name] += 1

            # Decide if we should mulligan (simple heuristic: mulligan if <2 or >4 power)
            mulligans_taken = 0
            if initial_power < 2 or initial_power > 4:
                sim.mulligan()
                mulligans_taken = 1
                stats_after_mull1 = sim.get_hand_stats()

                # Check if we should mulligan again
                if stats_after_mull1['power_count'] < 2 or stats_after_mull1['power_count'] > 4:
                    sim.mulligan()
                    mulligans_taken = 2

            # Get final hand stats
            final_stats = sim.get_hand_stats()
            final_power = final_stats['power_count']
            total_power_final += final_power
            results['mulligan_power_dist'][min(final_power, 7)] += 1

            # Track mulligan decisions
            if mulligans_taken == 0:
                results['keep_rate'] += 1
            elif mulligans_taken == 1:
                results['mulligan_once'] += 1
            else:
                results['mulligan_twice'] += 1

            # Analyze final hand
            if 2 <= final_power <= 4:
                results['hands_with_2_4_power'] += 1
            if final_power <= 1:
                results['hands_screw'] += 1
            if final_power >= 5:
                results['hands_flood'] += 1

            # Check playability by turn
            non_power_costs = [c.cost for c in final_stats['non_power_cards']]
            if any(c <= 1 for c in non_power_costs):
                results['playable_turn_1'] += 1
            if any(c <= 2 for c in non_power_costs):
                results['playable_turn_2'] += 1
            if any(c <= 3 for c in non_power_costs):
                results['playable_turn_3'] += 1

            # Track influence
            for faction, count in final_stats['influence'].items():
                results['influence_in_hand'][faction] += count

        # Calculate averages and percentages
        results['avg_power_initial'] = round(total_power_initial / num_simulations, 2)
        results['avg_power_after_mull'] = round(total_power_final / num_simulations, 2)

        # Convert counts to percentages
        results['keep_rate_pct'] = round(results['keep_rate'] / num_simulations * 100, 1)
        results['mulligan_once_pct'] = round(results['mulligan_once'] / num_simulations * 100, 1)
        results['mulligan_twice_pct'] = round(results['mulligan_twice'] / num_simulations * 100, 1)

        results['hands_with_2_4_power_pct'] = round(results['hands_with_2_4_power'] / num_simulations * 100, 1)
        results['hands_screw_pct'] = round(results['hands_screw'] / num_simulations * 100, 1)
        results['hands_flood_pct'] = round(results['hands_flood'] / num_simulations * 100, 1)

        results['playable_turn_1_pct'] = round(results['playable_turn_1'] / num_simulations * 100, 1)
        results['playable_turn_2_pct'] = round(results['playable_turn_2'] / num_simulations * 100, 1)
        results['playable_turn_3_pct'] = round(results['playable_turn_3'] / num_simulations * 100, 1)

        # Convert power distribution to percentages
        results['power_dist_pct'] = {
            k: round(v / num_simulations * 100, 1)
            for k, v in results['power_distribution'].items()
        }
        results['mull_power_dist_pct'] = {
            k: round(v / num_simulations * 100, 1)
            for k, v in results['mulligan_power_dist'].items()
        }

        # Average influence per hand
        results['avg_influence'] = {
            k: round(v / num_simulations, 2)
            for k, v in results['influence_in_hand'].items()
            if v > 0
        }

        # Top cards by appearance (sorted)
        results['top_cards'] = sorted(
            results['card_appearance'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        # Card appearance as percentage
        results['card_appearance_pct'] = {
            name: round(count / num_simulations * 100, 1)
            for name, count in results['card_appearance'].items()
        }

        return results
