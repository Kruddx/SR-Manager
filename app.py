import os
import sys
import base64
import json
from datetime import datetime

# Добавляем текущую директорию в путь Python
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify  # добавили jsonify



from discord_auth import get_discord_login_url, exchange_code_for_token, get_discord_user, get_or_create_user
from models import db, User



load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sr_manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Импортируем db и инициализируем ПЕРЕД моделями
from models import db
db.init_app(app)


# Теперь импортируем ВСЕ модели
from models import User, Raid, Reserve  # добавили Raid и Reserve

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


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            # Получаем данные из формы
            encrypted_data = request.form.get('encrypted_data')
            date_str = request.form.get('date')

            # Декодируем base64 и парсим JSON
            json_data = json.loads(base64.b64decode(encrypted_data).decode('utf-8'))

            # Извлекаем instances из JSON
            instances = json_data.get('instances', 'unknown')

            # Создаем запись в таблице Raid
            raid = Raid(
                user_id=session['user_id'],
                encrypted_data=encrypted_data,
                date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                instances=instances
            )
            db.session.add(raid)
            db.session.commit()

            # Обрабатываем данные для таблицы Reserves
            process_raid_data(raid, json_data)

            return redirect(url_for('dashboard'))

        except Exception as e:
            return f"Ошибка при обработке данных: {str(e)}", 400

    return render_template('upload.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    raids = Raid.query.filter_by(user_id=user.id).order_by(Raid.date.desc()).all()

    return render_template('dashboard.html', user=user, raids=raids)


@app.route('/raid/<int:raid_id>/delete', methods=['POST'])
def delete_raid(raid_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    raid = Raid.query.filter_by(id=raid_id, user_id=session['user_id']).first()
    if raid:
        # Удаляем связанные записи в Reserves
        Reserve.query.filter_by(raid_id=raid_id).delete()
        db.session.delete(raid)
        db.session.commit()
        return jsonify({'success': True})

    return jsonify({'error': 'Raid не найден'}), 404


def process_raid_data(raid, json_data):
    # TODO: Реализовать логику преобразования JSON в записи Reserves
    # Это сложная часть - нужно уточнить структуру вашего JSON
    print(f"Обрабатываем данные для raid {raid.id}")
    print(f"JSON данные: {json_data}")

    # Заглушка - нужно реализовать реальную логику
    # based on your JSON structure
    pass


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)


