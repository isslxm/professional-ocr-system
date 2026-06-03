from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
import io
import base64
import os
import pytesseract
from datetime import datetime
import tempfile

app = Flask(__name__, template_folder='.', static_folder='static')
CORS(app)

UPLOAD_FOLDER = 'uploads'
DEBUG_FOLDER = 'debug'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DEBUG_FOLDER, exist_ok=True)


pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Islam Osmonov\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

try:
    import easyocr
    EASYOCR_AVAILABLE = True
    print("✅ EasyOCR загружен")
except ImportError:
    EASYOCR_AVAILABLE = False
    print("⚠️ EasyOCR не установлен. Установи: pip install easyocr")

# Глобальный reader для EasyOCR
_easyocr_reader = None

def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        print("🔄 Инициализация EasyOCR (первая загрузка ~1-2 мин)...")
        _easyocr_reader = easyocr.Reader(['ru', 'en'], gpu=False)
        print("✅ EasyOCR готов")
    return _easyocr_reader


class OCRProcessor:

    @staticmethod
    def preprocess_for_small_text(image, save_debug=False):
        try:
            img_array = np.array(image)
            original = img_array.copy()

            # 1. Конвертация в RGB
            if len(img_array.shape) == 2:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
            elif img_array.shape[2] == 4:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)

            # 2. Увеличение в 2.5 раза (super-resolution-like)
            height, width = img_array.shape[:2]
            scale = 2.5
            upscaled = cv2.resize(img_array, (int(width * scale), int(height * scale)), 
                                  interpolation=cv2.INTER_CUBIC)

            # 3. Конвертация в LAB для CLAHE
            lab = cv2.cvtColor(upscaled, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)

            # 4. CLAHE с агрессивными параметрами
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)

            # 5. Обратно в RGB
            lab_enhanced = cv2.merge([l_enhanced, a, b])
            enhanced_color = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)

            # 6. Конвертация в grayscale
            gray = cv2.cvtColor(enhanced_color, cv2.COLOR_RGB2GRAY)

            # 7. Нелокальное шумоподавление (сохраняет края)
            denoised = cv2.fastNlMeansDenoising(gray, None, h=15, templateWindowSize=7, searchWindowSize=21)

            # 8. Усиление резкости (unsharp mask)
            gaussian = cv2.GaussianBlur(denoised, (0, 0), 3)
            sharpened = cv2.addWeighted(denoised, 1.8, gaussian, -0.8, 0)

            # 9. Дополнительное усиление резкости ядром
            kernel_sharpen = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened2 = cv2.filter2D(sharpened, -1, kernel_sharpen)

            # 10. Адаптивная бинаризация
            binary = cv2.adaptiveThreshold(
                sharpened2, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                15, 12
            )

            # 11. Морфология: закрытие для соединения разорванных букв
            # kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            # closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)

            # 12. Открытие для удаления шума
            # kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            # processed = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel_open)

            # Сохраняем отладочные изображения
            if save_debug:
                debug_images = {
                    '01_original': original,
                    '02_upscaled': upscaled,
                    '03_gray': gray,
                    '04_denoised': denoised,
                    '05_sharpened': sharpened2,
                    '06_binary': binary,
                    # '07_final': processed
                }
                for name, img in debug_images.items():
                    if len(img.shape) == 2:
                        cv2.imwrite(f'{DEBUG_FOLDER}/{name}.jpg', img)
                    else:
                        cv2.imwrite(f'{DEBUG_FOLDER}/{name}.jpg', cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

            # return Image.fromarray(processed)

        except Exception as e:
            print(f"❌ Ошибка предобработки: {e}")
            import traceback
            traceback.print_exc()
            return image

    @staticmethod
    def preprocess_standard(image):
        """Стандартная предобработка для обычного текста."""
        try:
            img_array = np.array(image)
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)

            thresh = cv2.adaptiveThreshold(
                blurred, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )

            kernel = np.ones((2, 2), np.uint8)
            processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            return Image.fromarray(processed)
        except Exception as e:
            print(f"❌ Ошибка стандартной предобработки: {e}")
            return image

    @staticmethod
    def preprocess_for_dark_background(image):
        """Специальная обработка для белого текста на тёмном фоне."""
        try:
            img_array = np.array(image)
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # Инвертируем цвета (белый текст → чёрный)
            inverted = cv2.bitwise_not(gray)

            # Увеличение
            height, width = gray.shape
            upscaled = cv2.resize(inverted, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)

            # Контраст
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(upscaled)

            return Image.fromarray(enhanced)
        except Exception as e:
            print(f"❌ Ошибка инвертированной предобработки: {e}")
            return image

    @staticmethod
    def recognize_tesseract(image, lang='rus', config=None, psm=6):
        """Распознавание через Tesseract с заданными параметрами."""
        try:
            if config is None:
                config = r'--oem 3 --psm {}'.format(psm)

            text = pytesseract.image_to_string(image, lang=lang, config=config)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            cleaned = '\n'.join(lines)

            return {
                'success': True,
                'text': cleaned,
                'engine': 'tesseract',
                'psm': psm,
                'raw_length': len(text),
                'cleaned_length': len(cleaned)
            }
        except Exception as e:
            return {'success': False, 'error': str(e), 'engine': 'tesseract'}

    @staticmethod
    def recognize_easyocr(image_np):
        """Распознавание через EasyOCR (лучше для фотографий)."""
        try:
            if not EASYOCR_AVAILABLE:
                return {'success': False, 'error': 'EasyOCR не установлен', 'engine': 'easyocr'}

            reader = get_easyocr_reader()
            results = reader.readtext(image_np, detail=0, paragraph=True, 
                                       contrast_ths=0.1, adjust_contrast=0.5)

            text = '\n'.join(results) if results else ''

            return {
                'success': True,
                'text': text,
                'engine': 'easyocr',
                'paragraphs': len(results)
            }
        except Exception as e:
            return {'success': False, 'error': str(e), 'engine': 'easyocr'}

    @staticmethod
    def recognize_multi_strategy(image, lang='rus', small_text=False, save_debug=False):
        """
        Мультистратегийное распознавание:
        1. Пробуем Tesseract с разными PSM
        2. Если плохо — пробуем EasyOCR
        3. Выбираем лучший результат
        """
        results = []

        # === СТРАТЕГИЯ 1: Tesseract с предобработкой для мелкого текста ===
        if small_text:
            processed = OCRProcessor.preprocess_for_small_text(image, save_debug=save_debug)
            for psm in [6, 3, 4, 11]:
                res = OCRProcessor.recognize_tesseract(processed, lang=lang, psm=psm)
                if res['success'] and len(res['text']) > 3:
                    results.append(res)
                    if len(res['text']) > 20:  # Если хороший результат — останавливаемся
                        break

        # === СТРАТЕГИЯ 2: Tesseract со стандартной предобработкой ===
        if not results or all(len(r['text']) < 5 for r in results):
            processed = OCRProcessor.preprocess_standard(image)
            for psm in [6, 3, 11]:
                res = OCRProcessor.recognize_tesseract(processed, lang=lang, psm=psm)
                if res['success'] and len(res['text']) > 3:
                    results.append(res)

        # === СТРАТЕГИЯ 3: Tesseract без предобработки (сырое изображение) ===
        if not results or all(len(r['text']) < 5 for r in results):
            res = OCRProcessor.recognize_tesseract(image, lang=lang, psm=3)
            if res['success'] and len(res['text']) > 3:
                results.append(res)

        # === СТРАТЕГИЯ 4: Инвертированные цвета (белый текст на тёмном) ===
        if not results or all(len(r['text']) < 5 for r in results):
            processed = OCRProcessor.preprocess_for_dark_background(image)
            res = OCRProcessor.recognize_tesseract(processed, lang=lang, psm=6)
            if res['success'] and len(res['text']) > 3:
                results.append({**res, 'inverted': True})

        # === СТРАТЕГИЯ 5: EasyOCR (если доступен и Tesseract не справился) ===
        if EASYOCR_AVAILABLE:
            if not results or all(len(r['text']) < 10 for r in results):
                np_image = np.array(image)
                res = OCRProcessor.recognize_easyocr(np_image)
                if res['success'] and len(res['text']) > 3:
                    results.append(res)

        # === ВЫБИРАЕМ ЛУЧШИЙ РЕЗУЛЬТАТ ===
        if not results:
            return {
                'success': False,
                'text': '',
                'error': 'Текст не распознан ни одним движком',
                'attempts': len(results)
            }

        # Сортируем по длине текста (чем больше — тем лучше, обычно)
        best = max(results, key=lambda x: len(x.get('text', '')))

        return {
            'success': True,
            'text': best['text'],
            'engine': best.get('engine', 'unknown'),
            'strategy': best.get('psm', best.get('paragraphs', 'default')),
            'all_results': [
                {'engine': r.get('engine'), 'psm': r.get('psm'), 
                 'length': len(r.get('text', '')), 'text_preview': r.get('text', '')[:50]}
                for r in results
            ],
            'debug_saved': save_debug
        }


