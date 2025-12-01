"""
Deck Analysis tools for Eternal Card Game decks.

Provides various analysis features:
- Mana curve analysis
- Card type distribution
- Influence requirements analysis
- Synergy detection

ARCHITECTURE OVERVIEW
=====================
This module provides comprehensive deck composition analysis. It examines what
cards are in a deck and how they work together, without any randomization.

Analysis Types:
1. CURVE ANALYSIS - Distribution of cards by power cost
   - Shows where the deck's plays concentrate (aggro peaks at 1-2, control at 4+)
   - Calculates average mana cost of non-power cards
   - Identifies curve peaks and gaps

2. TYPE DISTRIBUTION - Breakdown by card type
   - Units vs Spells vs Attachments vs Relics
   - Percentage calculations for deck composition
   - Grouped card lists for reference

3. INFLUENCE REQUIREMENTS - Casting difficulty analysis
   - Identifies cards with demanding influence (e.g., FFF, PPSS)
   - Calculates "difficulty score": cost + (pips * 2) + (factions * 3)
   - Flags potential bottlenecks (cards hard to cast on curve)

4. SYNERGY ANALYSIS - Keyword and tribal detection
   - Scans card text for ~40 Eternal keywords (Flying, Lifesteal, Aegis, etc.)
   - Parses unit types for tribal synergies (Soldier, Valkyrie, etc.)
   - Detects "enablers" (cards that grant abilities) vs "payoffs" (cards that benefit)
   - Identifies synergy packages when keyword/tribal density exceeds threshold

USAGE
=====
    from decks.deck_analysis import DeckAnalyzer

    analyzer = DeckAnalyzer(deck)

    # Individual analyses
    curve = analyzer.analyze_curve()
    types = analyzer.analyze_type_distribution()
    influence = analyzer.analyze_influence_requirements()
    synergies = analyzer.analyze_synergies()

    # Or get everything at once
    full = analyzer.get_full_analysis()

DESIGN DECISIONS
================
1. Market cards are excluded from analysis (main deck only)
2. Each card counted by quantity (4x Torch = 4 cards in curve)
3. Card lists deduplicated for display (show card once with quantity)
4. Synergy packages require minimum thresholds (e.g., 4+ Lifesteal cards)
5. Difficulty scoring weights multi-faction cards higher than single-faction
"""

import re
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


@dataclass
class SynergyAnalysis:
    """Synergy and keyword analysis results."""
    # Keywords found: {'Flying': {'count': 12, 'cards': [...]}, ...}
    keywords: Dict[str, dict]
    # Unit types/tribes: {'Soldier': {'count': 8, 'cards': [...]}, ...}
    unit_types: Dict[str, dict]
    # Synergy packages detected: [{'name': 'Lifesteal Package', 'cards': [...], 'strength': 0.8}, ...]
    synergy_packages: List[dict]
    # Cards that enable synergies (grant keywords, buff tribes, etc.)
    enablers: List[dict]
    # Cards that payoff synergies (benefit from keywords, tribal, etc.)
    payoffs: List[dict]


