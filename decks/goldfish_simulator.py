"""
Goldfish Simulator for Eternal Card Game decks.

Simulates playing out turns against an imaginary opponent (goldfishing).
Tracks power development, playable cards, and deck progression.

ARCHITECTURE OVERVIEW
=====================
"Goldfishing" is a card game term meaning to play your deck against an imaginary
opponent who does nothing (like playing against a goldfish). This lets you test
how your deck develops over multiple turns without opponent interaction.

What This Simulates:
- Drawing opening hand (7 cards)
- Turn-by-turn progression: untap power, draw card, play cards
- Power development and influence accumulation
- Playing units to battlefield, casting spells
- Tracking total attack power on board

What This Does NOT Simulate:
- Opponent actions (blocking, removal, etc.)
- Combat damage (just tracks potential damage)
- Card abilities (spells have no effect)
- Market/Smuggler access

Two Modes:
1. INTERACTIVE - User advances turns manually, can choose which cards to play
2. AUTO-PLAY - AI plays turns automatically using simple heuristics:
   - Always play power if available
   - Play highest-cost unit that's affordable
   - Then play spells with remaining power

Game State Tracking:
- Hand, Deck, Battlefield, Void (graveyard)
- Power available vs max power
- Influence per faction
- Total damage potential (sum of unit attack values)
- Cards played, spells cast

USAGE
=====
    sim = GoldfishSimulator.from_deck(deck)
    sim.start_turn()  # Begin turn 1

    # Manual play
    playable = sim.get_playable_cards()
    result = sim.play_card(playable[0])

    # Or auto-play
    actions = sim.auto_play_turn()

    # Simulate multiple turns
    summaries = sim.simulate_turns(10)

SESSION PERSISTENCE
==================
State serialized via to_dict()/from_dict() for Django sessions.
Allows user to step through turns across page refreshes.

DESIGN DECISIONS
================
1. Player is "on the play" (no draw turn 1)
2. Power cards go to void after playing (simplified - real game has power "in play")
3. No summoning sickness tracked (goldfish doesn't interact anyway)
4. Auto-play prioritizes biggest threats (highest cost units first)
5. Units track attack/health but no damage is actually dealt
"""

import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class GoldfishCard:
    """Represents a card in the goldfish simulation."""
    id: int
    name: str
    card_type: str
    cost: int
    influence: str
    attack: int
    health: int
    image_url: str
    is_power: bool

    def __hash__(self):
        return hash((self.id, id(self)))


@dataclass
class GoldfishState:
    """
    Represents the game state during goldfish simulation.
    """
    # Cards
    hand: List[GoldfishCard] = field(default_factory=list)
    deck: List[GoldfishCard] = field(default_factory=list)
    battlefield: List[GoldfishCard] = field(default_factory=list)
    void: List[GoldfishCard] = field(default_factory=list)

    # Resources
    power_available: int = 0
    power_max: int = 0
    influence: Dict[str, int] = field(default_factory=dict)

    # Game state
    turn: int = 0
    power_played_this_turn: bool = False

    # Stats tracking
    total_damage_potential: int = 0
    cards_played_total: int = 0
    spells_cast: int = 0