# ============= API ENDPOINTS =============

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/api/health')
def health():
    tesseract_ok = False
    try:
        pytesseract.get_tesseract_version()
        tesseract_ok = True
    except:
        pass

    return jsonify({
        'status': 'ok',
        'version': '3.1.0-enhanced',
        'time': datetime.now().isoformat(),
        'engines': {
            'tesseract': tesseract_ok,
            'easyocr': EASYOCR_AVAILABLE
        }
    })

@app.route('/api/recognize', methods=['POST'])
def recognize():
    """
    Улучшенное API распознавания.
    Параметры:
    - image: base64 изображение
    - lang: язык (rus, eng, rus+eng)
    - preprocess: bool — включить предобработку
    - small_text: bool — усиленная обработка для мелкого текста
    - save_debug: bool — сохранить отладочные изображения
    """
    try:
        data = request.json
        image_data = data.get('image')
        lang = data.get('lang', 'rus')
        preprocess = data.get('preprocess', True)
        small_text = data.get('small_text', False)
        save_debug = data.get('save_debug', False)

        if not image_data:
            return jsonify({'success': False, 'error': 'Изображение не предоставлено'}), 400

        # Декодируем base64
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Сохраняем оригинал для отладки
        if save_debug:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            image.save(f'{DEBUG_FOLDER}/{timestamp}_original.jpg')

        # Распознаём мультистратегией
        result = OCRProcessor.recognize_multi_strategy(
            image, lang=lang, small_text=small_text, save_debug=save_debug
        )

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/debug-images', methods=['GET'])
def list_debug_images():
    """Возвращает список отладочных изображений для анализа."""
    try:
        files = sorted(os.listdir(DEBUG_FOLDER))
        return jsonify({
            'success': True,
            'folder': DEBUG_FOLDER,
            'files': files,
            'count': len(files)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 Крупно v3.1 — Улучшенное OCR")
    print("="*70)
    print("\n📋 Доступные движки:")

    # Проверяем Tesseract
    try:
        ver = pytesseract.get_tesseract_version()
        print(f"   ✅ Tesseract: {ver}")
        langs = pytesseract.get_languages()
        print(f"   🌐 Языки: {', '.join(langs)}")
    except Exception as e:
        print(f"   ❌ Tesseract: {e}")
        print("   💡 Укажи путь: pytesseract.pytesseract.tesseract_cmd = r'...'")

    # Проверяем EasyOCR
    if EASYOCR_AVAILABLE:
        print(f"   ✅ EasyOCR: доступен")
    else:
        print(f"   ⚠️ EasyOCR: не установлен (pip install easyocr)")

    print("\n🌐 Сервер: http://localhost:5000")
    print("📊 Отладка: http://localhost:5000/api/debug-images")
    print("="*70 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
