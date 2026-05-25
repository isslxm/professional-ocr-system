# Крупно v3.0 — OCR для пожилых и слабовидящих

## 🚀 Быстрый старт

### 1. Установи зависимости
```bash
pip install flask flask-cors pillow pytesseract numpy opencv-python-headless
```

### 2. Установи Tesseract OCR

**Windows:**
1. Скачай с [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
2. Установи в `C:\Program Files\Tesseract-OCR`
3. Добавь в PATH: `C:\Program Files\Tesseract-OCR`
4. Скачай `rus.traineddata` и положи в `C:\Program Files\Tesseract-OCR\tessdata`

**Проверь:**
```bash
tesseract --version
tesseract --list-langs   # должен быть rus
```

### 3. Сгенерируй иконки
```bash
python generate_icons.py
```

### 4. Запусти сервер
```bash
python app.py
```

Открой `http://localhost:5000`

### 5. Для телефона (HTTPS обязателен для камеры)
```bash
# Установи ngrok
ngrok http 5000
# Открой https-ссылку на телефоне
```

## 📱 Установка на устройство (PWA)

### Android (Chrome)
1. Открой сайт в Chrome
2. Появится баннер "Установить приложение"
3. Нажми "Установить"
4. Приложение появится на главном экране

### iOS (Safari)
1. Открой сайт в Safari
2. Нажми "Поделиться" (Share)
3. "На экран Домой" (Add to Home Screen)
4. Нажми "Добавить"

### Windows/Mac (Chrome/Edge)
1. В адресной строке появится иконка установки (⊕)
2. Нажми "Установить Крупно"

## ✨ Функции

- 📷 **Камера** с зумом и вспышкой
- 🔍 **Режим лупы** для быстрого увеличения
- 📝 **OCR** с усилением мелкого текста
- 🔊 **Озвучка** офлайн через Web Speech API
- 💊 **Режим "Лекарство"** — выделяет дозировку
- 📜 **История** последних 30 сканов
- 🌙 **Тёмная/светлая тема**
- 📲 **Установка** как нативное приложение

## 🛠️ Структура

```
├── app.py              # Flask backend
├── index.html          # Frontend (PWA)
├── generate_icons.py   # Генератор иконок
├── static/
│   ├── manifest.json       # PWA манифест
│   ├── service-worker.js   # Офлайн-кэш
│   └── icons/
│       ├── icon-72x72.png
│       ├── icon-192x192.png
│       └── icon-512x512.png
```

## ⚠️ Важно

- **Камера работает только по HTTPS** — используй ngrok для теста на телефоне
- **Озвучка работает офлайн** — используется Web Speech API браузера
- **OCR требует Tesseract** — без него распознавание не работает
