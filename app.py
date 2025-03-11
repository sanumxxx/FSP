# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json
from flask import render_template
from sqlalchemy import desc
from datetime import datetime


# Создаем экземпляр Flask-приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///admin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB макс размер файла

# Убедимся, что папка для загрузок существует
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Инициализация базы данных
db = SQLAlchemy(app)

# Настройка системы аутентификации
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Определение моделей данных

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(20), default='admin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization = db.Column(db.String(200))
    city = db.Column(db.String(100))
    logo = db.Column(db.String(200))  # Path to the logo file
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    members = db.relationship('TeamMember', backref='team', lazy=True, cascade="all, delete-orphan")
    event_participations = db.relationship('EventParticipant', backref='team', lazy=True)

    def __repr__(self):
        return f'<Team {self.name}>'


class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    role = db.Column(db.String(50))  # e.g., "captain", "member"
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('team_id', 'participant_id', name='_team_participant_uc'),
    )

    def __repr__(self):
        return f'<TeamMember {self.participant_id} in Team {self.team_id}>'


class EventParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    place = db.Column(db.Integer, nullable=True)
    score = db.Column(db.Float, default=0)
    rating_change = db.Column(db.Integer, default=0)
    is_team = db.Column(db.Boolean, default=False)  # Flag to indicate if this is a team entry
    published = db.Column(db.Boolean, default=False)  # Flag to control visibility on the public site

    # Add a CheckConstraint to ensure at least one of participant_id or team_id is not null
    __table_args__ = (
        db.CheckConstraint('participant_id IS NOT NULL OR team_id IS NOT NULL',
                           name='_participant_or_team_required'),
    )

    def __repr__(self):
        if self.participant_id:
            return f'<EventParticipant Participant:{self.participant_id} in Event:{self.event_id}>'
        else:
            return f'<EventParticipant Team:{self.team_id} in Event:{self.event_id}>'


# Add this line to the Participant model to establish the relationship
# Find the Participant model and add this line inside the class:
team_memberships = db.relationship('TeamMember', backref='participant', lazy=True)

# Add this line to the Event model to access team participants more easily
# Find the Event model and add this line inside the class:
team_participants = db.relationship('EventParticipant',
                                    primaryjoin="and_(EventParticipant.event_id==Event.id, "
                                                "EventParticipant.team_id!=None)",
                                    backref="event_teams", lazy=True)

class FederationMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    photo = db.Column(db.String(200))
    order = db.Column(db.Integer, default=0)  # для сортировки
    icon = db.Column(db.String(50))  # иконка Font Awesome
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<FederationMember {self.name} - {self.position}>'


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    published = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<News {self.title}>'


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200))
    image = db.Column(db.String(200))
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    registration_link = db.Column(db.String(200))
    published = db.Column(db.Boolean, default=True)
    # New field for discipline
    discipline = db.Column(db.String(50), default='other')  # 'algorithmic', 'product', 'robotics', 'other'
    # New field for organizer
    organizer = db.Column(db.String(200), default='Федерация спортивного программирования ЗО')

    def __repr__(self):
        return f'<Event {self.title}>'


class Statistics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Integer, default=0)
    is_counter = db.Column(db.Boolean, default=True)  # Показывает, нужен ли "+" после значения
    title = db.Column(db.String(100), nullable=False)
    subtitle = db.Column(db.String(100), nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<Statistics {self.key}: {self.value}>'

    @classmethod
    def get_value(cls, key, default=0):
        """Получение значения статистики по ключу"""
        stat = cls.query.filter_by(key=key).first()
        return stat.value if stat else default

    @classmethod
    def update_value(cls, key, value):
        """Обновление значения статистики"""
        stat = cls.query.filter_by(key=key).first()
        if stat:
            stat.value = value
            stat.last_updated = datetime.now()
            db.session.commit()
            return True
        return False


class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100))
    organization = db.Column(db.String(200))
    rating = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50), default='open')  # 'open', 'student', 'school'
    achievements = db.Column(db.Text)

    def __repr__(self):
        return f'<Participant {self.name}>'


class Partner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    logo = db.Column(db.String(200))
    website = db.Column(db.String(200))
    description = db.Column(db.Text)

    def __repr__(self):
        return f'<Partner {self.name}>'


class Gallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    image = db.Column(db.String(200), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Gallery {self.title}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Роуты для аутентификации

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(next_page or url_for('admin_dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')

    return render_template('admin/login.html')

@app.route('/admin/structure')
@login_required
def admin_structure_list():
    """Страница со списком членов федерации"""
    members = FederationMember.query.order_by(FederationMember.order).all()
    return render_template('admin/structure/list.html', members=members)


@app.route('/admin/events/<int:event_id>/participants')
@login_required
def admin_event_participants(event_id):
    """Страница со списком участников мероприятия (индивидуальных и команд)"""
    event = Event.query.get_or_404(event_id)

    # Получаем индивидуальных участников этого мероприятия
    individual_participants = db.session.query(
        EventParticipant,
        Participant.name.label('participant_name'),
        Participant.organization,
        Participant.city
    ).join(
        Participant, EventParticipant.participant_id == Participant.id
    ).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.participant_id != None
    ).all()

    # Преобразуем результаты запроса в список словарей для индивидуальных участников
    individual_data = []
    for p_event, p_name, p_org, p_city in individual_participants:
        individual_data.append({
            'id': p_event.id,
            'participant_id': p_event.participant_id,
            'team_id': None,
            'is_team': False,
            'participant_name': p_name,
            'organization': p_org,
            'city': p_city,
            'place': p_event.place,
            'score': p_event.score,
            'rating_change': p_event.rating_change,
            'published': p_event.published if hasattr(p_event, 'published') else False
        })

    # Получаем команды этого мероприятия
    team_participants = db.session.query(
        EventParticipant,
        Team.name.label('team_name'),
        Team.organization,
        Team.city
    ).join(
        Team, EventParticipant.team_id == Team.id
    ).filter(
        EventParticipant.event_id == event_id,
        EventParticipant.team_id != None
    ).all()

    # Преобразуем результаты запроса в список словарей для команд
    team_data = []
    for p_event, t_name, t_org, t_city in team_participants:
        team_data.append({
            'id': p_event.id,
            'participant_id': None,
            'team_id': p_event.team_id,
            'is_team': True,
            'participant_name': t_name,  # Используем имя команды
            'organization': t_org,
            'city': t_city,
            'place': p_event.place,
            'score': p_event.score,
            'rating_change': p_event.rating_change,
            'published': p_event.published if hasattr(p_event, 'published') else False
        })

    # Объединяем данные для отображения в шаблоне
    participants_data = individual_data + team_data

    # Сортируем по месту (сначала с указанным местом, потом все остальные)
    participants_data.sort(key=lambda x: (x['place'] is None, x['place']))

    # Для выпадающих списков при добавлении новых участников
    all_participants = Participant.query.order_by(Participant.name).all()
    all_teams = Team.query.order_by(Team.name).all()

    # Исключаем уже добавленных индивидуальных участников
    added_participant_ids = [p['participant_id'] for p in individual_data if p['participant_id'] is not None]
    available_participants = [p for p in all_participants if p.id not in added_participant_ids]

    # Исключаем уже добавленные команды
    added_team_ids = [p['team_id'] for p in team_data if p['team_id'] is not None]
    available_teams = [t for t in all_teams if t.id not in added_team_ids]

    return render_template(
        'admin/events/participants.html',
        event=event,
        participants=participants_data,
        all_participants=available_participants,
        all_teams=available_teams
    )


@app.route('/admin/events/<int:event_id>/participants/add', methods=['POST'])
@login_required
def admin_event_add_participant(event_id):
    """Добавление участника или команды к мероприятию"""
    event = Event.query.get_or_404(event_id)

    participant_type = request.form.get('participant_type', 'individual')
    participant_id = request.form.get('participant_id') if participant_type == 'individual' else None
    team_id = request.form.get('team_id') if participant_type == 'team' else None
    place = request.form.get('place')
    score = request.form.get('score', 0)
    rating_change = request.form.get('rating_change', 0)

    # Проверяем, что участник или команда еще не добавлены к мероприятию
    if participant_type == 'individual':
        existing = EventParticipant.query.filter_by(
            event_id=event_id,
            participant_id=participant_id
        ).first()
    else:
        existing = EventParticipant.query.filter_by(
            event_id=event_id,
            team_id=team_id
        ).first()

    if existing:
        if participant_type == 'individual':
            flash('Этот участник уже добавлен к мероприятию', 'danger')
        else:
            flash('Эта команда уже добавлена к мероприятию', 'danger')
    else:
        participant_event = EventParticipant(
            event_id=event_id,
            participant_id=participant_id,
            team_id=team_id,
            is_team=(participant_type == 'team'),
            place=place if place else None,
            score=float(score) if score else 0,
            rating_change=int(rating_change) if rating_change else 0
        )
        db.session.add(participant_event)
        db.session.commit()

        if participant_type == 'individual':
            flash('Участник успешно добавлен к мероприятию', 'success')
        else:
            flash('Команда успешно добавлена к мероприятию', 'success')

    return redirect(url_for('admin_event_participants', event_id=event_id))


# Обновление данных участника мероприятия
@app.route('/admin/events/<int:event_id>/participants/update', methods=['POST'])
@login_required
def admin_event_update_participant(event_id):
    event = Event.query.get_or_404(event_id)

    participant_event_id = request.form.get('id')
    place = request.form.get('place')
    score = request.form.get('score', 0)
    rating_change = request.form.get('rating_change', 0)

    participant_event = EventParticipant.query.get_or_404(participant_event_id)

    if participant_event.event_id != event_id:
        flash('Ошибка: участник не принадлежит этому мероприятию', 'danger')
    else:
        participant_event.place = place if place else None
        participant_event.score = float(score)
        participant_event.rating_change = int(rating_change)
        db.session.commit()
        flash('Данные участника обновлены', 'success')

    return redirect(url_for('admin_event_participants', event_id=event_id))


# Удаление участника из мероприятия
@app.route('/admin/events/<int:event_id>/participants/remove', methods=['POST'])
@login_required
def admin_event_remove_participant(event_id):
    event = Event.query.get_or_404(event_id)

    participant_event_id = request.form.get('id')
    participant_event = EventParticipant.query.get_or_404(participant_event_id)

    if participant_event.event_id != event_id:
        flash('Ошибка: участник не принадлежит этому мероприятию', 'danger')
    else:
        db.session.delete(participant_event)
        db.session.commit()
        flash('Участник удален из мероприятия', 'success')

    return redirect(url_for('admin_event_participants', event_id=event_id))


# Импорт участников из CSV
@app.route('/admin/events/<int:event_id>/participants/import', methods=['POST'])
@login_required
def admin_event_import_participants(event_id):
    event = Event.query.get_or_404(event_id)

    if 'participants_file' not in request.files:
        flash('Не выбран файл для импорта', 'danger')
        return redirect(url_for('admin_event_participants', event_id=event_id))

    file = request.files['participants_file']
    if file.filename == '':
        flash('Не выбран файл для импорта', 'danger')
        return redirect(url_for('admin_event_participants', event_id=event_id))

    create_missing = 'create_missing' in request.form
    overwrite_existing = 'overwrite_existing' in request.form

    # Чтение CSV-файла
    try:
        data = file.read().decode('utf-8')
        lines = data.splitlines()
        reader = csv.reader(lines)

        added_count = 0
        existing_count = 0
        created_count = 0

        for row in reader:
            if len(row) < 3:
                continue

            name = row[0].strip()
            organization = row[1].strip() if len(row) > 1 else ''
            city = row[2].strip() if len(row) > 2 else ''
            place = row[3].strip() if len(row) > 3 else None
            score = row[4].strip() if len(row) > 4 else 0

            # Поиск участника по имени
            participant = Participant.query.filter_by(name=name).first()

            # Создаем участника, если не найден и включена соответствующая опция
            if not participant and create_missing:
                participant = Participant(
                    name=name,
                    organization=organization,
                    city=city
                )
                db.session.add(participant)
                db.session.commit()
                created_count += 1

            if participant:
                # Проверяем, есть ли уже участник в этом мероприятии
                existing = EventParticipant.query.filter_by(
                    event_id=event_id,
                    participant_id=participant.id
                ).first()

                if existing:
                    existing_count += 1
                    if overwrite_existing:
                        existing.place = int(place) if place and place.isdigit() else None
                        existing.score = float(score) if score else 0
                        db.session.commit()
                else:
                    participant_event = EventParticipant(
                        event_id=event_id,
                        participant_id=participant.id,
                        place=int(place) if place and place.isdigit() else None,
                        score=float(score) if score else 0,
                        rating_change=0  # По умолчанию 0, будет рассчитан позже
                    )
                    db.session.add(participant_event)
                    added_count += 1

        db.session.commit()

        flash(
            f'Импорт завершен: добавлено {added_count} участников, обновлено {existing_count}, создано {created_count}',
            'success')
    except Exception as e:
        flash(f'Ошибка при импорте: {str(e)}', 'danger')

    return redirect(url_for('admin_event_participants', event_id=event_id))


# Рассчет рейтинга участников
@app.route('/admin/events/<int:event_id>/calculate-rating', methods=['POST'])
@login_required
def admin_event_calculate_rating(event_id):
    event = Event.query.get_or_404(event_id)

    method = request.form.get('rating_method', 'standard')
    event_weight = int(request.form.get('event_weight', 1))
    first_place_points = int(request.form.get('first_place_points', 100))
    apply_immediately = 'apply_immediately' in request.form

    participants = EventParticipant.query.filter_by(event_id=event_id).all()

    # Сортируем участников по месту или баллам
    if method == 'standard':
        # Сначала идут участники с указанным местом (сортировка по месту),
        # потом все остальные (без указанного места)
        participants_with_place = [p for p in participants if p.place is not None]
        participants_with_place.sort(key=lambda p: p.place)

        participants_without_place = [p for p in participants if p.place is None]

        sorted_participants = participants_with_place + participants_without_place
    else:  # на основе баллов
        participants.sort(key=lambda p: p.score, reverse=True)
        sorted_participants = participants

    # Рассчитываем изменение рейтинга
    for i, participant in enumerate(sorted_participants):
        if method == 'standard' and participant.place is not None:
            # Для участников с указанным местом используем место
            place = participant.place
        else:
            # Для остальных используем позицию в отсортированном списке
            place = i + 1

        # Простая формула для рейтинга: первое место получает максимум очков,
        # остальные - уменьшение на основе места
        if place == 1:
            rating_points = first_place_points
        else:
            # Экспоненциальное уменьшение очков с увеличением места
            rating_points = first_place_points / (place ** 1.5)

        # Учитываем вес мероприятия
        rating_points *= event_weight

        # Округляем до целого
        participant.rating_change = int(rating_points)

    # Применяем изменения, если нужно
    if apply_immediately:
        # Обновляем рейтинг участников
        for participant_event in participants:
            participant = Participant.query.get(participant_event.participant_id)
            if participant:
                participant.rating += participant_event.rating_change

        db.session.commit()
        flash('Рейтинг участников успешно рассчитан и применен', 'success')
    else:
        db.session.commit()  # Сохраняем только расчет, не применяя к общему рейтингу
        flash('Рейтинг участников успешно рассчитан. Изменения сохранены для просмотра.', 'success')

    return redirect(url_for('admin_event_participants', event_id=event_id))


@app.route('/admin/teams')
@login_required
def admin_teams_list():
    """Страница со списком команд"""
    teams = Team.query.order_by(Team.name).all()
    return render_template('admin/teams/list.html', teams=teams)


@app.route('/admin/teams/create', methods=['GET', 'POST'])
@login_required
def admin_teams_create():
    """Страница создания новой команды"""
    if request.method == 'POST':
        name = request.form.get('name')
        organization = request.form.get('organization')
        city = request.form.get('city')
        description = request.form.get('description')
        is_active = True if request.form.get('is_active') else False

        team = Team(
            name=name,
            organization=organization,
            city=city,
            description=description,
            is_active=is_active
        )

        # Обработка загрузки логотипа
        if 'logo' in request.files:
            file = request.files['logo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'teams', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                team.logo = f'uploads/teams/{filename}'

        db.session.add(team)
        db.session.commit()
        flash('Команда успешно создана!', 'success')
        return redirect(url_for('admin_teams_list'))

    return render_template('admin/teams/create.html')


@app.route('/admin/teams/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_teams_edit(id):
    """Страница редактирования команды"""
    team = Team.query.get_or_404(id)

    if request.method == 'POST':
        team.name = request.form.get('name')
        team.organization = request.form.get('organization')
        team.city = request.form.get('city')
        team.description = request.form.get('description')
        team.is_active = True if request.form.get('is_active') else False

        # Обработка загрузки логотипа
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename:
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'teams', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    file.save(filepath)

                    # Удаляем старый логотип
                    if team.logo:
                        old_file = os.path.join(app.root_path, 'static', team.logo)
                        if os.path.exists(old_file):
                            os.remove(old_file)

                    team.logo = f'uploads/teams/{filename}'

        db.session.commit()
        flash('Информация о команде успешно обновлена!', 'success')
        return redirect(url_for('admin_teams_list'))

    return render_template('admin/teams/edit.html', team=team)


@app.route('/admin/teams/delete/<int:id>', methods=['POST'])
@login_required
def admin_teams_delete(id):
    """Удаление команды"""
    team = Team.query.get_or_404(id)

    # Удаляем логотип
    if team.logo:
        file_path = os.path.join(app.root_path, 'static', team.logo)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(team)
    db.session.commit()
    flash('Команда успешно удалена!', 'success')
    return redirect(url_for('admin_teams_list'))


# Team Members Management
@app.route('/admin/teams/<int:team_id>/members')
@login_required
def admin_team_members(team_id):
    """Страница управления участниками команды"""
    team = Team.query.get_or_404(team_id)

    # Получаем всех участников этой команды через связь TeamMember
    members_query = db.session.query(
        TeamMember,
        Participant.name.label('participant_name'),
        Participant.organization,
        Participant.city,
        TeamMember.role
    ).join(
        Participant, TeamMember.participant_id == Participant.id
    ).filter(
        TeamMember.team_id == team_id
    ).all()

    # Преобразуем результаты запроса в список словарей
    members_data = []
    for member, p_name, p_org, p_city, role in members_query:
        members_data.append({
            'id': member.id,
            'participant_id': member.participant_id,
            'participant_name': p_name,
            'organization': p_org,
            'city': p_city,
            'role': role,
            'joined_at': member.joined_at
        })

    # Для выпадающего списка при добавлении новых участников - получаем ВСЕХ участников
    all_participants = Participant.query.order_by(Participant.name).all()

    # Исключаем уже добавленных участников
    added_participant_ids = [m['participant_id'] for m in members_data]

    # Отладочные сообщения - раскомментируйте при необходимости
    print(f"Всего участников в базе: {len(all_participants)}")
    print(f"Участники в этой команде: {added_participant_ids}")

    # Используем list comprehension для создания доступных участников
    available_participants = [p for p in all_participants if p.id not in added_participant_ids]

    # Отладочное сообщение
    print(f"Доступно для добавления: {len(available_participants)}")

    return render_template(
        'admin/teams/members.html',
        team=team,
        members=members_data,
        available_participants=available_participants
    )


@app.route('/admin/teams/<int:team_id>/members/add', methods=['POST'])
@login_required
def admin_team_add_member(team_id):
    """Добавление участника в команду"""
    team = Team.query.get_or_404(team_id)

    participant_id = request.form.get('participant_id')
    role = request.form.get('role', '')

    # Отладка
    print(f"Добавление участника в команду. Team ID: {team_id}, Participant ID: {participant_id}, Role: {role}")

    # Проверка, что participant_id не пусто
    if not participant_id:
        flash('Необходимо выбрать участника', 'danger')
        return redirect(url_for('admin_team_members', team_id=team_id))

    # Убедимся, что участник существует
    participant = Participant.query.get(participant_id)
    if not participant:
        flash('Выбранный участник не найден', 'danger')
        return redirect(url_for('admin_team_members', team_id=team_id))

    # Проверяем, что участник еще не добавлен в команду
    existing = TeamMember.query.filter_by(
        team_id=team_id,
        participant_id=participant_id
    ).first()

    if existing:
        flash('Этот участник уже добавлен в команду', 'danger')
    else:
        # Если устанавливается роль капитана, проверяем, нет ли уже капитана
        if role == 'Капитан':
            current_captain = TeamMember.query.filter_by(
                team_id=team_id,
                role='Капитан'
            ).first()

            if current_captain:
                # Можно либо отклонить запрос, либо обновить текущего капитана
                current_captain.role = 'Участник'  # Понижаем роль текущего капитана
                db.session.flush()  # Фиксируем изменения

        team_member = TeamMember(
            team_id=team_id,
            participant_id=participant_id,
            role=role
        )
        db.session.add(team_member)

        try:
            db.session.commit()
            flash('Участник успешно добавлен в команду', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка добавления участника: {str(e)}")
            flash(f'Ошибка добавления участника: {str(e)}', 'danger')

    return redirect(url_for('admin_team_members', team_id=team_id))


@app.route('/admin/teams/<int:team_id>/members/update', methods=['POST'])
@login_required
def admin_team_update_member(team_id):
    """Обновление роли участника в команде"""
    team = Team.query.get_or_404(team_id)

    member_id = request.form.get('id')
    role = request.form.get('role', '')

    team_member = TeamMember.query.get_or_404(member_id)

    if team_member.team_id != team_id:
        flash('Ошибка: участник не принадлежит этой команде', 'danger')
    else:
        team_member.role = role
        db.session.commit()
        flash('Роль участника обновлена', 'success')

    return redirect(url_for('admin_team_members', team_id=team_id))


@app.route('/admin/teams/<int:team_id>/members/remove', methods=['POST'])
@login_required
def admin_team_remove_member(team_id):
    """Удаление участника из команды"""
    team = Team.query.get_or_404(team_id)

    member_id = request.form.get('id')
    team_member = TeamMember.query.get_or_404(member_id)

    if team_member.team_id != team_id:
        flash('Ошибка: участник не принадлежит этой команде', 'danger')
    else:
        db.session.delete(team_member)
        db.session.commit()
        flash('Участник удален из команды', 'success')

    return redirect(url_for('admin_team_members', team_id=team_id))



# Сброс результатов мероприятия
@app.route('/admin/events/<int:event_id>/clear-results', methods=['POST'])
@login_required
def admin_event_clear_results(event_id):
    event = Event.query.get_or_404(event_id)

    # Получаем всех участников мероприятия
    participants = EventParticipant.query.filter_by(event_id=event_id).all()

    # Отменяем изменения рейтинга, если они были применены
    for participant_event in participants:
        if participant_event.rating_change != 0:
            participant = Participant.query.get(participant_event.participant_id)
            if participant:
                participant.rating -= participant_event.rating_change

        # Сбрасываем место, баллы и изменение рейтинга
        participant_event.place = None
        participant_event.score = 0
        participant_event.rating_change = 0

    db.session.commit()
    flash('Результаты мероприятия сброшены', 'success')

    return redirect(url_for('admin_event_participants', event_id=event_id))

@app.route('/admin/structure/create', methods=['GET', 'POST'])
@login_required
def admin_structure_create():
    """Страница добавления члена федерации"""
    if request.method == 'POST':
        name = request.form.get('name')
        position = request.form.get('position')
        description = request.form.get('description')
        icon = request.form.get('icon')
        order = request.form.get('order', 0)
        is_active = True if request.form.get('is_active') else False

        member = FederationMember(
            name=name,
            position=position,
            description=description,
            icon=icon,
            order=order,
            is_active=is_active
        )

        # Обработка загрузки фото
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'members', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                member.photo = f'uploads/members/{filename}'

        db.session.add(member)
        db.session.commit()
        flash('Член федерации успешно добавлен!', 'success')
        return redirect(url_for('admin_structure_list'))

    return render_template('admin/structure/create.html')


@app.route('/admin/structure/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_structure_edit(id):
    """Страница редактирования члена федерации"""
    member = FederationMember.query.get_or_404(id)

    if request.method == 'POST':
        member.name = request.form.get('name')
        member.position = request.form.get('position')
        member.description = request.form.get('description')
        member.icon = request.form.get('icon')
        member.order = request.form.get('order', 0)
        member.is_active = True if request.form.get('is_active') else False

        # Обработка загрузки фото
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'members', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    file.save(filepath)

                    # Удаляем старое фото
                    if member.photo:
                        old_file = os.path.join(app.root_path, 'static', member.photo)
                        if os.path.exists(old_file):
                            os.remove(old_file)

                    member.photo = f'uploads/members/{filename}'

        db.session.commit()
        flash('Информация о члене федерации успешно обновлена!', 'success')
        return redirect(url_for('admin_structure_list'))

    return render_template('admin/structure/edit.html', member=member)


@app.route('/admin/structure/delete/<int:id>', methods=['POST'])
@login_required
def admin_structure_delete(id):
    """Удаление члена федерации"""
    member = FederationMember.query.get_or_404(id)

    # Удаляем фото
    if member.photo:
        file_path = os.path.join(app.root_path, 'static', member.photo)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(member)
    db.session.commit()
    flash('Член федерации успешно удален!', 'success')
    return redirect(url_for('admin_structure_list'))


@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


# Функция для проверки разрешенных типов файлов
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Роуты администрирования

# Modified part of the admin_dashboard route to properly handle calendar navigation
@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Главная страница админ-панели"""
    # Получаем параметры для календаря из GET-параметров (если есть)
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)

    # Set default values if not provided
    if month is None or year is None:
        current_date = datetime.now()
        if month is None:
            month = current_date.month
        if year is None:
            year = current_date.year

    news_count = News.query.count()
    events_count = Event.query.count()
    participants_count = Participant.query.count()
    partners_count = Partner.query.count()

    # Получаем предстоящие события
    upcoming_events = Event.query.filter(Event.start_date >= datetime.utcnow()).order_by(Event.start_date).limit(
        5).all()

    # Последние новости
    recent_news = News.query.order_by(News.created_at.desc()).limit(5).all()

    # Последние изображения галереи
    recent_gallery_images = Gallery.query.order_by(Gallery.created_at.desc()).limit(6).all()

    # Статистика по дисциплинам
    algorithmic_events_count = Event.query.filter_by(discipline='algorithmic').count()
    product_events_count = Event.query.filter_by(discipline='product').count()
    robotics_events_count = Event.query.filter_by(discipline='robotics').count()
    other_events_count = Event.query.filter_by(discipline='other').count()

    # Предстоящие события по дисциплинам (для быстрого доступа)
    upcoming_algorithmic = Event.query.filter(
        Event.discipline == 'algorithmic',
        Event.start_date >= datetime.utcnow()
    ).order_by(Event.start_date).limit(3).all()

    upcoming_product = Event.query.filter(
        Event.discipline == 'product',
        Event.start_date >= datetime.utcnow()
    ).order_by(Event.start_date).limit(3).all()

    upcoming_robotics = Event.query.filter(
        Event.discipline == 'robotics',
        Event.start_date >= datetime.utcnow()
    ).order_by(Event.start_date).limit(3).all()

    # Генерируем данные для календаря
    calendar_data = generate_calendar_data(year, month)

    return render_template('admin/dashboard.html',
                           news_count=news_count,
                           events_count=events_count,
                           participants_count=participants_count,
                           partners_count=partners_count,
                           upcoming_events=upcoming_events,
                           recent_news=recent_news,
                           recent_gallery_images=recent_gallery_images,
                           algorithmic_events_count=algorithmic_events_count,
                           product_events_count=product_events_count,
                           robotics_events_count=robotics_events_count,
                           other_events_count=other_events_count,
                           upcoming_algorithmic=upcoming_algorithmic,
                           upcoming_product=upcoming_product,
                           upcoming_robotics=upcoming_robotics,
                           calendar_data=calendar_data)


# Управление новостями
@app.route('/admin/news')
@login_required
def admin_news_list():
    news = News.query.order_by(News.created_at.desc()).all()
    return render_template('admin/news/list.html', news=news)


@app.route('/admin/news/create', methods=['GET', 'POST'])
@login_required
def admin_news_create():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        published = True if request.form.get('published') else False

        news = News(title=title, content=content, published=published)

        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'news', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                news.image = f'uploads/news/{filename}'

        db.session.add(news)
        db.session.commit()
        flash('Новость успешно создана!', 'success')
        return redirect(url_for('admin_news_list'))

    return render_template('admin/news/create.html')


@app.route('/admin/news/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_news_edit(id):
    news = News.query.get_or_404(id)

    if request.method == 'POST':
        news.title = request.form.get('title')
        news.content = request.form.get('content')
        news.published = True if request.form.get('published') else False

        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'news', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)

                # Удаляем старое изображение, если оно было
                if news.image:
                    old_file = os.path.join(app.root_path, 'static', news.image)
                    if os.path.exists(old_file):
                        os.remove(old_file)

                news.image = f'uploads/news/{filename}'

        db.session.commit()
        flash('Новость успешно обновлена!', 'success')
        return redirect(url_for('admin_news_list'))

    return render_template('admin/news/edit.html', news=news)


@app.route('/admin/news/delete/<int:id>', methods=['POST'])
@login_required
def admin_news_delete(id):
    news = News.query.get_or_404(id)

    # Удаляем изображение
    if news.image:
        file_path = os.path.join(app.root_path, 'static', news.image)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(news)
    db.session.commit()
    flash('Новость успешно удалена!', 'success')
    return redirect(url_for('admin_news_list'))


# Управление мероприятиями
@app.route('/admin/events')
@login_required
def admin_events_list():
    events = Event.query.order_by(Event.start_date.desc()).all()
    return render_template('admin/events/list.html', events=events)


@app.route('/admin/events/create', methods=['GET', 'POST'])
@login_required
def admin_events_create():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        location = request.form.get('location')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d %H:%M')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d %H:%M')
        registration_link = request.form.get('registration_link')
        published = True if request.form.get('published') else False
        discipline = request.form.get('discipline', 'other')  # Дисциплина, по умолчанию 'other'
        organizer = request.form.get('organizer', 'Федерация спортивного программирования ЗО')

        event = Event(
            title=title,
            description=description,
            location=location,
            start_date=start_date,
            end_date=end_date,
            registration_link=registration_link,
            published=published,
            discipline=discipline,
            organizer=organizer
        )

        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'events', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                event.image = f'uploads/events/{filename}'

        db.session.add(event)
        db.session.commit()
        flash('Мероприятие успешно создано!', 'success')
        return redirect(url_for('admin_events_list'))

    return render_template('admin/events/create.html')



@app.route('/admin/events/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_events_edit(id):
    event = Event.query.get_or_404(id)

    if request.method == 'POST':
        event.title = request.form.get('title')
        event.description = request.form.get('description')
        event.location = request.form.get('location')
        event.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d %H:%M')
        event.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d %H:%M')
        event.registration_link = request.form.get('registration_link')
        event.published = True if request.form.get('published') else False
        event.discipline = request.form.get('discipline', 'other')  # Обновление дисциплины
        event.organizer = request.form.get('organizer', 'Федерация спортивного программирования ЗО')

        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'events', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    file.save(filepath)

                    # Удаляем старое изображение
                    if event.image:
                        old_file = os.path.join(app.root_path, 'static', event.image)
                        if os.path.exists(old_file):
                            os.remove(old_file)

                    event.image = f'uploads/events/{filename}'

        db.session.commit()
        flash('Мероприятие успешно обновлено!', 'success')
        return redirect(url_for('admin_events_list'))

    return render_template('admin/events/edit.html', event=event)


@app.route('/admin/events/delete/<int:id>', methods=['POST'])
@login_required
def admin_events_delete(id):
    event = Event.query.get_or_404(id)

    # Удаляем изображение
    if event.image:
        file_path = os.path.join(app.root_path, 'static', event.image)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(event)
    db.session.commit()
    flash('Мероприятие успешно удалено!', 'success')
    return redirect(url_for('admin_events_list'))


# Управление участниками
@app.route('/admin/participants')
@login_required
def admin_participants_list():
    participants = Participant.query.order_by(Participant.rating.desc()).all()
    return render_template('admin/participants/list.html', participants=participants)


@app.route('/admin/participants/create', methods=['GET', 'POST'])
@login_required
def admin_participants_create():
    if request.method == 'POST':
        name = request.form.get('name')
        city = request.form.get('city')
        organization = request.form.get('organization')
        rating = request.form.get('rating')
        category = request.form.get('category')
        achievements = request.form.get('achievements')

        participant = Participant(
            name=name,
            city=city,
            organization=organization,
            rating=rating,
            category=category,
            achievements=achievements
        )

        db.session.add(participant)
        db.session.commit()
        flash('Участник успешно добавлен!', 'success')
        return redirect(url_for('admin_participants_list'))

    return render_template('admin/participants/create.html')


@app.route('/admin/participants/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_participants_edit(id):
    participant = Participant.query.get_or_404(id)

    if request.method == 'POST':
        participant.name = request.form.get('name')
        participant.city = request.form.get('city')
        participant.organization = request.form.get('organization')
        participant.rating = request.form.get('rating')
        participant.category = request.form.get('category')
        participant.achievements = request.form.get('achievements')

        db.session.commit()
        flash('Информация об участнике успешно обновлена!', 'success')
        return redirect(url_for('admin_participants_list'))

    return render_template('admin/participants/edit.html', participant=participant)


@app.route('/admin/participants/delete/<int:id>', methods=['POST'])
@login_required
def admin_participants_delete(id):
    participant = Participant.query.get_or_404(id)
    db.session.delete(participant)
    db.session.commit()
    flash('Участник успешно удален!', 'success')
    return redirect(url_for('admin_participants_list'))


# Управление партнерами
@app.route('/admin/partners')
@login_required
def admin_partners_list():
    partners = Partner.query.all()
    return render_template('admin/partners/list.html', partners=partners)


@app.route('/admin/partners/create', methods=['GET', 'POST'])
@login_required
def admin_partners_create():
    if request.method == 'POST':
        name = request.form.get('name')
        website = request.form.get('website')
        description = request.form.get('description')

        partner = Partner(name=name, website=website, description=description)

        # Обработка загрузки логотипа
        if 'logo' in request.files:
            file = request.files['logo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'partners', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                partner.logo = f'uploads/partners/{filename}'

        db.session.add(partner)
        db.session.commit()
        flash('Партнер успешно добавлен!', 'success')
        return redirect(url_for('admin_partners_list'))

    return render_template('admin/partners/create.html')


@app.route('/admin/partners/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_partners_edit(id):
    partner = Partner.query.get_or_404(id)

    if request.method == 'POST':
        partner.name = request.form.get('name')
        partner.website = request.form.get('website')
        partner.description = request.form.get('description')

        # Обработка загрузки логотипа
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename:
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'partners', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    file.save(filepath)

                    # Удаляем старый логотип
                    if partner.logo:
                        old_file = os.path.join(app.root_path, 'static', partner.logo)
                        if os.path.exists(old_file):
                            os.remove(old_file)

                    partner.logo = f'uploads/partners/{filename}'

        db.session.commit()
        flash('Информация о партнере успешно обновлена!', 'success')
        return redirect(url_for('admin_partners_list'))

    return render_template('admin/partners/edit.html', partner=partner)


@app.route('/admin/partners/delete/<int:id>', methods=['POST'])
@login_required
def admin_partners_delete(id):
    partner = Partner.query.get_or_404(id)

    # Удаляем логотип
    if partner.logo:
        file_path = os.path.join(app.root_path, 'static', partner.logo)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(partner)
    db.session.commit()
    flash('Партнер успешно удален!', 'success')
    return redirect(url_for('admin_partners_list'))


# Управление галереей
@app.route('/admin/gallery')
@login_required
def admin_gallery_list():
    gallery_items = Gallery.query.order_by(Gallery.created_at.desc()).all()
    return render_template('admin/gallery/list.html', gallery_items=gallery_items)


@app.route('/admin/gallery/create', methods=['GET', 'POST'])
@login_required
def admin_gallery_create():
    if request.method == 'POST':
        title = request.form.get('title')
        event_id = request.form.get('event_id')

        if event_id and event_id.isdigit():
            event_id = int(event_id)
        else:
            event_id = None

        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'gallery', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)

                gallery_item = Gallery(title=title, image=f'uploads/gallery/{filename}', event_id=event_id)
                db.session.add(gallery_item)
                db.session.commit()
                flash('Изображение успешно добавлено в галерею!', 'success')
            else:
                flash('Пожалуйста, загрузите изображение в формате png, jpg, jpeg или gif', 'danger')
        else:
            flash('Необходимо выбрать изображение', 'danger')

        return redirect(url_for('admin_gallery_list'))

    events = Event.query.all()
    return render_template('admin/gallery/create.html', events=events)


@app.route('/admin/gallery/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_gallery_edit(id):
    gallery_item = Gallery.query.get_or_404(id)

    if request.method == 'POST':
        gallery_item.title = request.form.get('title')

        event_id = request.form.get('event_id')
        if event_id and event_id.isdigit():
            gallery_item.event_id = int(event_id)
        else:
            gallery_item.event_id = None

        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'gallery', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    file.save(filepath)

                    # Удаляем старое изображение
                    if gallery_item.image:
                        old_file = os.path.join(app.root_path, 'static', gallery_item.image)
                        if os.path.exists(old_file):
                            os.remove(old_file)

                    gallery_item.image = f'uploads/gallery/{filename}'

        db.session.commit()
        flash('Информация успешно обновлена!', 'success')
        return redirect(url_for('admin_gallery_list'))

    events = Event.query.all()
    return render_template('admin/gallery/edit.html', gallery_item=gallery_item, events=events)


@app.route('/admin/gallery/delete/<int:id>', methods=['POST'])
@login_required
def admin_gallery_delete(id):
    gallery_item = Gallery.query.get_or_404(id)

    # Удаляем изображение
    if gallery_item.image:
        file_path = os.path.join(app.root_path, 'static', gallery_item.image)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(gallery_item)
    db.session.commit()
    flash('Изображение успешно удалено из галереи!', 'success')
    return redirect(url_for('admin_gallery_list'))


# Управление пользователями (только для суперадминов)
@app.route('/admin/users')
@login_required
def admin_users_list():
    if current_user.role != 'superadmin':
        flash('У вас недостаточно прав для доступа к этой странице', 'danger')
        return redirect(url_for('admin_dashboard'))

    users = User.query.all()
    return render_template('admin/users/list.html', users=users)


@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
def admin_users_create():
    if current_user.role != 'superadmin':
        flash('У вас недостаточно прав для доступа к этой странице', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Пользователь с таким именем или email уже существует', 'danger')
            return redirect(url_for('admin_users_create'))

        user = User(username=username, email=email, role=role)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()
        flash('Пользователь успешно создан!', 'success')
        return redirect(url_for('admin_users_list'))

    return render_template('admin/users/create.html')


@app.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_users_edit(id):
    if current_user.role != 'superadmin':
        flash('У вас недостаточно прав для доступа к этой странице', 'danger')
        return redirect(url_for('admin_dashboard'))

    user = User.query.get_or_404(id)

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        password = request.form.get('password')

        existing_user = User.query.filter(
            ((User.username == username) | (User.email == email)) &
            (User.id != id)
        ).first()

        if existing_user:
            flash('Пользователь с таким именем или email уже существует', 'danger')
            return redirect(url_for('admin_users_edit', id=id))

        user.username = username
        user.email = email
        user.role = role

        if password:
            user.set_password(password)

        db.session.commit()
        flash('Информация о пользователе успешно обновлена!', 'success')
        return redirect(url_for('admin_users_list'))

    return render_template('admin/users/edit.html', user=user)


@app.route('/admin/users/delete/<int:id>', methods=['POST'])
@login_required
def admin_users_delete(id):
    if current_user.role != 'superadmin':
        flash('У вас недостаточно прав для доступа к этой странице', 'danger')
        return redirect(url_for('admin_dashboard'))

    if current_user.id == id:
        flash('Вы не можете удалить свою учетную запись', 'danger')
        return redirect(url_for('admin_users_list'))

    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь успешно удален!', 'success')
    return redirect(url_for('admin_users_list'))


# Изменение своего профиля
@app.route('/admin/profile', methods=['GET', 'POST'])
@login_required
def admin_profile():
    if request.method == 'POST':
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')

        # Проверяем, не занят ли email другим пользователем
        existing_user = User.query.filter(
            (User.email == email) &
            (User.id != current_user.id)
        ).first()

        if existing_user:
            flash('Этот email уже занят другим пользователем', 'danger')
            return redirect(url_for('admin_profile'))

        current_user.email = email

        # Если пользователь хочет изменить пароль
        if current_password and new_password:
            if current_user.check_password(current_password):
                current_user.set_password(new_password)
                flash('Пароль успешно изменен!', 'success')
            else:
                flash('Текущий пароль указан неверно', 'danger')
                return redirect(url_for('admin_profile'))

        db.session.commit()
        flash('Профиль успешно обновлен!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/profile.html')


# API для получения данных для фронтенда
@app.route('/api/events/<int:event_id>')
@login_required
def api_event_detail(event_id):
    """API endpoint для получения данных о событии"""
    event = Event.query.get_or_404(event_id)

    return jsonify({
        'id': event.id,
        'title': event.title,
        'description': event.description,
        'location': event.location,
        'start_date': event.start_date.strftime('%Y-%m-%dT%H:%M:%S'),
        'end_date': event.end_date.strftime('%Y-%m-%dT%H:%M:%S'),
        'discipline': event.discipline,
        'registration_link': event.registration_link
    })


@app.route('/api/news')
def api_news():
    news = News.query.filter_by(published=True).order_by(News.created_at.desc()).all()
    news_data = []

    for item in news:
        news_data.append({
            'id': item.id,
            'title': item.title,
            'content': item.content,
            'image': item.image,
            'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    return json.dumps(news_data)


@app.route('/api/participants')
def api_participants():
    category = request.args.get('category', 'all')

    if category == 'all':
        participants = Participant.query.order_by(Participant.rating.desc()).all()
    else:
        participants = Participant.query.filter_by(category=category).order_by(Participant.rating.desc()).all()

    participants_data = []
    for participant in participants:
        participants_data.append({
            'id': participant.id,
            'name': participant.name,
            'city': participant.city,
            'organization': participant.organization,
            'rating': participant.rating,
            'achievements': participant.achievements
        })

    return json.dumps(participants_data)


@app.route('/api/partners')
def api_partners():
    partners = Partner.query.all()
    partners_data = []

    for partner in partners:
        partners_data.append({
            'id': partner.id,
            'name': partner.name,
            'logo': partner.logo,
            'website': partner.website,
            'description': partner.description
        })

    return json.dumps(partners_data)


@app.route('/api/gallery')
def api_gallery():
    event_id = request.args.get('event_id')

    if event_id and event_id.isdigit():
        gallery_items = Gallery.query.filter_by(event_id=int(event_id)).order_by(Gallery.created_at.desc()).all()
    else:
        gallery_items = Gallery.query.order_by(Gallery.created_at.desc()).all()

    gallery_data = []
    for item in gallery_items:
        gallery_data.append({
            'id': item.id,
            'title': item.title,
            'image': item.image,
            'event_id': item.event_id,
            'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    return json.dumps(gallery_data)




@app.context_processor
def inject_now():
    return {'now': datetime.now()}

@app.route('/news')
def news_list():
    """Страница со списком всех новостей"""
    news = News.query.filter_by(published=True).order_by(desc(News.created_at)).all()
    return render_template('news.html', news=news)


@app.route('/news/<int:id>')
def news_detail(id):
    """Страница с детальной информацией о новости"""
    news_item = News.query.get_or_404(id)
    if not news_item.published:
        return redirect(url_for('news_list'))

    # Получаем другие новости для блока "Читайте также"
    related_news = News.query.filter(
        News.id != id,
        News.published == True
    ).order_by(desc(News.created_at)).limit(3).all()

    return render_template('news_detail.html', news=news_item, related_news=related_news)


@app.route('/events')
def events_list():
    """Страница со списком всех мероприятий"""
    # Получаем текущие и будущие мероприятия
    upcoming_events = Event.query.filter(
        Event.start_date >= datetime.now(),
        Event.published == True
    ).order_by(Event.start_date).all()

    # Получаем прошедшие мероприятия
    past_events = Event.query.filter(
        Event.start_date < datetime.now(),
        Event.published == True
    ).order_by(desc(Event.start_date)).all()

    return render_template('events.html',
                           upcoming_events=upcoming_events,
                           past_events=past_events)


@app.route('/events/<int:id>')
def event_detail(id):
    """Страница с детальной информацией о мероприятии"""
    event = Event.query.get_or_404(id)
    if not event.published:
        return redirect(url_for('events_list'))

    # Получаем фотографии из галереи, связанные с этим мероприятием
    gallery_items = Gallery.query.filter_by(event_id=id).all()

    # Получаем индивидуальных участников этого мероприятия (только опубликованные)
    individual_participants = db.session.query(
        EventParticipant,
        Participant.name.label('participant_name'),
        Participant.organization,
        Participant.city
    ).join(
        Participant, EventParticipant.participant_id == Participant.id
    ).filter(
        EventParticipant.event_id == id,
        EventParticipant.participant_id != None,
        EventParticipant.published == True  # Only published participants
    ).all()

    # Получаем команды этого мероприятия (только опубликованные)
    team_participants = db.session.query(
        EventParticipant,
        Team.name.label('participant_name'),
        Team.organization,
        Team.city
    ).join(
        Team, EventParticipant.team_id == Team.id
    ).filter(
        EventParticipant.event_id == id,
        EventParticipant.team_id != None,
        EventParticipant.published == True  # Only published participants
    ).all()

    # Преобразуем результаты запросов в списки словарей
    individual_data = []
    for p_event, p_name, p_org, p_city in individual_participants:
        individual_data.append({
            'id': p_event.id,
            'participant_id': p_event.participant_id,
            'team_id': None,
            'is_team': False,
            'participant_name': p_name,
            'organization': p_org,
            'city': p_city,
            'place': p_event.place,
            'score': p_event.score,
            'rating_change': p_event.rating_change
        })

    team_data = []
    for p_event, t_name, t_org, t_city in team_participants:
        team_data.append({
            'id': p_event.id,
            'participant_id': None,
            'team_id': p_event.team_id,
            'is_team': True,
            'participant_name': t_name,
            'organization': t_org,
            'city': t_city,
            'place': p_event.place,
            'score': p_event.score,
            'rating_change': p_event.rating_change
        })

    # Объединяем данные
    participants = individual_data + team_data

    # Сортируем по месту (сначала с указанным местом, потом все остальные)
    participants.sort(key=lambda x: (x['place'] is None, x['place']))

    return render_template('event_detail.html',
                           event=event,
                           gallery_items=gallery_items,
                           participants=participants,
                           debug_info={'participants_count': len(participants)})


@app.route('/admin/events/<int:event_id>/participants/toggle-publish', methods=['POST'])
@login_required
def admin_event_toggle_publish_participant(event_id):
    """Изменение статуса публикации участника или команды в мероприятии"""
    event = Event.query.get_or_404(event_id)

    participant_id = request.form.get('participant_id')
    published = request.form.get('published') == 'true'

    participant_event = EventParticipant.query.get_or_404(participant_id)

    if participant_event.event_id != event_id:
        return jsonify({'success': False, 'message': 'Ошибка: участник не принадлежит этому мероприятию'})

    participant_event.published = published
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Участник {"опубликован" if published else "скрыт"}',
        'published': published
    })


def generate_calendar_data(year=None, month=None):
    """Generate calendar data for displaying in the dashboard with event information"""
    from datetime import datetime, timedelta
    import calendar

    # If no year/month specified, use current date
    if year is None or month is None:
        current_date = datetime.now()
        year = current_date.year
        month = current_date.month

    # Get first day of month and number of days in month
    first_day = datetime(year, month, 1)
    _, num_days = calendar.monthrange(year, month)

    # Get day of week for the first day (Monday is 0 in Python's calendar)
    first_weekday = first_day.weekday()

    # Generate calendar grid (a list of weeks, where each week is a list of days)
    weeks = []
    week = [{'day': 0, 'today': False, 'events': []} for _ in range(7)]

    # Fill in the first week with empty cells before the 1st day of month
    for i in range(first_weekday):
        week[i] = {'day': 0, 'today': False, 'events': []}

    # Fill in the actual days
    current_date = datetime.now().date()
    day = 1

    # Get all events in this month
    start_of_month = datetime(year, month, 1)
    if month == 12:
        end_of_month = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_of_month = datetime(year, month + 1, 1) - timedelta(days=1)

    events_this_month = Event.query.filter(
        Event.start_date >= start_of_month,
        Event.start_date <= end_of_month
    ).all()

    # Create a dictionary of events by day
    events_by_day = {}
    for event in events_this_month:
        event_day = event.start_date.day
        if event_day not in events_by_day:
            events_by_day[event_day] = []

        # Only add the first 3 events for display purposes
        if len(events_by_day[event_day]) < 3:
            events_by_day[event_day].append({
                'id': event.id,
                'title': event.title,
                'discipline': event.discipline,
                'time': event.start_date.strftime('%H:%M')
            })

    # Fill the calendar
    while day <= num_days:
        for i in range(first_weekday, 7):
            if day <= num_days:
                is_today = (day == current_date.day and
                            month == current_date.month and
                            year == current_date.year)

                day_events = events_by_day.get(day, [])
                has_more_events = len(events_by_day.get(day, [])) > 3

                # Only include the first 3 events for display, but note if there are more
                week[i] = {
                    'day': day,
                    'today': is_today,
                    'events': day_events[:3],
                    'has_more': has_more_events,
                    'total_events': len(day_events)
                }
                day += 1
            else:
                week[i] = {'day': 0, 'today': False, 'events': [], 'has_more': False, 'total_events': 0}

        weeks.append(week.copy())
        week = [{'day': 0, 'today': False, 'events': [], 'has_more': False, 'total_events': 0} for _ in range(7)]
        first_weekday = 0  # For all subsequent weeks, start from Monday

    # Also include month name and year for display
    month_name = first_day.strftime('%B')

    return {
        'weeks': weeks,
        'month_name': month_name,
        'year': year,
        'month': month
    }

@app.route('/participants')
def participants_list():
    """Страница с рейтингом участников"""
    category = request.args.get('category', 'all')

    if category == 'all':
        participants = Participant.query.order_by(desc(Participant.rating)).all()
    else:
        participants = Participant.query.filter_by(category=category).order_by(desc(Participant.rating)).all()

    return render_template('participants.html',
                           participants=participants,
                           current_category=category)


@app.route('/gallery')
def gallery():
    """Страница с галереей изображений"""
    gallery_items = Gallery.query.order_by(desc(Gallery.created_at)).all()

    # Группируем изображения по мероприятиям
    events = Event.query.filter(
        Event.id.in_([item.event_id for item in gallery_items if item.event_id])
    ).all()

    event_dict = {event.id: event for event in events}

    return render_template('gallery.html',
                           gallery_items=gallery_items,
                           events=event_dict)


@app.route('/contacts')
def contacts():
    """Страница с контактной информацией"""
    return render_template('contacts.html')

@app.route('/privacy')
def privacy():
    """Страница с контактной информацией"""
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    """Страница с контактной информацией"""
    return render_template('terms.html')

# Инициализация базы данных с первым администратором
@app.route('/admin/statistics')
@login_required
def admin_statistics():
    """Страница управления статистикой"""
    statistics = Statistics.query.all()

    # Автоматический подсчет некоторых статистик
    participants_count = Participant.query.count()
    cities_count = db.session.query(db.func.count(db.distinct(Participant.city))).scalar() or 0
    events_count = Event.query.filter(Event.start_date >= datetime(datetime.now().year, 1, 1)).count()

    return render_template('admin/statistics/manage.html',
                           statistics=statistics,
                           participants_count=participants_count,
                           cities_count=cities_count,
                           events_count=events_count)


@app.route('/admin/statistics/update', methods=['POST'])
@login_required
def admin_statistics_update():
    """Обновление значений статистики"""
    for key, value in request.form.items():
        if key.startswith('stat_'):
            stat_key = key.replace('stat_', '')
            try:
                stat_value = int(value)
                Statistics.update_value(stat_key, stat_value)
            except ValueError:
                flash(f'Некорректное значение для {stat_key}', 'danger')

    flash('Статистика успешно обновлена', 'success')
    return redirect(url_for('admin_statistics'))


@app.route('/admin/statistics/sync', methods=['POST'])
@login_required
def admin_statistics_sync():
    """Синхронизация статистики с реальными данными"""
    # Количество участников
    participants_count = Participant.query.count()
    Statistics.update_value('participants', participants_count)

    # Количество городов
    cities_count = db.session.query(db.func.count(db.distinct(Participant.city))).scalar() or 0
    Statistics.update_value('cities', cities_count)

    # Количество соревнований в текущем году
    events_count = Event.query.filter(Event.start_date >= datetime(datetime.now().year, 1, 1)).count()
    Statistics.update_value('competitions', events_count)

    flash('Статистика успешно синхронизирована с данными', 'success')
    return redirect(url_for('admin_statistics'))


@app.route('/admin/statistics/create', methods=['POST'])
@login_required
def admin_statistics_create():
    """Создание нового элемента статистики"""
    key = request.form.get('key')
    value = request.form.get('value', 0)
    title = request.form.get('title')
    subtitle = request.form.get('subtitle')
    is_counter = 'is_counter' in request.form

    if not key or not title or not subtitle:
        flash('Все поля должны быть заполнены', 'danger')
        return redirect(url_for('admin_statistics'))

    # Проверяем, существует ли уже такой ключ
    existing = Statistics.query.filter_by(key=key).first()
    if existing:
        flash(f'Статистика с ключом {key} уже существует', 'danger')
        return redirect(url_for('admin_statistics'))

    try:
        value = int(value)
        new_stat = Statistics(
            key=key,
            value=value,
            title=title,
            subtitle=subtitle,
            is_counter=is_counter
        )
        db.session.add(new_stat)
        db.session.commit()
        flash('Новый элемент статистики успешно создан', 'success')
    except ValueError:
        flash('Значение должно быть целым числом', 'danger')

    return redirect(url_for('admin_statistics'))


@app.route('/admin/statistics/delete/<key>', methods=['POST'])
@login_required
def admin_statistics_delete(key):
    """Удаление элемента статистики"""
    stat = Statistics.query.filter_by(key=key).first_or_404()
    db.session.delete(stat)
    db.session.commit()
    flash('Элемент статистики успешно удален', 'success')
    return redirect(url_for('admin_statistics'))


# Обновляем маршрут главной страницы для передачи статистики в шаблон
@app.route('/')
def home():
    """Главная страница сайта ФСПМО"""
    # Получаем последние новости
    news = News.query.filter_by(published=True).order_by(desc(News.created_at)).limit(3).all()

    # Получаем ближайшие мероприятия
    upcoming_events = Event.query.filter(
        Event.start_date >= datetime.now(),
        Event.published == True
    ).order_by(Event.start_date).limit(3).all()

    # Получаем топ участников
    top_participants = Participant.query.order_by(desc(Participant.rating)).limit(5).all()

    # Получаем партнеров
    partners = Partner.query.all()

    # Получаем изображения для галереи
    gallery_items = Gallery.query.order_by(desc(Gallery.created_at)).limit(8).all()

    # Получаем структуру федерации
    federation_structure = FederationMember.query.filter_by(is_active=True).order_by(FederationMember.order).all()

    # Получаем статистику
    statistics = {
        'participants': Statistics.get_value('participants', 0),
        'competitions': Statistics.get_value('competitions', 0),
        'cities': Statistics.get_value('cities', 0),
        'achievements': Statistics.get_value('achievements', 0),
        'participants_is_counter': Statistics.query.filter_by(
            key='participants').first().is_counter if Statistics.query.filter_by(key='participants').first() else True
    }

    return render_template('index.html',
                           news=news,
                           upcoming_events=upcoming_events,
                           top_participants=top_participants,
                           partners=partners,
                           gallery_items=gallery_items,
                           federation_structure=federation_structure,
                           statistics=statistics)


# Добавляем функцию для инициализации статистики при первом запуске
def init_statistics():
    """Инициализация базовых статистик, если их нет"""
    default_stats = [
        {'key': 'participants', 'value': 0, 'is_counter': True, 'title': 'Участников', 'subtitle': ''},
        {'key': 'competitions', 'value': 0, 'is_counter': False, 'title': 'Соревнований', 'subtitle': 'в год'},
        {'key': 'cities', 'value': 0, 'is_counter': False, 'title': 'Городов', 'subtitle': 'участников'},
        {'key': 'achievements', 'value': 0, 'is_counter': False, 'title': 'Призовых', 'subtitle': 'мест'}
    ]

    for stat in default_stats:
        existing = Statistics.query.filter_by(key=stat['key']).first()
        if not existing:
            new_stat = Statistics(
                key=stat['key'],
                value=stat['value'],
                is_counter=stat['is_counter'],
                title=stat['title'],
                subtitle=stat['subtitle']
            )
            db.session.add(new_stat)

    db.session.commit()


# Вызываем функцию инициализации статистики при создании базы данных
@app.cli.command('init-db')
def init_db_command():
    """Очистить существующие данные и создать новые таблицы."""
    db.drop_all()
    db.create_all()

    # Создаем суперадмина
    admin = User(
        username='admin',
        email='admin@example.com',
        role='superadmin'
    )
    admin.set_password('admin')
    db.session.add(admin)
    db.session.commit()

    # Инициализируем статистику
    init_statistics()

    print('База данных инициализирована, создан пользователь admin и базовая статистика')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')