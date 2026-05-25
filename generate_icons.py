#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs('static/icons/web', exist_ok=True)

SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
BG = (15, 15, 26)       # #0f0f1a
ACCENT = (124, 92, 255) # #7c5cff
WHITE = (255, 255, 255)

def draw_rounded_rect(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    r = radius
    draw.pieslice([x1, y1, x1+r*2, y1+r*2], 180, 270, fill=fill)
    draw.pieslice([x2-r*2, y1, x2, y1+r*2], 270, 360, fill=fill)
    draw.pieslice([x1, y2-r*2, x1+r*2, y2], 90, 180, fill=fill)
    draw.pieslice([x2-r*2, y2-r*2, x2, y2], 0, 90, fill=fill)
    draw.rectangle([x1+r, y1, x2-r, y2], fill=fill)
    draw.rectangle([x1, y1+r, x2, y2-r], fill=fill)

def generate_icon(size):
    img = Image.new('RGB', (size, size), BG)
    draw = ImageDraw.Draw(img)

    # Фоновый круг/квадрат с закруглением
    pad = size // 12
    draw_rounded_rect(draw, [pad, pad, size-pad, size-pad], size//8, ACCENT)

    # Глаз / буква К
    try:
        font_size = int(size * 0.45)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("arial.ttf", int(size*0.45))
        except:
            font = ImageFont.load_default()

    text = "К"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - size//20

    # Тень
    draw.text((x+3, y+3), text, fill=(0,0,0,80), font=font)
    # Текст
    draw.text((x, y), text, fill=WHITE, font=font)

    # Маска для maskable (круг)
    if size >= 192:
        # Добавим безопасную зону по центру
        pass

    path = f'static/icons/web/icon-{size}.png'
    img.save(path, 'PNG')
    print(f"✓ {path}")

if __name__ == '__main__':
    print("🎨 Генерация иконок...")
    for s in SIZES:
        generate_icon(s)
    print("✅ Готово!")
