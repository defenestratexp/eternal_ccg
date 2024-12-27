#!/home/tthompson/.virtualenvs/n9n/bin/python
import random


def parse_deck(deck_file):
    with open(deck_file, "r") as file:
        lines = file.readlines()

    deck = []
    for line in lines:
        line = line.strip()
        if (
            line
            and not line.startswith("FORMAT")
            and not line.startswith("---------------MARKET---------------")
        ):
            parts = line.rsplit(" ", 2)
            card_name = parts[0]
            quantity = int(parts[1])
            set_info = parts[2]
            for _ in range(quantity):
                deck.append((card_name, set_info))
    return deck


def draw_initial_hand(deck, hand_size=7):
    hand = random.sample(deck, hand_size)
    return hand


def simulate_draws(deck_file, num_draws=5):
    deck = parse_deck(deck_file)

    for draw in range(num_draws):
        hand = draw_initial_hand(deck)
        print(f"Draw {draw + 1}:")
        for card in hand:
            card_name, set_info = card
            if (
                "Sigil" in card_name or "Cylix" in card_name or "Waystone" in card_name
            ):  # Adjust power card recognition here
                print(f"{card_name} - P ({set_info})")
            else:
                print(f"{card_name} ({set_info})")
        print("\n")


if __name__ == "__main__":
    simulate_draws("deck_text/deck.txt")
