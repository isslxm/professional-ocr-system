from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from flask import send_from_directory
import pytesseract
from PIL import Image
import cv2
import numpy as np
import io
import base64
from deep_translator import GoogleTranslator
from gtts import gTTS
import os
from datetime import datetime
import uuid
import json

app = Flask(__name__)
CORS(app)

# Конфигурация
UPLOAD_FOLDER = 'uploads'
AUDIO_FOLDER = 'audio_output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# История распознавания
recognition_history = []

class OCRProcessor:
    """Класс для обработки OCR"""
    
    @staticmethod
    def preprocess_image(image):
        """Предобработка изображения для улучшения OCR"""
        try:
            # Конвертируем PIL в numpy array
            img_array = np.array(image)
            
            # Конвертируем в оттенки серого
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # CLAHE для улучшения контраста
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # Гауссово размытие для удаления шума
            blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
            
            # Адаптивная бинаризация
            thresh = cv2.adaptiveThreshold(
                blurred,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,
                2
            )
            
            # Морфологические операции
            kernel = np.ones((2, 2), np.uint8)
            processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            processed = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)
            
            return Image.fromarray(processed)
        except Exception as e:
            print(f"Ошибка предобработки: {e}")
            return image
    
    @staticmethod
    def recognize_text(image, lang='eng', preprocess=True):
        """Распознавание текста с изображения"""
        try:
            if preprocess:
                image = OCRProcessor.preprocess_image(image)
            
            # Конфигурация Tesseract
            custom_config = r'--oem 3 --psm 6'
            
            # Распознавание
            text = pytesseract.image_to_string(
                image,
                lang=lang,
                config=custom_config
            )
            
            return {
                'success': True,
                'text': text.strip(),
                'confidence': 0.95  # Tesseract не всегда предоставляет confidence
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

class TranslationService:
    """Сервис перевода текста"""
    
    SUPPORTED_LANGUAGES = {
        'ru': 'Русский',
        'en': 'English',
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch',
        'zh-CN': '中文',
        'ja': '日本語',
        'ko': '한국어',
        'ar': 'العربية',
        'hi': 'हिन्दी'
    }
    
    @staticmethod
    def translate(text, source='auto', target='en'):
        """Перевод текста"""
        try:
            if not text or not text.strip():
                return {
                    'success': False,
                    'error': 'Пустой текст'
                }
            
            translator = GoogleTranslator(source=source, target=target)
            translated = translator.translate(text)
            
            return {
                'success': True,
                'translated_text': translated,
                'source_lang': source,
                'target_lang': target
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

class TTSService:
    """Сервис озвучивания текста"""
    
    @staticmethod
    def text_to_speech_gtts(text, lang='en', filename=None):
        """Озвучка текста через Google TTS (бесплатно)"""
        try:
            if not filename:
                filename = f"{uuid.uuid4()}.mp3"
            
            filepath = os.path.join(AUDIO_FOLDER, filename)
            
            # Создаём аудио
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(filepath)
            
            return {
                'success': True,
                'filename': filename,
                'filepath': filepath
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def text_to_speech_elevenlabs(text, voice_id='21m00Tcm4TlvDq8ikWAM', api_key=None):
        """
        Озвучка через ElevenLabs API (платно, но качественнее)
        Требует API ключ: https://elevenlabs.io/
        """
        if not api_key:
            return {
                'success': False,
                'error': 'ElevenLabs API key не указан'
            }
        
        try:
            import requests
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
            
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                filename = f"{uuid.uuid4()}_elevenlabs.mp3"
                filepath = os.path.join(AUDIO_FOLDER, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                return {
                    'success': True,
                    'filename': filename,
                    'filepath': filepath,
                    'provider': 'elevenlabs'
                }
            else:
                return {
                    'success': False,
                    'error': f'ElevenLabs API error: {response.status_code}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

# ============= API ENDPOINTS =============

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работоспособности"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'ocr': True,
            'translation': True,
            'tts': True
        }
    })

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """Получить список доступных языков"""
    return jsonify({
        'success': True,
        'languages': TranslationService.SUPPORTED_LANGUAGES
    })

@app.route('/api/recognize', methods=['POST'])
def recognize():
    """API для распознавания текста"""
    try:
        data = request.json
        
        # Получаем параметры
        image_data = data.get('image')
        lang = data.get('lang', 'eng')
        preprocess = data.get('preprocess', True)
        
        if not image_data:
            return jsonify({
                'success': False,
                'error': 'Изображение не предоставлено'
            }), 400
        
        # Декодируем base64
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Распознавание
        result = OCRProcessor.recognize_text(image, lang, preprocess)
        
        if result['success']:
            # Сохраняем в историю
            record = {
                'id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat(),
                'text': result['text'],
                'lang': lang,
                'confidence': result.get('confidence', 0)
            }
            recognition_history.append(record)
            
            return jsonify({
                'success': True,
                'text': result['text'],
                'confidence': result['confidence'],
                'record_id': record['id']
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/translate', methods=['POST'])
def translate():
    """API для перевода текста"""
    try:
        data = request.json
        
        text = data.get('text')
        source = data.get('source', 'auto')
        target = data.get('target', 'en')
        
        if not text:
            return jsonify({
                'success': False,
                'error': 'Текст не предоставлен'
            }), 400
        
        result = TranslationService.translate(text, source, target)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/speak', methods=['POST'])
def speak():
    """API для озвучивания текста"""
    try:
        data = request.json
        
        text = data.get('text')
        lang = data.get('lang', 'en')
        provider = data.get('provider', 'gtts')  # 'gtts' или 'elevenlabs'
        
        if not text:
            return jsonify({
                'success': False,
                'error': 'Текст не предоставлен'
            }), 400
        
        # Выбираем провайдер
        if provider == 'elevenlabs':
            api_key = data.get('elevenlabs_api_key')
            result = TTSService.text_to_speech_elevenlabs(text, api_key=api_key)
        else:
            result = TTSService.text_to_speech_gtts(text, lang)
        
        if result['success']:
            return jsonify({
                'success': True,
                'audio_url': f"/api/audio/{result['filename']}",
                'filename': result['filename']
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/audio/<filename>', methods=['GET'])
def get_audio(filename):
    """Получить аудио файл"""
    try:
        filepath = os.path.join(AUDIO_FOLDER, filename)
        
        if os.path.exists(filepath):
            return send_file(filepath, mimetype='audio/mpeg')
        else:
            return jsonify({
                'success': False,
                'error': 'Файл не найден'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """Получить историю распознавания"""
    return jsonify({
        'success': True,
        'history': recognition_history[-10:]  # Последние 10 записей
    })

@app.route('/api/process', methods=['POST'])
def process_all():
    """
    Комплексная обработка: OCR + Перевод + Озвучка
    Всё в одном запросе для удобства
    """
    try:
        data = request.json
        
        # Параметры
        image_data = data.get('image')
        ocr_lang = data.get('ocr_lang', 'eng')
        translate_to = data.get('translate_to')
        speak = data.get('speak', False)
        speak_lang = data.get('speak_lang', 'en')
        
        if not image_data:
            return jsonify({
                'success': False,
                'error': 'Изображение не предоставлено'
            }), 400
        
        # 1. OCR
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        ocr_result = OCRProcessor.recognize_text(image, ocr_lang)
        
        if not ocr_result['success']:
            return jsonify(ocr_result), 500
        
        response = {
            'success': True,
            'ocr': {
                'text': ocr_result['text'],
                'lang': ocr_lang
            }
        }
        
        # 2. Перевод (если указан)
        if translate_to:
            trans_result = TranslationService.translate(
                ocr_result['text'],
                source='auto',
                target=translate_to
            )
            
            if trans_result['success']:
                response['translation'] = {
                    'text': trans_result['translated_text'],
                    'target_lang': translate_to
                }
        
        # 3. Озвучка (если указано)
        if speak:
            text_to_speak = response.get('translation', {}).get('text', ocr_result['text'])
            
            tts_result = TTSService.text_to_speech_gtts(text_to_speak, speak_lang)
            
            if tts_result['success']:
                response['audio'] = {
                    'url': f"/api/audio/{tts_result['filename']}",
                    'filename': tts_result['filename']
                }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
 
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# @app.route('/test-pwa')
# def test_pwa():
#     return render_template('test_pwa.html')

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 Professional OCR System - Backend Server")
    print("="*70)
    print("\n📋 Доступные функции:")
    print("  ✓ OCR (распознавание текста)")
    print("  ✓ Translation (перевод на 10+ языков)")
    print("  ✓ Text-to-Speech (озвучка Google TTS)")
    print("  ✓ ElevenLabs TTS (опционально)")
    print("\n🌐 API Endpoints:")
    print("  • GET  /api/health - проверка статуса")
    print("  • GET  /api/languages - список языков")
    print("  • POST /api/recognize - OCR")
    print("  • POST /api/translate - перевод")
    print("  • POST /api/speak - озвучка")
    print("  • POST /api/process - всё в одном")
    print("  • GET  /api/history - история")
    print("\n📱 Для доступа с телефона:")
    print("  1. Узнай IP: ip addr show")
    print("  2. Открой: http://IP:5000")
    print("\n" + "="*70 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)