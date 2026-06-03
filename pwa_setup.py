#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw, ImageFont
import json

# Создаем директории
def create_directories():
    """Создает необходимые директории"""
    dirs = [
        'static',
        'static/icons',
        'static/screenshots'
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"✓ Created directory: {dir_path}")

def generate_icon(size, output_path):
    """Генерирует иконку приложения"""
    # Создаем градиентный фон
    img = Image.new('RGB', (size, size), color='white')
    draw = ImageDraw.Draw(img)
    
    # Градиент от #667eea до #764ba2
    for i in range(size):
        r = int(102 + (118 - 102) * i / size)
        g = int(126 + (75 - 126) * i / size)
        b = int(234 + (162 - 234) * i / size)
        draw.line([(0, i), (size, i)], fill=(r, g, b))
    
    # Рисуем символ
    # Простой символ "OCR"
    try:
        # Пытаемся использовать системный шрифт
        font_size = size // 3
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    text = "OCR"
    
    # Получаем размер текста
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Центрируем текст
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    # Рисуем белый текст с тенью
    shadow_offset = size // 50
    draw.text((x + shadow_offset, y + shadow_offset), text, fill=(0, 0, 0, 128), font=font)
    draw.text((x, y), text, fill='white', font=font)
    
    # Сохраняем
    img.save(output_path, 'PNG', optimize=True)
    print(f"✓ Generated icon: {output_path} ({size}x{size})")

def generate_all_icons():
    """Генерирует все необходимые иконки"""
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    for size in sizes:
        output_path = f"static/icons/icon-{size}x{size}.png"
        generate_icon(size, output_path)

def create_manifest():
    """Создает manifest.json"""
    manifest = {
        "name": "Professional OCR System",
        "short_name": "OCR Pro",
        "description": "AI-Powered Text Recognition, Translation & Speech",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#667eea",
        "theme_color": "#667eea",
        "orientation": "portrait",
        "icons": [
            {
                "src": f"/static/icons/icon-{size}x{size}.png",
                "sizes": f"{size}x{size}",
                "type": "image/png",
                "purpose": "any maskable"
            }
            for size in [72, 96, 128, 144, 152, 192, 384, 512]
        ],
        "categories": ["productivity", "utilities", "education"]
    }
    
    with open('static/manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print("✓ Created manifest.json")

def create_service_worker():
    """Создает service-worker.js"""
    sw_content = """const CACHE_NAME = 'ocr-pro-v1.0.0';
const urlsToCache = [
  '/',
  '/static/manifest.json'
];

// Install
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
      .then(() => self.skipWaiting())
  );
});

// Activate
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch - Network First strategy
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  if (event.request.url.includes('/api/')) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (!response || response.status !== 200) {
          return response;
        }
        const responseToCache = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseToCache);
        });
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
"""
    
    with open('static/service-worker.js', 'w', encoding='utf-8') as f:
        f.write(sw_content)
    
    print("✓ Created service-worker.js")

def update_flask_app():
    """Инструкции по обновлению Flask app"""
    instructions = """
═══════════════════════════════════════════════════════════════════
✓ PWA Setup Complete!
═══════════════════════════════════════════════════════════════════

📁 Created structure:
  static/
    ├── manifest.json
    ├── service-worker.js
    └── icons/
        ├── icon-72x72.png
        ├── icon-96x96.png
        ├── icon-128x128.png
        ├── icon-144x144.png
        ├── icon-152x152.png
        ├── icon-192x192.png
        ├── icon-384x384.png
        └── icon-512x512.png

📝 Next steps:

1. Убедись что templates/index.html обновлен (уже обновлен в артефакте)

2. Добавь в app.py маршрут для статики (если еще нет):

   from flask import send_from_directory
   
   @app.route('/static/<path:path>')
   def send_static(path):
       return send_from_directory('static', path)

3. Перезапусти Flask сервер:
   
   python app.py

4. Открой на телефоне через ngrok:
   
   ngrok http 5000
   
5. В Chrome на телефоне увидишь "Install App" или кнопку установки

6. После установки приложение будет на главном экране!

═══════════════════════════════════════════════════════════════════
🎯 Testing PWA:

На Android:
  1. Открой Chrome
  2. Зайди на сайт
  3. Меню → "Add to Home screen"
  4. Или нажми кнопку "📲 Install App"

На iOS:
  1. Открой Safari
  2. Зайди на сайт  
  3. Нажми Share → "Add to Home Screen"

═══════════════════════════════════════════════════════════════════
"""
    
    print(instructions)

def main():
    """Главная функция"""
    print("\n🚀 Setting up PWA for OCR System...\n")
    
    # 1. Создаем директории
    create_directories()
    print()
    
    # 2. Генерируем иконки
    print("📱 Generating icons...")
    generate_all_icons()
    print()
    
    # 3. Создаем manifest
    print("📄 Creating manifest...")
    create_manifest()
    print()
    
    # 4. Создаем service worker
    print("⚙️ Creating service worker...")
    create_service_worker()
    print()
    
    # 5. Показываем инструкции
    update_flask_app()

if __name__ == '__main__':
    main()