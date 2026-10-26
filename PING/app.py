#!/usr/bin/env python3
"""PING — red social local. SQLite en local y Turso opcional en producción."""
import os
import sqlite3
from math import radians, sin, cos, sqrt, asin
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, jsonify, make_response, session

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = bool(os.environ.get('PING_HTTPS', '').lower() in ('1', 'true', 'yes'))
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30

TURSO_URL = os.environ.get('TURSO_DATABASE_URL', '').strip()
TURSO_TOKEN = os.environ.get('TURSO_AUTH_TOKEN', '').strip()
USE_TURSO = bool(TURSO_URL and TURSO_TOKEN)
LOCAL_DB = os.environ.get('PING_DB_PATH', os.path.join(app.instance_path, 'ping.db'))

ZONAS = {
    'lalin': {'nombre': 'Lalín', 'lat': 42.6606, 'lng': -8.1133},
    'cello': {'nombre': 'Cello', 'lat': 42.6500, 'lng': -8.7500},
    'rodeiro': {'nombre': 'Rodeiro', 'lat': 42.6500, 'lng': -7.9500},
    'santiago': {'nombre': 'Santiago de Compostela', 'lat': 42.8782, 'lng': -8.5448},
    'pontevedra': {'nombre': 'Pontevedra', 'lat': 42.4300, 'lng': -8.6440},
    'ourense': {'nombre': 'Ourense', 'lat': 42.3400, 'lng': -7.8700},
    'vigo': {'nombre': 'Vigo', 'lat': 42.2406, 'lng': -8.7227},
    'coruna': {'nombre': 'A Coruña', 'lat': 43.3623, 'lng': -8.4115}
}
CATEGORIES = {'general', 'venta', 'evento', 'perdido', 'ayuda', 'ocio', 'comunidad'}

if USE_TURSO:
    try:
        import libsql
    except ImportError as exc:
        raise RuntimeError('Hay configuración de Turso, pero falta libsql. Instala requirements.txt.') from exc