class DeckAnalyzer:
    """
    Comprehensive deck analysis tool.
    """

    FACTIONS = {'F': 'Fire', 'T': 'Time', 'J': 'Justice', 'P': 'Primal', 'S': 'Shadow'}

    # Keywords to detect in card text
    KEYWORDS = [
        'Flying', 'Overwhelm', 'Lifesteal', 'Deadly', 'Quickdraw', 'Endurance',
        'Aegis', 'Charge', 'Unblockable', 'Revenge', 'Destiny', 'Echo',
        'Warp', 'Infiltrate', 'Killer', 'Reckless', 'Scout', 'Mentor',
        'Student', 'Tribute', 'Ultimate', 'Summon', 'Entomb', 'Spark',
        'Spellcraft', 'Empower', 'Twist', 'Plunder', 'Imbue', 'Inscribe',
        'Amplify', 'Invoke', 'Bond', 'Ally', 'Renown', 'Berserk',
        'Double Damage', 'Lifegain', 'Silence', 'Stun', 'Shift',
    ]

    # Patterns indicating enablers (cards that grant abilities to others)
    ENABLER_PATTERNS = [
        'gives', 'grant', 'other .* get', 'other .* have', 'your .* get',
        'your .* have', 'all .* get', 'all .* have', 'units get', 'units have',
        'when another', 'each other', 'friendly .* get', 'friendly .* have',
    ]

    # Patterns indicating payoffs (cards that benefit from conditions)
    PAYOFF_PATTERNS = [
        'for each', 'if you have', 'when you play', 'whenever you',
        'gets \\+', 'gain \\+', 'equal to', 'based on', 'per ',
        'for every', 'if .* in your void', 'if .* in play',
    ]

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

    def analyze_synergies(self) -> SynergyAnalysis:
        """
        Analyze synergies, keywords, and tribal elements in the deck.

        Returns:
            SynergyAnalysis with keyword, tribal, and synergy data
        """
        keywords = defaultdict(lambda: {'count': 0, 'cards': []})
        unit_types = defaultdict(lambda: {'count': 0, 'cards': []})
        enablers = []
        payoffs = []

        seen_cards = set()

        for card in self.non_power_cards:
            card_text = card['card_text'] or ''
            card_text_lower = card_text.lower()
            card_name = card['name']

            # Skip duplicates for card lists (but count quantities)
            is_new_card = card_name not in seen_cards
            if is_new_card:
                seen_cards.add(card_name)

            # Detect keywords
            for keyword in self.KEYWORDS:
                # Check if keyword appears in card text (case-insensitive)
                if re.search(rf'\b{keyword}\b', card_text, re.IGNORECASE):
                    keywords[keyword]['count'] += card['quantity']
                    if is_new_card:
                        keywords[keyword]['cards'].append({
                            'name': card_name,
                            'quantity': card['quantity'],
                            'card_type': card['card_type'],
                            'cost': card['cost'],
                        })

            # Parse unit types
            if card['unit_types']:
                types = [t.strip() for t in card['unit_types'].split(',') if t.strip()]
                for utype in types:
                    unit_types[utype]['count'] += card['quantity']
                    if is_new_card:
                        unit_types[utype]['cards'].append({
                            'name': card_name,
                            'quantity': card['quantity'],
                            'card_type': card['card_type'],
                            'cost': card['cost'],
                        })

            # Detect enablers
            if is_new_card:
                for pattern in self.ENABLER_PATTERNS:
                    if re.search(pattern, card_text_lower):
                        enablers.append({
                            'name': card_name,
                            'quantity': card['quantity'],
                            'card_type': card['card_type'],
                            'cost': card['cost'],
                            'text': card_text[:100] + '...' if len(card_text) > 100 else card_text,
                        })
                        break

                # Detect payoffs
                for pattern in self.PAYOFF_PATTERNS:
                    if re.search(pattern, card_text_lower):
                        payoffs.append({
                            'name': card_name,
                            'quantity': card['quantity'],
                            'card_type': card['card_type'],
                            'cost': card['cost'],
                            'text': card_text[:100] + '...' if len(card_text) > 100 else card_text,
                        })
                        break

        # Detect synergy packages
        synergy_packages = self._detect_synergy_packages(keywords, unit_types)

        # Sort by count
        keywords = dict(sorted(keywords.items(), key=lambda x: x[1]['count'], reverse=True))
        unit_types = dict(sorted(unit_types.items(), key=lambda x: x[1]['count'], reverse=True))

        return SynergyAnalysis(
            keywords=dict(keywords),
            unit_types=dict(unit_types),
            synergy_packages=synergy_packages,
            enablers=enablers,
            payoffs=payoffs,
        )

    def _detect_synergy_packages(self, keywords: dict, unit_types: dict) -> List[dict]:
        """
        Detect common synergy packages based on keyword/tribal density.

        Args:
            keywords: Keyword analysis results
            unit_types: Unit type analysis results

        Returns:
            List of detected synergy packages
        """
        packages = []
        total_non_power = len(self.non_power_cards)
        if total_non_power == 0:
            return packages

        # Keyword-based packages
        keyword_packages = {
            'Lifesteal': {'name': 'Lifesteal Package', 'threshold': 4, 'description': 'Life gain synergies'},
            'Flying': {'name': 'Evasion Package', 'threshold': 6, 'description': 'Aerial threats'},
            'Overwhelm': {'name': 'Overwhelm Package', 'threshold': 4, 'description': 'Damage through blockers'},
            'Aegis': {'name': 'Aegis Package', 'threshold': 4, 'description': 'Protected threats'},
            'Charge': {'name': 'Aggro Package', 'threshold': 4, 'description': 'Fast damage'},
            'Warp': {'name': 'Warp Package', 'threshold': 4, 'description': 'Top-deck manipulation'},
            'Revenge': {'name': 'Revenge Package', 'threshold': 3, 'description': 'Recurring threats'},
            'Killer': {'name': 'Killer Package', 'threshold': 3, 'description': 'Removal on units'},
            'Deadly': {'name': 'Deadly Package', 'threshold': 4, 'description': 'Efficient blockers'},
            'Infiltrate': {'name': 'Infiltrate Package', 'threshold': 3, 'description': 'Face damage payoffs'},
            'Summon': {'name': 'ETB Effects', 'threshold': 6, 'description': 'Enter-the-battlefield value'},
            'Entomb': {'name': 'Death Triggers', 'threshold': 4, 'description': 'On-death value'},
            'Ultimate': {'name': 'Ultimate Package', 'threshold': 3, 'description': 'Late-game power'},
        }

        for keyword, config in keyword_packages.items():
            if keyword in keywords and keywords[keyword]['count'] >= config['threshold']:
                strength = min(1.0, keywords[keyword]['count'] / (config['threshold'] * 2))
                packages.append({
                    'name': config['name'],
                    'type': 'keyword',
                    'keyword': keyword,
                    'count': keywords[keyword]['count'],
                    'cards': keywords[keyword]['cards'],
                    'strength': round(strength, 2),
                    'description': config['description'],
                })

        # Tribal packages (any tribe with 6+ cards)
        for tribe, data in unit_types.items():
            if data['count'] >= 6:
                strength = min(1.0, data['count'] / 16)
                packages.append({
                    'name': f'{tribe} Tribal',
                    'type': 'tribal',
                    'tribe': tribe,
                    'count': data['count'],
                    'cards': data['cards'],
                    'strength': round(strength, 2),
                    'description': f'{tribe} creature synergies',
                })

        # Sort by strength
        packages.sort(key=lambda x: x['strength'], reverse=True)
        return packages

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
            'synergies': self.analyze_synergies(),
            'total_cards': len(self.cards),
            'power_count': len(self.power_cards),
            'non_power_count': len(self.non_power_cards),
        }
