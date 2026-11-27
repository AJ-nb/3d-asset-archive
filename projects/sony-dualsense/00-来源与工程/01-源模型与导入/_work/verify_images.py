from pathlib import Path
from struct import unpack

from PIL import Image, ImageDraw, ImageFont

delivery = Path.cwd() / '4k'
renders = delivery / 'renders'
shots = [
    'dualsense-white-01-hero',
    'dualsense-white-02-front',
    'dualsense-white-03-controls',
    'dualsense-white-04-rear',
    'dualsense-white-06-grip',
    'white-clay-01-hero',
    'white-clay-02-front',
    'white-clay-05-shoulder',
]
assert {path.stem for path in renders.glob('*.png')} == set(shots)
qa = delivery.parent / '_work' / 'qa'
tiles = Image.new('RGB', (1960, 667), '#141B23')
drawing = ImageDraw.Draw(tiles)
font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 20)
for idx, shot in enumerate(shots):
    path = renders / (shot + '.png')
    with path.open('rb') as file:
        header = file.read(29)
    assert header[:8] == b'\x89PNG\r\n\x1a\n'
    width, height, bits, format_code = unpack('>IIBB', header[16:26])
    assert (width, height, bits, format_code) == (3840, 2160, 16, 2), (shot, width, height, bits, format_code)
    with Image.open(path) as image:
        image.load()
        assert image.size == (3840, 2160)
        assert image.getbbox() == (0, 0, 3840, 2160)
        if shot == 'dualsense-white-01-hero':
            preview = image.resize((1600, 900), Image.Resampling.LANCZOS)
            preview.save(delivery / 'DualSense-preview.jpg', quality=95, subsampling=0, optimize=True)
        if shot in ('dualsense-white-03-controls', 'dualsense-white-06-grip'):
            image.crop((1040, 600, 2160, 1520)).save(qa / (shot + '-100pct.jpg'), quality=97, subsampling=0)
        thumb = image.resize((460, 259), Image.Resampling.LANCZOS)
        x, y = 16 + (idx % 4) * 488, 18 + (idx // 4) * 326
        tiles.paste(thumb, (x, y))
        drawing.text((x, y + 269), shot, fill='#EAEDF3', font=font)
    print('PASS', shot, width, height, str(bits) + '-bit RGB', path.stat().st_size)
tiles.save(qa / '4k-contact-sheet.jpg', quality=93)
