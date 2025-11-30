from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(100), unique=True, nullable=False)
    discord_username = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    raids = db.relationship('Raid', backref='user', lazy=True)


class Raid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    encrypted_data = db.Column(db.Text, nullable=False)
    date = db.Column(db.Date, nullable=False)
    instances = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reserves = db.relationship('Reserve', backref='raid', lazy=True)


class Reserve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    raid_id = db.Column(db.Integer, db.ForeignKey('raid.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    items = db.Column(db.Text, nullable=False)
    quality = db.Column(db.Integer)
    sr_plus = db.Column(db.Integer)
    item_id = db.Column(db.Integer)
    date = db.Column(db.Date, nullable=False)
    key = db.Column(db.String(300), nullable=False)