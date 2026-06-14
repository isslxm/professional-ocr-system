import os
import io
import base64
import tempfile
import numpy as np
import cv2
import pytesseract
from datetime import datetime
from dotenv import load_dotenv

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
from PIL import Image

from models import db, User, ScanHistory
from auth import auth, bcrypt

# ─────────────────────────────────────────────
# Загрузка переменных окружения из .env
# ─────────────────────────────────────────────
load_dotenv()

# ─────────────────────────────────────────────
# Создание приложения
# ─────────────────────────────────────────────
app = Flask(__name__, template_folder='.', static_folder='static')
CORS(app, supports_credentials=True)   # supports_credentials нужен для сессий

# ─────────────────────────────────────────────
# Конфигурация
# ─────────────────────────────────────────────
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '230c4c1e41319d0d4532006a42e630ef8a14057d848874186d9ceb249303b7c5')

# Исправление URL для Railway (postgres:// → postgresql://)
database_url = os.getenv('DATABASE_URL', '')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ─────────────────────────────────────────────
# Инициализация расширений
# ─────────────────────────────────────────────
db.init_app(app)
bcrypt.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401

# Регистрация blueprint авторизации (/api/auth/*)
app.register_blueprint(auth)

# ─────────────────────────────────────────────
# Создание папок и таблиц БД
# ─────────────────────────────────────────────
UPLOAD_FOLDER = 'uploads'
DEBUG_FOLDER  = 'debug'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DEBUG_FOLDER,  exist_ok=True)

with app.app_context():
    db.create_all()
    print("✅ Таблицы БД созданы/проверены")

# ─────────────────────────────────────────────
# Путь к Tesseract (локально — Windows)
# На Railway это не нужно, там tesseract в PATH
# ─────────────────────────────────────────────
TESSERACT_LOCAL = r'C:\Users\Islam Osmonov\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
if os.path.exists(TESSERACT_LOCAL):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_LOCAL

# ─────────────────────────────────────────────
# EasyOCR (опционально)
# ─────────────────────────────────────────────
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    print("✅ EasyOCR загружен")
except ImportError:
    EASYOCR_AVAILABLE = False
    print("⚠️ EasyOCR не установлен. pip install easyocr")

_easyocr_reader = None

def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        print("🔄 Инициализация EasyOCR (~1-2 мин)...")
        _easyocr_reader = easyocr.Reader(['ru', 'en'], gpu=False)
        print("✅ EasyOCR готов")
    return _easyocr_reader


# ═══════════════════════════════════════════════
# OCR ПРОЦЕССОР (без изменений — твой оригинал)
# ═══════════════════════════════════════════════

