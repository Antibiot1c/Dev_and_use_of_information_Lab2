from flask import Flask, request, redirect, flash, render_template_string, url_for, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import webbrowser
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hobbyhub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# дозволяємо фронтенду (index.html) ходити на API
CORS(app)


# -----------------------------
# МОДЕЛІ
# -----------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(120))
    is_admin = db.Column(db.Boolean, default=False)
    posts = db.relationship("Post", backref="author", lazy=True)
    likes = db.relationship("Like", backref="user", lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500))
    likes_count = db.Column(db.Integer, default=0)  # перейменував на likes_count для ясності
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    likes = db.relationship("Like", backref="post", lazy=True)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='unique_like'),
    )


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -----------------------------
# HTML-РОУТИ (лаба №1)
# -----------------------------
@app.route('/')
def index():
    posts = Post.query.order_by(Post.id.desc()).all()
    return render_template_string("""
    <h1>HobbyHub - Hobby Social Network</h1>
    {% for msg in get_flashed_messages() %}
        <p>{{msg}}</p>
    {% endfor %}
    {% if current_user.is_authenticated %}
        <p>Hello, {{current_user.name or current_user.email}}! 
        <a href="{{ url_for('profile') }}">Profile</a> | 
        <a href="{{ url_for('logout') }}">Logout</a></p>
        {% if current_user.is_admin %}
        <p><a href="{{ url_for('admin') }}">Admin Panel</a></p>
        {% endif %}
    {% else %}
        <p><a href="{{ url_for('login') }}">Login</a> | 
        <a href="{{ url_for('register') }}">Register</a></p>
    {% endif %}

    <h2>User Posts:</h2>
    {% for post in posts %}
        <div style="border:1px solid #ccc; padding:10px; margin:10px 0;">
            <h3>{{ post.title }}</h3>
            <p>{{ post.content }}</p>
            {% if post.image_url %}<img src="{{ post.image_url }}" width="200">{% endif %}
            <p>Author: {{ post.author.name or post.author.email }} | Likes: {{ post.likes_count }}</p>
        </div>
    {% else %}
        <p>No posts yet.</p>
    {% endfor %}
    """, posts=posts)


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']

        # проста валідація пошти
        if "@" not in email:
            flash("Invalid email format")
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash("User already exists")
        else:
            user = User(email=email, password=generate_password_hash(password), name=name)
            db.session.add(user)
            db.session.commit()
            flash("Registered! Please log in.")
            return redirect(url_for('login'))

    return render_template_string("""
    <h2>Register</h2>
    <form method="post">
        Name: <input name="name"><br>
        Email: <input name="email"><br>
        Password: <input name="password" type="password"><br>
        <input type="submit">
    </form>
    """)


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Logged in successfully!")
            return redirect(url_for('index'))
        flash("Invalid email or password")
    return render_template_string("""
    <h2>Login</h2>
    <form method="post">
        Email: <input name="email"><br>
        Password: <input name="password" type="password"><br>
        <input type="submit">
    </form>
    """)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out")
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image_url = request.form.get('image_url')
        post = Post(title=title, content=content, image_url=image_url, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash("Post added!")
        return redirect(url_for('profile'))

    posts = current_user.posts
    return render_template_string("""
    <h2>Your Profile</h2>
    <p>Hello, {{ current_user.name or current_user.email }}! 
    <a href="{{ url_for('index') }}">Home</a> | 
    <a href="{{ url_for('logout') }}">Logout</a></p>

    <h3>Add a Post</h3>
    <form method="post">
        Title: <input name="title"><br>
        Content:<br>
        <textarea name="content" rows="4" cols="50"></textarea><br>
        Image URL (optional): <input name="image_url"><br>
        <input type="submit" value="Add Post">
    </form>

    <h3>Your Posts</h3>
    {% for post in posts %}
        <div style="border:1px solid #ccc; padding:10px; margin:10px 0;">
            <h4>{{ post.title }}</h4>
            <p>{{ post.content }}</p>
            {% if post.image_url %}<img src="{{ post.image_url }}" width="200">{% endif %}
        </div>
    {% else %}
        <p>No posts yet.</p>
    {% endfor %}
    """, posts=posts)


@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return "403 - Access Denied"
    users = User.query.all()
    posts = Post.query.all()
    return render_template_string("""
    <h2>Admin Panel</h2>
    <p><a href="{{ url_for('index') }}">Home</a></p>
    <h3>Users</h3>
    <ul>
    {% for u in users %}
        <li>{{ u.name or u.email }} ({{ u.email }}) {% if u.is_admin %}[Admin]{% endif %}</li>
    {% endfor %}
    </ul>

    <h3>All Posts</h3>
    {% for post in posts %}
        <div style="border:1px solid #ccc; padding:10px; margin:10px 0;">
            <h4>{{ post.title }}</h4>
            <p>{{ post.content }}</p>
            {% if post.image_url %}<img src="{{ post.image_url }}" width="200">{% endif %}
            <p>Author: {{ post.author.name or post.author.email }}</p>
        </div>
    {% else %}
        <p>No posts yet.</p>
    {% endfor %}
    """, users=users, posts=posts)


# -----------------------------
# ХЕЛПЕР для токена (лаба №2)
# -----------------------------
def get_user_from_token(req):
    auth = req.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token.isdigit():
            return User.query.get(int(token))
    return None


# -----------------------------
# API для фронтенду (лаба №2)
# -----------------------------
@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json()
    name = data.get("name","")
    email = data.get("email","").lower()
    password = data.get("password","")

    # валідація емейла: має бути @
    if "@" not in email:
        return jsonify({"error": "Невалідний email"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Користувач вже існує"}), 400

    user = User(
        email=email,
        password=generate_password_hash(password),
        name=name
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({"status":"ok"})


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    email = data.get("email","").lower()
    password = data.get("password","")

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"error":"Невірний email або пароль"}), 401

    token = str(user.id)
    return jsonify({
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin
        },
        "token": token
    })


@app.route("/api/posts", methods=["GET","POST"])
def api_posts():
    if request.method == "GET":
        posts = Post.query.order_by(Post.id.desc()).all()
        return jsonify({
            "posts":[
                {
                    "id":p.id,
                    "title":p.title,
                    "content":p.content,
                    "image_url":p.image_url,
                    "likes":p.likes_count,
                    "liked_by_me": False,  # фронт оновить це вручну при лайку
                    "author_name": (p.author.name or p.author.email)
                }
                for p in posts
            ]
        })

    # POST -> створити пост
    user = get_user_from_token(request)
    if not user:
        return jsonify({"error":"Unauthorized"}), 401

    data = request.get_json()
    title = data.get("title","").strip()
    content = data.get("content","").strip()
    image_url = data.get("image_url","").strip() or None

    if not title or not content:
        return jsonify({"error":"title/content обовʼязково"}), 400

    post = Post(
        title=title,
        content=content,
        image_url=image_url,
        author=user
    )
    db.session.add(post)
    db.session.commit()

    return jsonify({"status":"ok","post_id":post.id})


# toggle лайка:
# - якщо юзер ще не лайкав пост -> створюємо Like, +1
# - якщо вже лайкав -> видаляємо Like, -1
@app.route("/api/like/<int:post_id>", methods=["POST"])
def api_like(post_id):
    user = get_user_from_token(request)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404

    existing = Like.query.filter_by(user_id=user.id, post_id=post.id).first()
    if existing:
        # знімаємо лайк
        db.session.delete(existing)
        if post.likes_count > 0:
            post.likes_count -= 1
        db.session.commit()
        return jsonify({"status": "unliked", "likes": post.likes_count})
    else:
        # ставимо лайк
        new_like = Like(user_id=user.id, post_id=post.id)
        db.session.add(new_like)
        post.likes_count += 1
        db.session.commit()
        return jsonify({"status": "liked", "likes": post.likes_count})


# -----------------------------
# Видача фронтенду файлу index.html через Flask (/frontend)
# -----------------------------
@app.route('/frontend')
def serve_frontend():
    return send_from_directory(os.getcwd(), 'index.html')


# -----------------------------
# CLI команди
# -----------------------------
@app.cli.command('init-db')
def init_db():
    db.create_all()
    print("✅ Database created!")

@app.cli.command('create-admin')
def create_admin():
    email = input("Email: ").strip().lower()
    password = input("Password: ").strip()
    name = input("Name: ").strip()
    user = User(email=email, password=generate_password_hash(password), name=name, is_admin=True)
    db.session.add(user)
    db.session.commit()
    print("✅ Admin created!")


# -----------------------------
# Запуск
# -----------------------------
if __name__ == '__main__':
    host = '127.0.0.1'
    port = 8000
    url = f"http://{host}:{port}/frontend"   # відкриває index.html одразу

    with app.app_context():
        db.create_all()

    webbrowser.open(url)
    app.run(host=host, port=port, debug=True, use_reloader=False)
