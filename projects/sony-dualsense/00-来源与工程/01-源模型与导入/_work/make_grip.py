from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

size = 1024
tile = Image.new('L', (size, size))
drawing = ImageDraw.Draw(tile)
step = size // 8
radius = 28
width = 15
for row in range(8):
    for col in range(8):
        x = col * step + step // 2 + (row % 2) * step // 5
        y = row * step + step // 2
        role = (2 * row + col) % 4
        if role == 0:
            points = [(x + radius * cos(radians(ang)), y + radius * sin(radians(ang)))
                      for ang in (-90, 30, 150, -90)]
            drawing.line(points, fill=226, width=width, joint='curve')
        elif role == 1:
            drawing.ellipse((x - radius, y - radius, x + radius, y + radius),
                            outline=226, width=width)
        elif role == 2:
            d = radius * .76
            drawing.line((x - d, y - d, x + d, y + d), fill=226, width=width)
            drawing.line((x - d, y + d, x + d, y - d), fill=226, width=width)
        else:
            d = radius * .82
            drawing.rectangle((x - d, y - d, x + d, y + d), outline=226, width=width)
tile.filter(ImageFilter.GaussianBlur(4.3)).save(Path.cwd() / '_work' / 'grip-symbol-height.png')
