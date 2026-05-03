"""
Generate Blixtro Android launcher icons from src/static/images/Blixtro.png.

The source image is 563×563 RGB PNG — the official Blixtro logo.
We resize it to each required mipmap density with a dark navy background
(#0f172a) and 12% padding so the logo sits comfortably inside the icon bounds.

Sizes:
  mipmap-mdpi:    48x48
  mipmap-hdpi:    72x72
  mipmap-xhdpi:   96x96
  mipmap-xxhdpi:  144x144
  mipmap-xxxhdpi: 192x192

Run from the project root:
  python script/generate_icons.py
"""

import os
from PIL import Image, ImageDraw

SOURCE_PNG = os.path.join('src', 'static', 'images', 'Blixtro.png')

SIZES = {
    'mipmap-mdpi':    48,
    'mipmap-hdpi':    72,
    'mipmap-xhdpi':   96,
    'mipmap-xxhdpi':  144,
    'mipmap-xxxhdpi': 192,
}

RES_DIR = os.path.join('android', 'app', 'src', 'main', 'res')
BG_COLOR = (15, 23, 42)   # #0f172a — Blixtro dark navy
PADDING  = 0.12           # 12% padding on each side


def make_icon(logo: Image.Image, size: int) -> Image.Image:
    """
    Compose a square icon at `size`×`size`:
    - Dark navy background
    - Logo centred with PADDING% breathing room on each side
    """
    # Background
    icon = Image.new('RGBA', (size, size), BG_COLOR + (255,))

    # Logo area: (1 - 2*PADDING) * size
    logo_size = int(size * (1 - 2 * PADDING))
    logo_size = max(logo_size, 1)

    # Resize logo with high-quality Lanczos resampling
    logo_resized = logo.resize((logo_size, logo_size), Image.LANCZOS)

    # Centre it
    offset = (size - logo_size) // 2
    if logo_resized.mode == 'RGBA':
        icon.paste(logo_resized, (offset, offset), logo_resized)
    else:
        icon.paste(logo_resized, (offset, offset))

    return icon


def make_round(icon: Image.Image) -> Image.Image:
    """Apply a circular mask."""
    size = icon.size[0]
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    result.paste(icon, mask=mask)
    return result


def make_foreground(icon: Image.Image) -> Image.Image:
    """
    Foreground layer for adaptive icon: logo on transparent background.
    The adaptive icon system composites this over the background color.
    """
    size = icon.size[0]
    fg = Image.new('RGBA', (size, size), (0, 0, 0, 0))

    logo_size = int(size * (1 - 2 * PADDING))
    logo_size = max(logo_size, 1)
    logo_resized = logo_src.resize((logo_size, logo_size), Image.LANCZOS)

    offset = (size - logo_size) // 2
    if logo_resized.mode == 'RGBA':
        fg.paste(logo_resized, (offset, offset), logo_resized)
    else:
        fg.paste(logo_resized, (offset, offset))

    return fg


def main():
    global logo_src

    if not os.path.exists(SOURCE_PNG):
        print(f'ERROR: Source image not found at {SOURCE_PNG}')
        return

    # Load and convert source to RGBA for consistent compositing
    logo_src = Image.open(SOURCE_PNG).convert('RGBA')
    print(f'Source: {SOURCE_PNG} ({logo_src.size[0]}×{logo_src.size[1]}px, {logo_src.mode})\n')

    for folder, size in SIZES.items():
        out_dir = os.path.join(RES_DIR, folder)
        os.makedirs(out_dir, exist_ok=True)

        icon = make_icon(logo_src, size)

        # ic_launcher.png — square with dark background
        icon.convert('RGB').save(os.path.join(out_dir, 'ic_launcher.png'), optimize=True)

        # ic_launcher_round.png — circular clip
        make_round(icon).save(os.path.join(out_dir, 'ic_launcher_round.png'), optimize=True)

        # ic_launcher_foreground.png — transparent bg, for adaptive icon layer
        make_foreground(icon).save(os.path.join(out_dir, 'ic_launcher_foreground.png'), optimize=True)

        print(f'  ✓ {folder} ({size}×{size}px)')

    print('\nAll icons generated.')
    print('In Android Studio: Build → Clean Project → Rebuild Project.')


if __name__ == '__main__':
    print('Generating Blixtro launcher icons from Blixtro.png...\n')
    main()
