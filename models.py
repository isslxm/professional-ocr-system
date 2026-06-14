from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Связь: один пользователь → много записей истории
    history = db.relationship('ScanHistory', backref='user', lazy=True,
                              cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'


class ScanHistory(db.Model):
    __tablename__ = 'scan_history'

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    extracted_text  = db.Column(db.Text)
    language        = db.Column(db.String(20))   # 'rus', 'eng', 'rus+eng'
    engine          = db.Column(db.String(20))   # 'tesseract', 'easyocr'
    source          = db.Column(db.String(20))   # 'upload', 'camera'
    char_count      = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ScanHistory user={self.user_id} chars={self.char_count}>'
