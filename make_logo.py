"""Génère un logo Sudoku sans fond bleu : juste la grille"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = os.path.dirname(os.path.abspath(__file__))


def make_icon(size=512):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    margin = int(size * 0.04)
    grid_size = size - 2 * margin
    cell = grid_size // 9
    grid_size = cell * 9
    gx = (size - grid_size) // 2
    gy = (size - grid_size) // 2

    d.rounded_rectangle(
        (gx - 8, gy - 8, gx + grid_size + 8, gy + grid_size + 8),
        radius=int(size * 0.05),
        fill=(255, 255, 255, 255)
    )

    thin_color = (200, 210, 230, 255)
    for i in range(1, 9):
        if i % 3 == 0:
            continue
        d.line(
            (gx + i * cell, gy, gx + i * cell, gy + grid_size),
            fill=thin_color, width=max(2, size // 200)
        )
        d.line(
            (gx, gy + i * cell, gx + grid_size, gy + i * cell),
            fill=thin_color, width=max(2, size // 200)
        )

    bold_color = (30, 42, 71, 255)
    bold_w = max(6, size // 80)
    for i in range(4):
        x = gx + i * cell * 3
        y = gy + i * cell * 3
        d.line((x, gy, x, gy + grid_size), fill=bold_color, width=bold_w)
        d.line((gx, y, gx + grid_size, y), fill=bold_color, width=bold_w)

    pattern = {
        (0, 0): '5', (0, 4): '7', (0, 7): '1',
        (1, 2): '3', (1, 5): '9',
        (2, 1): '8', (2, 8): '6',
        (3, 0): '1', (3, 3): '4', (3, 6): '2',
        (4, 4): '8',
        (5, 2): '7', (5, 5): '3', (5, 8): '9',
        (6, 0): '9', (6, 7): '4',
        (7, 3): '2', (7, 6): '5',
        (8, 1): '6', (8, 4): '1', (8, 8): '7',
    }

    font_size = int(cell * 0.7)
    font = None
    for candidate in [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
        '/Library/Fonts/Arial Bold.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
    ]:
        if os.path.exists(candidate):
            font = ImageFont.truetype(candidate, font_size)
            break
    if font is None:
        font = ImageFont.load_default()

    primary = (45, 108, 223, 255)
    dark = (30, 42, 71, 255)
    for (r, c), num in pattern.items():
        color = primary if (r + c) % 2 == 0 else dark
        x = gx + c * cell + cell // 2
        y = gy + r * cell + cell // 2
        try:
            bbox = d.textbbox((0, 0), num, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            d.text((x - tw // 2, y - th // 2 - bbox[1]), num,
                   font=font, fill=color)
        except AttributeError:
            tw, th = d.textsize(num, font=font)
            d.text((x - tw // 2, y - th // 2), num, font=font, fill=color)

    return img


def make_presplash(size=1024):
    img = Image.new('RGBA', (size, size), (244, 246, 251, 255))
    d = ImageDraw.Draw(img)

    icon_size = size // 2
    icon = make_icon(icon_size)
    pos = ((size - icon_size) // 2, (size - icon_size) // 2 - icon_size // 6)
    img.paste(icon, pos, icon)

    font_size = size // 16
    font = None
    for candidate in [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
    ]:
        if os.path.exists(candidate):
            font = ImageFont.truetype(candidate, font_size)
            break
    if font is None:
        font = ImageFont.load_default()

    text = 'SUDOKU'
    try:
        bbox = d.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        tw, _ = d.textsize(text, font=font)
    d.text(((size - tw) // 2, pos[1] + icon_size + size // 20),
           text, font=font, fill=(30, 42, 71, 255))

    return img


if __name__ == '__main__':
    icon = make_icon(512)
    icon.save(os.path.join(OUT, 'icon.png'))
    print('icon.png ok')

    presplash = make_presplash(1024)
    presplash.save(os.path.join(OUT, 'presplash.png'))
    print('presplash.png ok')