class OCRProcessor:

    @staticmethod
    def preprocess_for_small_text(image, save_debug=False):
        try:
            img_array = np.array(image)
            original  = img_array.copy()

            if len(img_array.shape) == 2:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
            elif img_array.shape[2] == 4:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)

            height, width = img_array.shape[:2]
            scale = 2.5
            upscaled = cv2.resize(img_array, (int(width * scale), int(height * scale)),
                                  interpolation=cv2.INTER_CUBIC)

            lab = cv2.cvtColor(upscaled, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
            l_enhanced  = clahe.apply(l)
            lab_enhanced = cv2.merge([l_enhanced, a, b])
            enhanced_color = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)

            gray     = cv2.cvtColor(enhanced_color, cv2.COLOR_RGB2GRAY)
            denoised = cv2.fastNlMeansDenoising(gray, None, h=15, templateWindowSize=7, searchWindowSize=21)

            gaussian   = cv2.GaussianBlur(denoised, (0, 0), 3)
            sharpened  = cv2.addWeighted(denoised, 1.8, gaussian, -0.8, 0)
            kernel_sh  = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened2 = cv2.filter2D(sharpened, -1, kernel_sh)

            binary = cv2.adaptiveThreshold(
                sharpened2, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 15, 12
            )

            if save_debug:
                for name, img in {
                    '01_original': original, '02_upscaled': upscaled,
                    '03_gray': gray, '04_denoised': denoised,
                    '05_sharpened': sharpened2, '06_binary': binary
                }.items():
                    if len(img.shape) == 2:
                        cv2.imwrite(f'{DEBUG_FOLDER}/{name}.jpg', img)
                    else:
                        cv2.imwrite(f'{DEBUG_FOLDER}/{name}.jpg', cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

        except Exception as e:
            print(f"❌ Ошибка предобработки: {e}")
            return image

    @staticmethod
    def preprocess_standard(image):
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
            clahe     = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced  = clahe.apply(gray)
            blurred   = cv2.GaussianBlur(enhanced, (3, 3), 0)
            thresh    = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            kernel    = np.ones((2, 2), np.uint8)
            processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            return Image.fromarray(processed)
        except Exception as e:
            print(f"❌ Ошибка стандартной предобработки: {e}")
            return image

    @staticmethod
    def preprocess_for_dark_background(image):
        try:
            img_array = np.array(image)
            gray      = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
            inverted  = cv2.bitwise_not(gray)
            h, w      = gray.shape
            upscaled  = cv2.resize(inverted, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
            clahe     = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced  = clahe.apply(upscaled)
            return Image.fromarray(enhanced)
        except Exception as e:
            print(f"❌ Ошибка инвертированной предобработки: {e}")
            return image

    @staticmethod
    def recognize_tesseract(image, lang='rus', config=None, psm=6):
        try:
            if config is None:
                config = r'--oem 3 --psm {}'.format(psm)
            text    = pytesseract.image_to_string(image, lang=lang, config=config)
            lines   = [line.strip() for line in text.split('\n') if line.strip()]
            cleaned = '\n'.join(lines)
            return {'success': True, 'text': cleaned, 'engine': 'tesseract',
                    'psm': psm, 'raw_length': len(text), 'cleaned_length': len(cleaned)}
        except Exception as e:
            return {'success': False, 'error': str(e), 'engine': 'tesseract'}

    @staticmethod
    def recognize_easyocr(image_np):
        try:
            if not EASYOCR_AVAILABLE:
                return {'success': False, 'error': 'EasyOCR не установлен', 'engine': 'easyocr'}
            reader  = get_easyocr_reader()
            results = reader.readtext(image_np, detail=0, paragraph=True,
                                      contrast_ths=0.1, adjust_contrast=0.5)
            text = '\n'.join(results) if results else ''
            return {'success': True, 'text': text, 'engine': 'easyocr', 'paragraphs': len(results)}
        except Exception as e:
            return {'success': False, 'error': str(e), 'engine': 'easyocr'}

    @staticmethod
    def recognize_multi_strategy(image, lang='rus', small_text=False, save_debug=False):
        results = []

        if small_text:
            processed = OCRProcessor.preprocess_for_small_text(image, save_debug=save_debug)
            for psm in [6, 3, 4, 11]:
                res = OCRProcessor.recognize_tesseract(processed, lang=lang, psm=psm)
                if res['success'] and len(res['text']) > 3:
                    results.append(res)
                    if len(res['text']) > 20:
                        break

        if not results or all(len(r['text']) < 5 for r in results):
            processed = OCRProcessor.preprocess_standard(image)
            for psm in [6, 3, 11]:
                res = OCRProcessor.recognize_tesseract(processed, lang=lang, psm=psm)
                if res['success'] and len(res['text']) > 3:
                    results.append(res)

        if not results or all(len(r['text']) < 5 for r in results):
            res = OCRProcessor.recognize_tesseract(image, lang=lang, psm=3)
            if res['success'] and len(res['text']) > 3:
                results.append(res)

        if not results or all(len(r['text']) < 5 for r in results):
            processed = OCRProcessor.preprocess_for_dark_background(image)
            res = OCRProcessor.recognize_tesseract(processed, lang=lang, psm=6)
            if res['success'] and len(res['text']) > 3:
                results.append({**res, 'inverted': True})

        if EASYOCR_AVAILABLE and (not results or all(len(r['text']) < 10 for r in results)):
            np_image = np.array(image)
            res = OCRProcessor.recognize_easyocr(np_image)
            if res['success'] and len(res['text']) > 3:
                results.append(res)

        if not results:
            return {'success': False, 'text': '', 'error': 'Текст не распознан', 'attempts': 0}

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


# ═══════════════════════════════════════════════
# РОУТЫ — Статика
# ═══════════════════════════════════════════════

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


# ═══════════════════════════════════════════════
# РОУТЫ — OCR API
# ═══════════════════════════════════════════════

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
        'version': '4.0.0-auth',
        'time': datetime.now().isoformat(),
        'engines': {'tesseract': tesseract_ok, 'easyocr': EASYOCR_AVAILABLE}
    })


