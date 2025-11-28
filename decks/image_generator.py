"""
Deck image generator for Eternal Forge.

Creates visual deck list images showing card thumbnails in a grid layout.
"""

import io
import requests
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings


def generate_deck_image(deck, thumbnail_width=120, columns=4):
    """
    Generate a composite image showing all cards in a deck.

    Args:
        deck: Deck model instance
        thumbnail_width: Width of each card thumbnail
        columns: Number of columns in the grid

    Returns:
        BytesIO object containing PNG image data
    """
    # Collect all deck cards with their images
    main_cards = list(deck.main_deck_cards.select_related('card'))
    market_cards = list(deck.market_cards.select_related('card'))

    # Calculate image dimensions
    # Card aspect ratio is roughly 3:4
    thumbnail_height = int(thumbnail_width * 4 / 3)
    padding = 10
    header_height = 60
    section_header_height = 30

    # Calculate total rows needed
    main_rows = (len(main_cards) + columns - 1) // columns
    market_rows = (len(market_cards) + columns - 1) // columns if market_cards else 0

    total_width = (thumbnail_width + padding) * columns + padding
    total_height = (
        header_height +  # Title
        section_header_height +  # "Main Deck" header
        (thumbnail_height + padding) * main_rows +
        (section_header_height + (thumbnail_height + padding) * market_rows if market_cards else 0) +
        padding * 2
    )

    # Create base image with dark background
    img = Image.new('RGB', (total_width, total_height), color=(31, 41, 55))
    draw = ImageDraw.Draw(img)

    # Try to load a font, fall back to default
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        card_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except (OSError, IOError):
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        card_font = ImageFont.load_default()

    # Draw title
    title = f"{deck.name} ({deck.format})"
    draw.text((padding, padding), title, fill=(251, 191, 36), font=title_font)

    # Draw deck stats
    stats = f"{deck.main_deck_count} cards | {deck.power_count} power | Market: {deck.market_count}/5"
    draw.text((padding, padding + 30), stats, fill=(156, 163, 175), font=header_font)

    # Current Y position
    y = header_height

    # Draw "Main Deck" section
    draw.text((padding, y), "Main Deck", fill=(255, 255, 255), font=header_font)
    y += section_header_height

    # Draw main deck cards
    y = _draw_card_grid(img, draw, main_cards, y, thumbnail_width, thumbnail_height, columns, padding, card_font)

    # Draw market section if present
    if market_cards:
        draw.text((padding, y), "Market", fill=(255, 255, 255), font=header_font)
        y += section_header_height
        y = _draw_card_grid(img, draw, market_cards, y, thumbnail_width, thumbnail_height, columns, padding, card_font)

    # Save to BytesIO
    output = io.BytesIO()
    img.save(output, format='PNG', optimize=True)
    output.seek(0)

    return output


def _draw_card_grid(img, draw, deck_cards, start_y, thumb_width, thumb_height, columns, padding, font):
    """
    Draw a grid of card thumbnails.

    Returns the Y position after the last row.
    """
    x = padding
    y = start_y
    col = 0

    for dc in deck_cards:
        # Try to fetch and resize card image
        card_img = _fetch_card_thumbnail(dc.card.image_url, thumb_width, thumb_height)

        if card_img:
            img.paste(card_img, (x, y))
        else:
            # Draw placeholder
            draw.rectangle([x, y, x + thumb_width, y + thumb_height], fill=(55, 65, 81), outline=(75, 85, 99))
            # Draw card name in placeholder
            draw.text((x + 5, y + thumb_height // 2), dc.card.name[:15], fill=(156, 163, 175), font=font)

        # Draw quantity badge
        if dc.quantity > 1:
            badge_text = f"{dc.quantity}x"
            badge_w = 25
            badge_h = 18
            badge_x = x + thumb_width - badge_w - 2
            badge_y = y + 2
            draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], fill=(0, 0, 0, 180))
            draw.text((badge_x + 3, badge_y + 2), badge_text, fill=(255, 255, 255), font=font)

        # Move to next position
        col += 1
        x += thumb_width + padding

        if col >= columns:
            col = 0
            x = padding
            y += thumb_height + padding

    # If we didn't complete a row, move to next row
    if col > 0:
        y += thumb_height + padding

    return y


def _fetch_card_thumbnail(image_url, width, height):
    """
    Fetch and resize a card image from URL.

    Returns PIL Image or None if fetch fails.
    """
    if not image_url:
        return None

    try:
        response = requests.get(image_url, timeout=5)
        response.raise_for_status()

        card_img = Image.open(io.BytesIO(response.content))
        card_img = card_img.convert('RGB')
        card_img = card_img.resize((width, height), Image.Resampling.LANCZOS)

        return card_img
    except Exception:
        return None
