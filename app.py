from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from models import db, User, Raid, Reserve
from discord_auth import get_discord_login_url, exchange_code_for_token, get_discord_user, get_or_create_user
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sr_manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template('index.html', logged_in=False)

    user = User.query.get(session['user_id'])
    return render_template('index.html', logged_in=True, user=user)


@app.route('/login')
def login():
    return redirect(get_discord_login_url())


@app.route('/discord-callback')
def discord_callback():
    code = request.args.get('code')
    token_data = exchange_code_for_token(code)

    if 'access_token' in token_data:
        discord_user = get_discord_user(token_data['access_token'])
        user = get_or_create_user(discord_user)

        session['user_id'] = user.id
        return redirect(url_for('index'))

    return "Ошибка авторизации", 400


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


# Создаем таблицы при запуске
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)