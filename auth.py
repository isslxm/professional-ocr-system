from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from models import db, User

auth = Blueprint('auth', __name__, url_prefix='/api/auth')
bcrypt = Bcrypt()


@auth.route('/register', methods=['POST'])
def register():
    """
    POST /api/auth/register
    Body: { "username": "...", "email": "...", "password": "..." }
    """
    data = request.json or {}
    username = data.get('username', '').strip()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    # Валидация
    if not username or not email or not password:
        return jsonify({'success': False, 'error': 'Заполни все поля'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Пароль минимум 6 символов'}), 400

    # Проверка уникальности
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'Email уже занят'}), 409
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': 'Имя пользователя занято'}), 409

    # Создаём пользователя
    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(username=username, email=email, password=hashed)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    return jsonify({
        'success': True,
        'message': 'Аккаунт создан',
        'user': {'id': user.id, 'username': user.username, 'email': user.email}
    }), 201


@auth.route('/login', methods=['POST'])
def login():
    """
    POST /api/auth/login
    Body: { "email": "...", "password": "..." }
    """
    data     = request.json or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({'success': False, 'error': 'Неверный email или пароль'}), 401

    login_user(user, remember=True)
    return jsonify({
        'success': True,
        'user': {'id': user.id, 'username': user.username, 'email': user.email}
    })


@auth.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True, 'message': 'Вышел из аккаунта'})


@auth.route('/me', methods=['GET'])
def me():
    """Проверка — кто сейчас залогинен."""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'email': current_user.email
            }
        })
    return jsonify({'authenticated': False})