@app.route('/api/recognize', methods=['POST'])
@login_required   # ← теперь только для авторизованных
def recognize():
    """
    POST /api/recognize
    Body: {
      "image": "<base64>",
      "lang": "rus",
      "preprocess": true,
      "small_text": false,
      "save_debug": false,
      "source": "upload"   ← "upload" или "camera"
    }
    """
    try:
        data       = request.json
        image_data = data.get('image')
        lang       = data.get('lang', 'rus')
        small_text = data.get('small_text', False)
        save_debug = data.get('save_debug', False)
        source     = data.get('source', 'upload')

        if not image_data:
            return jsonify({'success': False, 'error': 'Изображение не предоставлено'}), 400

        # Декодируем base64
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        if save_debug:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            image.save(f'{DEBUG_FOLDER}/{ts}_original.jpg')

        # Распознаём
        result = OCRProcessor.recognize_multi_strategy(
            image, lang=lang, small_text=small_text, save_debug=save_debug
        )

        # ✅ Сохраняем в историю если успешно
        if result['success'] and result['text']:
            record = ScanHistory(
                user_id        = current_user.id,
                extracted_text = result['text'],
                language       = lang,
                engine         = result.get('engine', 'unknown'),
                source         = source,
                char_count     = len(result['text'])
            )
            db.session.add(record)
            db.session.commit()
            result['history_id'] = record.id

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════
# РОУТЫ — История
# ═══════════════════════════════════════════════

@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    """
    GET /api/history?page=1&per_page=20
    Возвращает историю сканирований текущего пользователя.
    """
    page     = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = (
        ScanHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(ScanHistory.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    items = [
        {
            'id':             r.id,
            'extracted_text': r.extracted_text,
            'language':       r.language,
            'engine':         r.engine,
            'source':         r.source,
            'char_count':     r.char_count,
            'created_at':     r.created_at.isoformat()
        }
        for r in pagination.items
    ]

    return jsonify({
        'success':  True,
        'items':    items,
        'total':    pagination.total,
        'pages':    pagination.pages,
        'page':     page,
        'per_page': per_page
    })


@app.route('/api/history/<int:record_id>', methods=['DELETE'])
@login_required
def delete_history_item(record_id):
    """DELETE /api/history/<id> — удалить одну запись истории."""
    record = ScanHistory.query.filter_by(
        id=record_id, user_id=current_user.id
    ).first()

    if not record:
        return jsonify({'success': False, 'error': 'Запись не найдена'}), 404

    db.session.delete(record)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Запись удалена'})


@app.route('/api/history', methods=['DELETE'])
@login_required
def clear_history():
    """DELETE /api/history — очистить всю историю пользователя."""
    ScanHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'История очищена'})


# ═══════════════════════════════════════════════
# РОУТЫ — Отладка
# ═══════════════════════════════════════════════

@app.route('/api/debug-images', methods=['GET'])
def list_debug_images():
    try:
        files = sorted(os.listdir(DEBUG_FOLDER))
        return jsonify({'success': True, 'folder': DEBUG_FOLDER, 'files': files, 'count': len(files)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 OCR System v4.0 — с авторизацией и историей")
    print("="*70)

    try:
        ver = pytesseract.get_tesseract_version()
        print(f"   ✅ Tesseract: {ver}")
    except Exception as e:
        print(f"   ❌ Tesseract: {e}")

    if EASYOCR_AVAILABLE:
        print("   ✅ EasyOCR: доступен")
    else:
        print("   ⚠️ EasyOCR: не установлен")

    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(f"   🗄️  БД: {'✅ настроена' if db_uri else '❌ DATABASE_URL не задан!'}")
    print("\n🌐 Сервер: http://localhost:5000")
    print("="*70 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