class GoldfishSimulator:
    """
    Simulates playing out turns with a deck (goldfishing).
    """

    FACTIONS = {'F': 'Fire', 'T': 'Time', 'J': 'Justice', 'P': 'Primal', 'S': 'Shadow'}

    def __init__(self, deck_cards: List[GoldfishCard]):
        """
        Initialize simulator with deck cards.

        Args:
            deck_cards: List of GoldfishCard objects
        """
        self.original_deck = deck_cards.copy()
        self.state = GoldfishState()
        self._setup_game()

    @classmethod
    def from_deck(cls, deck) -> 'GoldfishSimulator':
        """
        Create a simulator from a Deck model instance.

        Args:
            deck: A Deck model instance

        Returns:
            GoldfishSimulator instance
        """
        deck_cards = []

        for deck_card in deck.cards.select_related('card').all():
            card = deck_card.card

            # Skip market cards
            if deck_card.is_market:
                continue

            is_power = card.card_type in ['Power', 'Sigil']

            for _ in range(deck_card.quantity):
                gc = GoldfishCard(
                    id=card.id,
                    name=card.name,
                    card_type=card.card_type,
                    cost=card.cost,
                    influence=card.influence or '',
                    attack=card.attack or 0,
                    health=card.health or 0,
                    image_url=card.image_url,
                    is_power=is_power,
                )
                deck_cards.append(gc)

        return cls(deck_cards)

    def _setup_game(self):
        """Initialize game state with shuffled deck and opening hand."""
        self.state = GoldfishState()
        self.state.deck = self.original_deck.copy()
        random.shuffle(self.state.deck)
        self.state.influence = {f: 0 for f in self.FACTIONS}

        # Draw opening hand (7 cards)
        for _ in range(7):
            if self.state.deck:
                self.state.hand.append(self.state.deck.pop(0))

    def reset(self):
        """Reset the simulation to start a new game."""
        self._setup_game()

    def start_turn(self) -> dict:
        """
        Start a new turn.

        Returns:
            Dict with turn information
        """
        self.state.turn += 1
        self.state.power_played_this_turn = False

        # Refresh power
        self.state.power_available = self.state.power_max

        # Draw a card (except turn 1 on the play)
        drawn_card = None
        if self.state.turn > 1 and self.state.deck:
            drawn_card = self.state.deck.pop(0)
            self.state.hand.append(drawn_card)

        return {
            'turn': self.state.turn,
            'drawn_card': drawn_card,
            'hand_size': len(self.state.hand),
            'power_available': self.state.power_available,
        }

    def get_playable_cards(self) -> List[GoldfishCard]:
        """
        Get list of cards that can be played this turn.

        Returns:
            List of playable cards from hand
        """
        playable = []
        for card in self.state.hand:
            if self._can_play(card):
                playable.append(card)
        return playable

    def _can_play(self, card: GoldfishCard) -> bool:
        """Check if a card can be played."""
        # Power cards - can play one per turn
        if card.is_power:
            return not self.state.power_played_this_turn

        # Non-power cards - check cost and influence
        if card.cost > self.state.power_available:
            return False

        # Check influence requirements
        required = self._parse_influence(card.influence)
        for faction, count in required.items():
            if self.state.influence.get(faction, 0) < count:
                return False

        return True

    def _parse_influence(self, influence_str: str) -> Dict[str, int]:
        """Parse influence string into faction counts."""
        result = {}
        for char in influence_str:
            if char in self.FACTIONS:
                result[char] = result.get(char, 0) + 1
        return result

    def play_card(self, card: GoldfishCard) -> dict:
        """
        Play a card from hand.

        Args:
            card: The card to play

        Returns:
            Dict with result information
        """
        if card not in self.state.hand:
            return {'success': False, 'error': 'Card not in hand'}

        if not self._can_play(card):
            return {'success': False, 'error': 'Cannot play this card'}

        # Remove from hand
        self.state.hand.remove(card)
        self.state.cards_played_total += 1

        if card.is_power:
            # Power card - increase resources
            self.state.power_played_this_turn = True
            self.state.power_max += 1
            self.state.power_available += 1

            # Add influence
            for char in card.influence:
                if char in self.FACTIONS:
                    self.state.influence[char] = self.state.influence.get(char, 0) + 1

            # Power goes to void (for simplicity)
            self.state.void.append(card)

            return {
                'success': True,
                'action': 'played_power',
                'card': card,
                'power_max': self.state.power_max,
                'influence': dict(self.state.influence),
            }
        else:
            # Non-power card - spend power
            self.state.power_available -= card.cost

            if card.card_type == 'Unit':
                # Units go to battlefield
                self.state.battlefield.append(card)
                self.state.total_damage_potential += card.attack

                return {
                    'success': True,
                    'action': 'played_unit',
                    'card': card,
                    'attack': card.attack,
                    'total_damage': self.state.total_damage_potential,
                }
            else:
                # Spells go to void
                self.state.void.append(card)
                self.state.spells_cast += 1

                return {
                    'success': True,
                    'action': 'cast_spell',
                    'card': card,
                }

    def auto_play_turn(self) -> List[dict]:
        """
        Automatically play the turn with simple heuristics.

        Priority:
        1. Play power if available
        2. Play highest cost unit we can afford
        3. Play spells

        Returns:
            List of actions taken
        """
        actions = []

        # Play power first
        power_cards = [c for c in self.state.hand if c.is_power]
        if power_cards and not self.state.power_played_this_turn:
            # Prefer power that provides needed influence
            power_to_play = power_cards[0]
            result = self.play_card(power_to_play)
            if result['success']:
                actions.append(result)

        # Play units (highest cost first)
        while True:
            playable_units = [
                c for c in self.get_playable_cards()
                if c.card_type == 'Unit'
            ]
            if not playable_units:
                break

            # Play highest cost unit
            playable_units.sort(key=lambda c: c.cost, reverse=True)
            result = self.play_card(playable_units[0])
            if result['success']:
                actions.append(result)
            else:
                break

        # Play spells if we have power left
        while True:
            playable_spells = [
                c for c in self.get_playable_cards()
                if c.card_type not in ['Unit', 'Power', 'Sigil']
            ]
            if not playable_spells:
                break

            # Play highest cost spell
            playable_spells.sort(key=lambda c: c.cost, reverse=True)
            result = self.play_card(playable_spells[0])
            if result['success']:
                actions.append(result)
            else:
                break

        return actions

    def get_state_summary(self) -> dict:
        """
        Get a summary of the current game state.

        Returns:
            Dict with state information
        """
        return {
            'turn': self.state.turn,
            'hand': self.state.hand,
            'hand_size': len(self.state.hand),
            'battlefield': self.state.battlefield,
            'battlefield_size': len(self.state.battlefield),
            'deck_size': len(self.state.deck),
            'void_size': len(self.state.void),
            'power_available': self.state.power_available,
            'power_max': self.state.power_max,
            'influence': {k: v for k, v in self.state.influence.items() if v > 0},
            'total_damage_potential': self.state.total_damage_potential,
            'cards_played_total': self.state.cards_played_total,
            'spells_cast': self.state.spells_cast,
        }

    def simulate_turns(self, num_turns: int = 10) -> List[dict]:
        """
        Simulate multiple turns automatically.

        Args:
            num_turns: Number of turns to simulate

        Returns:
            List of turn summaries
        """
        turn_summaries = []

        for _ in range(num_turns):
            # Start turn
            turn_info = self.start_turn()

            # Auto-play the turn
            actions = self.auto_play_turn()

            # Get state after turn
            state = self.get_state_summary()

            turn_summaries.append({
                'turn': state['turn'],
                'drawn': turn_info.get('drawn_card'),
                'actions': actions,
                'power_max': state['power_max'],
                'influence': state['influence'],
                'battlefield_count': state['battlefield_size'],
                'damage_potential': state['total_damage_potential'],
                'hand_size': state['hand_size'],
            })

        return turn_summaries

    def to_dict(self) -> dict:
        """Serialize state for session storage."""
        def card_to_dict(c):
            return {
                'id': c.id,
                'name': c.name,
                'card_type': c.card_type,
                'cost': c.cost,
                'influence': c.influence,
                'attack': c.attack,
                'health': c.health,
                'image_url': c.image_url,
                'is_power': c.is_power,
            }

        return {
            'original_deck': [card_to_dict(c) for c in self.original_deck],
            'hand': [card_to_dict(c) for c in self.state.hand],
            'deck': [card_to_dict(c) for c in self.state.deck],
            'battlefield': [card_to_dict(c) for c in self.state.battlefield],
            'void': [card_to_dict(c) for c in self.state.void],
            'power_available': self.state.power_available,
            'power_max': self.state.power_max,
            'influence': self.state.influence,
            'turn': self.state.turn,
            'power_played_this_turn': self.state.power_played_this_turn,
            'total_damage_potential': self.state.total_damage_potential,
            'cards_played_total': self.state.cards_played_total,
            'spells_cast': self.state.spells_cast,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'GoldfishSimulator':
        """Deserialize from session storage."""
        def dict_to_card(d):
            return GoldfishCard(
                id=d['id'],
                name=d['name'],
                card_type=d['card_type'],
                cost=d['cost'],
                influence=d['influence'],
                attack=d['attack'],
                health=d['health'],
                image_url=d['image_url'],
                is_power=d['is_power'],
            )

        original_deck = [dict_to_card(d) for d in data['original_deck']]
        sim = cls(original_deck)

        sim.state.hand = [dict_to_card(d) for d in data['hand']]
        sim.state.deck = [dict_to_card(d) for d in data['deck']]
        sim.state.battlefield = [dict_to_card(d) for d in data['battlefield']]
        sim.state.void = [dict_to_card(d) for d in data['void']]
        sim.state.power_available = data['power_available']
        sim.state.power_max = data['power_max']
        sim.state.influence = data['influence']
        sim.state.turn = data['turn']
        sim.state.power_played_this_turn = data['power_played_this_turn']
        sim.state.total_damage_potential = data['total_damage_potential']
        sim.state.cards_played_total = data['cards_played_total']
        sim.state.spells_cast = data['spells_cast']

        return sim