def connection():
    if USE_TURSO:
        conn = libsql.connect('ping.db', sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
        conn.sync()
        return conn
    os.makedirs(os.path.dirname(os.path.abspath(LOCAL_DB)), exist_ok=True)
    conn = sqlite3.connect(LOCAL_DB, timeout=10)
    conn.row_factory = None
    return conn


def query(sql, params=()):
    conn = connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall() if cur.description else []
        conn.commit()
        if USE_TURSO:
            try:
                conn.sync()
            except Exception:
                pass
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass


def init_db():
    query('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
        email TEXT NOT NULL COLLATE NOCASE UNIQUE, password_hash TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    query('''CREATE TABLE IF NOT EXISTS post (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
        content TEXT NOT NULL, category TEXT DEFAULT 'general', lat REAL, lng REAL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    query('''CREATE TABLE IF NOT EXISTS group_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        description TEXT DEFAULT '', created_by TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    query('''CREATE TABLE IF NOT EXISTS group_member (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
        group_id INTEGER NOT NULL, joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(username, group_id))''')
    query('CREATE INDEX IF NOT EXISTS idx_post_created ON post(created_at)')
    query('CREATE INDEX IF NOT EXISTS idx_group_member_group ON group_member(group_id)')


try:
    init_db()
    print('PING database ready (' + ('Turso' if USE_TURSO else 'SQLite local') + ')')
except Exception as exc:
    # Dejar que la app arranque para mostrar errores de conexión en el log, no ocultarlos.
    app.logger.exception('No se pudo inicializar la base de datos: %s', exc)


def username():
    """Nombre de la cuenta autenticada; invitado solo para lectura."""
    value = session.get('username') or 'Invitado'
    return str(value).strip()[:32] or 'Invitado'


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify(error='Inicia sesión o crea una cuenta para hacer eso.', auth_required=True), 401
        return fn(*args, **kwargs)
    return wrapped


def haversine(lat1, lon1, lat2, lon2):
    radius = 6371
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return radius * 2 * asin(sqrt(min(1, a)))


def valid_coords(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return None, None
        return lat, lng
    except (TypeError, ValueError):
        return None, None


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    return response


@app.route('/')
def index():
    zone = request.cookies.get('ping_zone', 'lalin')
    if zone not in ZONAS:
        zone = 'lalin'
    return render_template('index.html', username=username(), zone=zone, zone_name=ZONAS[zone]['nombre'], logged_in=bool(session.get('user_id')), account_email=session.get('email', ''))


@app.get('/api/auth/me')
def auth_me():
    return jsonify(authenticated=bool(session.get('user_id')), username=session.get('username'), email=session.get('email'))


@app.post('/api/auth/register')
def auth_register():
    data = json_body()
    name = str(data.get('username', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    if len(name) < 3 or len(name) > 32 or not all(ch.isalnum() or ch in ' _-' for ch in name):
        return jsonify(error='El nombre debe tener entre 3 y 32 caracteres (letras, números, espacios, _ o -).'), 400
    if len(email) > 254 or '@' not in email or '.' not in email.rsplit('@', 1)[-1]:
        return jsonify(error='Introduce un correo electrónico válido.'), 400
    if len(password) < 8 or len(password) > 128:
        return jsonify(error='La contraseña debe tener entre 8 y 128 caracteres.'), 400
    try:
        rows = query('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?) RETURNING id',
                     (name, email, generate_password_hash(password)))
        session.clear()
        session['user_id'] = int(rows[0][0])
        session['username'] = name
        session['email'] = email
        session.permanent = True
        return jsonify(success=True, authenticated=True, username=name, email=email), 201
    except Exception as exc:
        msg = str(exc).lower()
        if 'unique' in msg or 'constraint' in msg:
            return jsonify(error='Ese nombre de usuario o correo ya está registrado.'), 409
        app.logger.exception('Register failed')
        return jsonify(error='No se pudo crear la cuenta. Inténtalo de nuevo.'), 500


@app.post('/api/auth/login')
def auth_login():
    data = json_body()
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    if not email or not password:
        return jsonify(error='Escribe tu correo y contraseña.'), 400
    try:
        rows = query('SELECT id, username, email, password_hash FROM users WHERE email=? LIMIT 1', (email,))
        if not rows or not check_password_hash(rows[0][3], password):
            return jsonify(error='Correo o contraseña incorrectos.'), 401
        session.clear()
        session['user_id'] = int(rows[0][0])
        session['username'] = rows[0][1]
        session['email'] = rows[0][2]
        session.permanent = True
        return jsonify(success=True, authenticated=True, username=rows[0][1], email=rows[0][2])
    except Exception:
        app.logger.exception('Login failed')
        return jsonify(error='No se pudo iniciar sesión. Inténtalo de nuevo.'), 500


@app.post('/api/auth/logout')
def auth_logout():
    session.clear()
    return jsonify(success=True, authenticated=False)


@app.post('/set_username')
@login_required
def set_username():
    name = str(json_body().get('username', '')).strip()
    if len(name) < 3 or len(name) > 32 or not all(ch.isalnum() or ch in ' _-' for ch in name):
        return jsonify(error='El nombre debe tener entre 3 y 32 caracteres.'), 400
    try:
        query('UPDATE users SET username=? WHERE id=?', (name, session['user_id']))
        session['username'] = name
        return jsonify(success=True, username=name)
    except Exception as exc:
        if 'unique' in str(exc).lower() or 'constraint' in str(exc).lower():
            return jsonify(error='Ese nombre ya está en uso.'), 409
        app.logger.exception('Rename failed')
        return jsonify(error='No se pudo actualizar el nombre.'), 500


@app.get('/api/posts')
def api_posts():
    try:
        lat, lng = valid_coords(request.args.get('lat'), request.args.get('lng'))
        rows = query('SELECT id, username, content, category, lat, lng, created_at FROM post ORDER BY id DESC LIMIT 200')
        result = []
        radius = min(max(request.args.get('radius', default=10, type=float) or 10, 1), 100)
        for row in rows:
            dist = None
            if lat is not None and lng is not None and row[4] is not None and row[5] is not None:
                dist = haversine(lat, lng, float(row[4]), float(row[5]))
                if dist > radius:
                    continue
            elif lat is not None and lng is not None and row[4] is not None and row[5] is not None:
                continue
            result.append({'id': row[0], 'username': row[1], 'content': row[2], 'category': row[3] or 'general',
                           'lat': row[4], 'lng': row[5], 'dist': round(dist, 1) if dist is not None else None,
                           'created_at': str(row[6] or '')})
        return jsonify(result)
    except Exception:
        app.logger.exception('GET /api/posts failed')
        return jsonify(error='No se pudieron cargar los avisos. Comprueba la base de datos.'), 500


@app.post('/api/posts')
@login_required
def create_post():
    data = json_body()
    content = str(data.get('content', '')).strip()
    category = str(data.get('category', 'general')).lower()
    lat, lng = valid_coords(data.get('lat'), data.get('lng'))
    if not content:
        return jsonify(error='Escribe el contenido del aviso.'), 400
    if len(content) > 500:
        return jsonify(error='El aviso puede tener como máximo 500 caracteres.'), 400
    if category not in CATEGORIES:
        category = 'general'
    try:
        rows = query('INSERT INTO post (username, content, category, lat, lng) VALUES (?, ?, ?, ?, ?) RETURNING id',
                     (username(), content, category, lat, lng))
        return jsonify(success=True, id=rows[0][0] if rows else None), 201
    except Exception:
        app.logger.exception('POST /api/posts failed')
        return jsonify(error='No se pudo publicar el aviso.'), 500


@app.get('/api/groups')
def api_groups():
    try:
        rows = query('''SELECT g.id, g.name, g.description, g.created_by, g.created_at,
                        (SELECT COUNT(*) FROM group_member m WHERE m.group_id=g.id) AS members,
                        (SELECT COUNT(*) FROM group_member m WHERE m.group_id=g.id AND m.username=?) AS is_member
                        FROM group_table g ORDER BY g.id DESC LIMIT 100''', (username(),))
        return jsonify([{'id': r[0], 'name': r[1], 'description': r[2] or '', 'created_by': r[3],
                         'created_at': str(r[4] or ''), 'members': r[5], 'is_member': bool(r[6])} for r in rows])
    except Exception:
        app.logger.exception('GET /api/groups failed')
        return jsonify(error='No se pudieron cargar los grupos.'), 500


@app.post('/api/groups')
@login_required
def create_group():
    data = json_body()
    name = str(data.get('name', '')).strip()
    description = str(data.get('description', '')).strip()
    if not name:
        return jsonify(error='El nombre del grupo es obligatorio.'), 400
    if len(name) > 60 or len(description) > 240:
        return jsonify(error='El nombre admite 60 caracteres y la descripción 240.'), 400
    try:
        rows = query('INSERT INTO group_table (name, description, created_by) VALUES (?, ?, ?) RETURNING id',
                     (name, description, username()))
        group_id = rows[0][0]
        query('INSERT OR IGNORE INTO group_member (username, group_id) VALUES (?, ?)', (username(), group_id))
        return jsonify(success=True, id=group_id), 201
    except Exception:
        app.logger.exception('POST /api/groups failed')
        return jsonify(error='No se pudo crear el grupo.'), 500


@app.post('/api/groups/<int:group_id>/join')
@login_required
def join_group(group_id):
    try:
        exists = query('SELECT id FROM group_table WHERE id=?', (group_id,))
        if not exists:
            return jsonify(error='Ese grupo ya no existe.'), 404
        query('INSERT OR IGNORE INTO group_member (username, group_id) VALUES (?, ?)', (username(), group_id))
        return jsonify(success=True)
    except Exception:
        app.logger.exception('POST /api/groups/join failed')
        return jsonify(error='No se pudo unir al grupo.'), 500


@app.post('/set_zone')
def set_zone():
    zone = json_body().get('zone')
    if zone not in ZONAS:
        return jsonify(error='Zona no válida.'), 400
    response = make_response(jsonify(success=True, zone=zone, coords=ZONAS[zone]))
    response.set_cookie('ping_zone', zone, max_age=60*60*24*30, httponly=True, samesite='Lax', secure=request.is_secure)
    return response


@app.get('/api/zones')
def get_zones():
    return jsonify([{'id': k, **v} for k, v in ZONAS.items()])


@app.get('/api/current_zone')
def get_current_zone():
    zone = request.cookies.get('ping_zone', 'lalin')
    if zone not in ZONAS:
        zone = 'lalin'
    return jsonify(zone=zone, coords=ZONAS[zone])


@app.get('/api/health')
def health():
    try:
        query('SELECT 1')
        return jsonify(status='ok', database='turso' if USE_TURSO else 'sqlite-local')
    except Exception:
        app.logger.exception('Health check failed')
        return jsonify(status='error', database='unavailable'), 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
