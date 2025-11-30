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

            if not encrypted_data or not date_str:
                return "Ошибка: заполните все поля", 400

            # Декодируем base64 и парсим JSON
            json_data = json.loads(base64.b64decode(encrypted_data).decode('utf-8'))

            # Валидируем JSON
            is_valid, validation_msg = validate_input_json(json_data)
            if not is_valid:
                return f"Ошибка валидации JSON: {validation_msg}", 400

            # Извлекаем instances из JSON
            instances_list = json_data.get('metadata', {}).get('instances', [])
            instances = instances_list[0] if instances_list else 'unknown'

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


@app.route('/generate')
def generate_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('generate.html')


@app.route('/api/instances')
def get_instances():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    user = User.query.get(session['user_id'])

    # Получаем уникальные instances пользователя
    instances = db.session.query(Raid.instances).filter_by(user_id=user.id).distinct().all()
    instances = [instance[0] for instance in instances if instance[0]]

    return jsonify({'instances': instances})

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


def validate_input_json(json_data):
    """
    Валидация структуры входного JSON
    """
    try:
        # Проверяем обязательные поля
        if 'metadata' not in json_data:
            return False, "Отсутствует metadata"

        if 'softreserves' not in json_data:
            return False, "Отсутствует softreserves"

        # Проверяем структуру softreserves
        for i, player in enumerate(json_data['softreserves']):
            if 'name' not in player:
                return False, f"Отсутствует name у игрока #{i}"
            if 'items' not in player:
                return False, f"Отсутствует items у игрока {player.get('name', 'unknown')}"

        return True, "OK"
    except Exception as e:
        return False, f"Ошибка валидации: {str(e)}"

def process_raid_data(raid, json_data):
    """
    Преобразуем JSON данные в записи таблицы Reserves
    """
    try:
        # Получаем instances из metadata
        instances_list = json_data.get('metadata', {}).get('instences', [])
        instances = instances_list[0] if instances_list else 'unknown'

        # Обрабатываем softreserves
        softreserves = json_data.get('softreserves', [])

        for player in softreserves:
            name = player.get('name', '')
            items = player.get('items', [])

            for item in items:
                item_id = item.get('id', 0)
                quality = item.get('quality', 0)

                # Создаем ключ на основе name и item_id
                key = f"{name}_{item_id}"

                # Создаем запись в таблице Reserves
                reserve = Reserve(
                    raid_id=raid.id,
                    name=name,
                    items=str(item_id),  # сохраняем как строку
                    quality=quality,
                    sr_plus=1,  # по умолчанию 1, будет пересчитываться при генерации
                    item_id=item_id,
                    date=raid.date,
                    key=key
                )
                db.session.add(reserve)

        # Обновляем instances в raid на основе metadata
        if instances != 'unknown':
            raid.instances = instances
            db.session.add(raid)

        db.session.commit()
        print(f"✅ Обработано {len(softreserves)} игроков для raid {raid.id}")

    except Exception as e:
        print(f"❌ Ошибка обработки данных: {e}")
        db.session.rollback()
        raise


@app.route('/generate/<instances>')
def generate_json(instances):
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    try:
        user = User.query.get(session['user_id'])

        # Находим все рейды с указанным instances
        raids = Raid.query.filter_by(user_id=user.id, instances=instances).order_by(Raid.date.desc()).all()

        if not raids:
            return jsonify({'error': f'Не найдено рейдов с instances: {instances}'}), 404

        # Берем самый последний рейд (первый в отсортированном списке)
        latest_raid = raids[0]

        # Получаем reserves только из последнего рейда
        latest_reserves = Reserve.query.filter_by(raid_id=latest_raid.id).all()

        # Собираем ВСЕ reserves для этих instances (для подсчета sr_plus)
        all_reserves = []
        for raid in raids:
            reserves = Reserve.query.filter_by(raid_id=raid.id).all()
            all_reserves.extend(reserves)

        # Группируем ВСЕ данные по имени игрока и item_id для подсчета sr_plus
        player_items_count = {}

        for reserve in all_reserves:
            name = reserve.name
            item_id = reserve.item_id

            if name not in player_items_count:
                player_items_count[name] = {}

            player_items_count[name][item_id] = player_items_count[name].get(item_id, 0) + 1

        # Формируем выходную структуру на основе ПОСЛЕДНЕГО рейда
        softreserves_output = []

        # Группируем reserves последнего рейда по игрокам
        latest_player_items = {}
        for reserve in latest_reserves:
            name = reserve.name
            if name not in latest_player_items:
                latest_player_items[name] = []

            latest_player_items[name].append({
                'id': reserve.item_id,
                'quality': reserve.quality
            })

        # Формируем финальный вывод
        for name, items in latest_player_items.items():
            items_list = []

            for item in items:
                item_id = item['id']
                quality = item['quality']

                # Берем sr_plus из общего подсчета по всем рейдам
                sr_plus = player_items_count.get(name, {}).get(item_id, 1)

                item_obj = {
                    'id': item_id,
                    'quality': quality
                }

                # Добавляем sr_plus только если больше 1
                if sr_plus > 1:
                    item_obj['sr_plus'] = sr_plus

                items_list.append(item_obj)

            softreserves_output.append({
                'name': name,
                'items': items_list
            })

        # Формируем финальный JSON
        output_data = {
            'softreserves': softreserves_output
        }

        # Кодируем в base64
        json_string = json.dumps(output_data, ensure_ascii=False, separators=(',', ':'))
        encoded_output = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')

        return jsonify({
            'success': True,
            'encoded_data': encoded_output,
            'instances': instances,
            'total_players': len(softreserves_output),
            'latest_raid_date': latest_raid.date.isoformat(),
            'total_raids_used': len(raids)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/debug/reserves')
def debug_reserves():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    reserves = Reserve.query.join(Raid).filter(Raid.user_id == user.id).all()

    debug_info = []
    for reserve in reserves:
        debug_info.append({
            'id': reserve.id,
            'name': reserve.name,
            'item_id': reserve.item_id,
            'quality': reserve.quality,
            'raid_date': reserve.raid.date,
            'instances': reserve.raid.instances
        })

    return jsonify(debug_info)


@app.route('/debug/player-stats/<instances>')
def debug_player_stats(instances):
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    user = User.query.get(session['user_id'])

    # Находим все рейды с указанным instances
    raids = Raid.query.filter_by(user_id=user.id, instances=instances).order_by(Raid.date.desc()).all()

    if not raids:
        return jsonify({'error': 'Рейды не найдены'}), 404

    latest_raid = raids[0]
    all_reserves = []

    for raid in raids:
        reserves = Reserve.query.filter_by(raid_id=raid.id).all()
        for reserve in reserves:
            all_reserves.append({
                'raid_date': raid.date.isoformat(),
                'player': reserve.name,
                'item_id': reserve.item_id,
                'quality': reserve.quality
            })

    latest_reserves = Reserve.query.filter_by(raid_id=latest_raid.id).all()

    return jsonify({
        'latest_raid_date': latest_raid.date.isoformat(),
        'total_raids': len(raids),
        'all_reserves': all_reserves,
        'latest_raid_reserves': [
            {
                'player': r.name,
                'item_id': r.item_id,
                'quality': r.quality
            } for r in latest_reserves
        ]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)


