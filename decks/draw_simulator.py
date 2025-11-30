"""
Draw Simulator for Eternal Card Game decks.

Simulates drawing opening hands with the game's mulligan mechanics:
- First hand: 7 cards, random
- First redraw: 7 cards, guaranteed 2-4 power
- Second redraw: 6 cards, guaranteed 2-4 power
- After that, must keep
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
