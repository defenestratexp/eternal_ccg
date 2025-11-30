"""
Deck vs Deck Battle Simulator for Eternal Card Game.

Simulates games between two decks using simplified game rules.
Tracks win rates, game length, and key statistics.
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class GamePhase(Enum):
    DRAW = "draw"
    MAIN = "main"
    ATTACK = "attack"
    END = "end"


@dataclass
class BattleCard:
    """Represents a card in battle simulation."""
    id: int
    name: str
    card_type: str
    cost: int
    influence: str
    attack: int
    health: int
    current_health: int = 0
    is_power: bool = False
    can_attack: bool = False  # Summoning sickness
    is_tapped: bool = False

    def __post_init__(self):
        if self.current_health == 0:
            self.current_health = self.health

    def __hash__(self):
        return hash((self.id, id(self)))


@dataclass
class PlayerState:
    """State for one player in the battle."""
    name: str
    health: int = 25
    hand: List[BattleCard] = field(default_factory=list)
    deck: List[BattleCard] = field(default_factory=list)
    battlefield: List[BattleCard] = field(default_factory=list)
    void: List[BattleCard] = field(default_factory=list)
    power_available: int = 0
    power_max: int = 0
    influence: Dict[str, int] = field(default_factory=dict)
    power_played_this_turn: bool = False


@dataclass
class BattleResult:
    """Result of a single battle."""
    winner: str  # 'player1', 'player2', or 'draw'
    turns: int
    player1_final_health: int
    player2_final_health: int
    player1_units_played: int
    player2_units_played: int
    player1_damage_dealt: int
    player2_damage_dealt: int


@dataclass
class SimulationResult:
    """Result of multiple simulated games."""
    games_played: int
    player1_wins: int
    player2_wins: int
    draws: int
    avg_game_length: float
    avg_player1_health: float
    avg_player2_health: float
    player1_win_rate: float
    player2_win_rate: float
    results: List[BattleResult] = field(default_factory=list)


class BattleSimulator:
    """
    Simulates battles between two decks.

    Uses simplified Eternal rules:
    - Draw 7 cards, mulligan to 6 (redraw if <=2 power or >=5 power)
    - Play one power per turn, draw one card per turn
    - Units have summoning sickness
    - Combat: attackers vs blockers, excess damage to face
    - Win at 0 health or deck empty
    """

    FACTIONS = {'F': 'Fire', 'T': 'Time', 'J': 'Justice', 'P': 'Primal', 'S': 'Shadow'}
    MAX_TURNS = 30

    def __init__(self, deck1_cards: List[BattleCard], deck2_cards: List[BattleCard],
                 deck1_name: str = "Deck 1", deck2_name: str = "Deck 2"):
        self.deck1_cards = deck1_cards
        self.deck2_cards = deck2_cards
        self.deck1_name = deck1_name
        self.deck2_name = deck2_name

    @classmethod
    def from_decks(cls, deck1, deck2) -> 'BattleSimulator':
        """Create simulator from two Deck model instances."""
        def deck_to_cards(deck) -> List[BattleCard]:
            cards = []
            for deck_card in deck.cards.select_related('card').all():
                card = deck_card.card
                if deck_card.is_market:
                    continue

                is_power = card.card_type in ['Power', 'Sigil']
                for _ in range(deck_card.quantity):
                    bc = BattleCard(
                        id=card.id,
                        name=card.name,
                        card_type=card.card_type,
                        cost=card.cost,
                        influence=card.influence or '',
                        attack=card.attack or 0,
                        health=card.health or 0,
                        is_power=is_power,
                    )
                    cards.append(bc)
            return cards

        return cls(
            deck_to_cards(deck1),
            deck_to_cards(deck2),
            deck1.name,
            deck2.name
        )

    def _create_player(self, cards: List[BattleCard], name: str) -> PlayerState:
        """Create a player state with shuffled deck."""
        deck = [
            BattleCard(
                id=c.id, name=c.name, card_type=c.card_type,
                cost=c.cost, influence=c.influence, attack=c.attack,
                health=c.health, is_power=c.is_power
            )
            for c in cards
        ]
        random.shuffle(deck)

        player = PlayerState(name=name, influence={f: 0 for f in self.FACTIONS})
        player.deck = deck

        # Draw opening hand with mulligan logic
        self._draw_opening_hand(player)

        return player

    def _draw_opening_hand(self, player: PlayerState):
        """Draw opening hand with mulligan logic."""
        # Draw 7
        for _ in range(7):
            if player.deck:
                player.hand.append(player.deck.pop(0))

        # Check if we should mulligan
        power_count = sum(1 for c in player.hand if c.is_power)
        if power_count <= 2 or power_count >= 5:
            # Mulligan - shuffle hand back and draw 6
            player.deck.extend(player.hand)
            player.hand = []
            random.shuffle(player.deck)
            for _ in range(6):
                if player.deck:
                    player.hand.append(player.deck.pop(0))

    def _parse_influence(self, influence_str: str) -> Dict[str, int]:
        """Parse influence string."""
        result = {}
        for char in influence_str:
            if char in self.FACTIONS:
                result[char] = result.get(char, 0) + 1
        return result

    def _can_play(self, player: PlayerState, card: BattleCard) -> bool:
        """Check if player can play a card."""
        if card.is_power:
            return not player.power_played_this_turn

        if card.cost > player.power_available:
            return False

        # Check influence
        required = self._parse_influence(card.influence)
        for faction, count in required.items():
            if player.influence.get(faction, 0) < count:
                return False

        return True

    def _play_card(self, player: PlayerState, card: BattleCard):
        """Play a card from hand."""
        if card not in player.hand:
            return

        player.hand.remove(card)

        if card.is_power:
            player.power_played_this_turn = True
            player.power_max += 1
            player.power_available += 1

            for char in card.influence:
                if char in self.FACTIONS:
                    player.influence[char] = player.influence.get(char, 0) + 1

            player.void.append(card)
        elif card.card_type == 'Unit':
            card.can_attack = False  # Summoning sickness
            player.battlefield.append(card)
            player.power_available -= card.cost
        else:
            # Spells go to void
            player.void.append(card)
            player.power_available -= card.cost

    def _ai_play_turn(self, player: PlayerState):
        """Simple AI: play power, then play units by cost."""
        # Play power first
        power_cards = [c for c in player.hand if c.is_power]
        if power_cards and not player.power_played_this_turn:
            self._play_card(player, power_cards[0])

        # Play units (highest cost first that we can afford)
        while True:
            playable = [
                c for c in player.hand
                if c.card_type == 'Unit' and self._can_play(player, c)
            ]
            if not playable:
                break
            playable.sort(key=lambda c: c.cost, reverse=True)
            self._play_card(player, playable[0])

    def _resolve_combat(self, attacker: PlayerState, defender: PlayerState) -> int:
        """
        Resolve combat phase.

        Simple rules:
        - All units that can attack do attack
        - Defender blocks with highest health unit against highest attack attacker
        - Unblocked damage goes to face

        Returns damage dealt to defender.
        """
        attackers = [u for u in attacker.battlefield if u.can_attack and not u.is_tapped]
        if not attackers:
            return 0

        blockers = list(defender.battlefield)
        total_damage = 0

        # Sort attackers by attack power (highest first)
        attackers.sort(key=lambda u: u.attack, reverse=True)

        for atk in attackers:
            if blockers:
                # Defender blocks with their highest health unit
                blockers.sort(key=lambda u: u.current_health, reverse=True)
                blocker = blockers[0]

                # Combat
                blocker.current_health -= atk.attack
                atk.current_health -= blocker.attack

                # Check if blocker dies
                if blocker.current_health <= 0:
                    defender.battlefield.remove(blocker)
                    defender.void.append(blocker)
                    blockers.remove(blocker)

                # Check if attacker dies
                if atk.current_health <= 0:
                    attacker.battlefield.remove(atk)
                    attacker.void.append(atk)
            else:
                # Unblocked - damage to face
                total_damage += atk.attack

        return total_damage

    def simulate_game(self) -> BattleResult:
        """Simulate a single game between the two decks."""
        player1 = self._create_player(self.deck1_cards, self.deck1_name)
        player2 = self._create_player(self.deck2_cards, self.deck2_name)

        turn = 0
        p1_units_played = 0
        p2_units_played = 0
        p1_damage_dealt = 0
        p2_damage_dealt = 0

        # Determine who goes first (random)
        current, other = (player1, player2) if random.random() < 0.5 else (player2, player1)

        while turn < self.MAX_TURNS:
            turn += 1

            # === Current player's turn ===
            # Untap
            current.power_available = current.power_max
            current.power_played_this_turn = False
            for unit in current.battlefield:
                unit.is_tapped = False
                unit.can_attack = True  # Remove summoning sickness

            # Draw (except turn 1 for player going first)
            if not (turn == 1 and current == player1):
                if current.deck:
                    current.hand.append(current.deck.pop(0))
                else:
                    # Deck empty - lose
                    break

            # Track units before playing
            units_before = len(current.battlefield)

            # AI plays the turn
            self._ai_play_turn(current)

            # Track units played
            units_after = len(current.battlefield)
            if current == player1:
                p1_units_played += (units_after - units_before)
            else:
                p2_units_played += (units_after - units_before)

            # Combat
            damage = self._resolve_combat(current, other)
            other.health -= damage
            if current == player1:
                p1_damage_dealt += damage
            else:
                p2_damage_dealt += damage

            # Check for win
            if other.health <= 0:
                break

            # Swap players
            current, other = other, current

        # Determine winner
        if player1.health <= 0 and player2.health <= 0:
            winner = 'draw'
        elif player2.health <= 0:
            winner = 'player1'
        elif player1.health <= 0:
            winner = 'player2'
        elif not player1.deck:
            winner = 'player2'
        elif not player2.deck:
            winner = 'player1'
        else:
            # Went to max turns - higher health wins
            if player1.health > player2.health:
                winner = 'player1'
            elif player2.health > player1.health:
                winner = 'player2'
            else:
                winner = 'draw'

        return BattleResult(
            winner=winner,
            turns=turn,
            player1_final_health=max(0, player1.health),
            player2_final_health=max(0, player2.health),
            player1_units_played=p1_units_played,
            player2_units_played=p2_units_played,
            player1_damage_dealt=p1_damage_dealt,
            player2_damage_dealt=p2_damage_dealt,
        )

    def simulate_games(self, num_games: int = 100) -> SimulationResult:
        """Run multiple simulated games and aggregate results."""
        results = []
        p1_wins = 0
        p2_wins = 0
        draws = 0
        total_turns = 0
        total_p1_health = 0
        total_p2_health = 0

        for _ in range(num_games):
            result = self.simulate_game()
            results.append(result)

            if result.winner == 'player1':
                p1_wins += 1
            elif result.winner == 'player2':
                p2_wins += 1
            else:
                draws += 1

            total_turns += result.turns
            total_p1_health += result.player1_final_health
            total_p2_health += result.player2_final_health

        return SimulationResult(
            games_played=num_games,
            player1_wins=p1_wins,
            player2_wins=p2_wins,
            draws=draws,
            avg_game_length=total_turns / num_games,
            avg_player1_health=total_p1_health / num_games,
            avg_player2_health=total_p2_health / num_games,
            player1_win_rate=(p1_wins / num_games) * 100,
            player2_win_rate=(p2_wins / num_games) * 100,
            results=results,
        )
