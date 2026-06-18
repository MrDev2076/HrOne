import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask import Flask, render_template, redirect, url_for, flash 
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, EmailField, TextAreaField, FileField, SubmitField
from wtforms.validators import DataRequired, Email
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super_secret_hrone_key_2026"
DB_FILE = "database.db"

#file uploading Config
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok= True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024 #100MB

# grha zhrj tknt gthb
#flask mailing feature
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'nadipallisudharshan@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'grha zhrj tknt gthb')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

#Form Feild setup
class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    subject = StringField('Subject', validators=[DataRequired()])
    message = TextAreaField('Message', validators=[DataRequired()])
    attachment = FileField('Attachment(Optional, Max 100MB)') 
    submit = SubmitField('Send Message')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                member_since TEXT DEFAULT '2026'
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'todo',
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        # Insert a default Admin account if empty
        try:
            conn.execute("INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
                         ('admin', 'admin@hrone.com', 'admin123', 'Admin'))
            conn.commit()
        except sqlite3.IntegrityError:
            pass

# --- Protection Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Authentication required! Please log in first.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'Admin':
            flash("Access denied! System Administrator clearance required.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with get_db_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
            if user:
                session['username'] = user['username']
                session['role'] = user['role']
                session['user_id'] = user['id']
                flash(f"Welcome back, {user['username']}!", "success")
                return redirect(url_for('dashboard'))
            flash("Invalid credentials. Try again.", "danger")
    return render_template('home.html', show_login_modal=True)

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('home'))

# --- General System Public Routes ---
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('role') == 'Admin':
        return redirect(url_for('admin_dashboard'))
    
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        orders = conn.execute("SELECT id, title as id, 'placed' as status, '0' as total, 'Just now' as created_at FROM tasks WHERE user_id = ?", (session['user_id'],)).fetchall()
    return render_template('user_dashboard.html', user=user, orders=orders)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        msg = Message(
            subject=f"[Contact form] {form.subject.data}",
            recipients=['nadipallisudharshan@gmail.com'], #Admin mail
            reply_to=form.email.data
        )

        body_text = f"From: {form.name.data} - {form.email.data} \n\n\nMessage: \n{form.message.data}"

        #File handling
        file = form.attachment.data
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            file_size = os.path.getsize(file_path)

            if file_size > 20 * 1024 * 1024:
                body_text = f"\n\n[SYSTEM NOTE]: A larger file named `{filename}` ({round(file_size/(1024*1024), 2)})"
            else:
                #file size is under 100MB
                with app.open_resource(file_path) as fp:
                    msg.attach(filename, file.mimetype, fp.read())
                    body_text += f"\n\n[SYSTEM NOTE:] Attached file `{filename}` successfully"
        msg.body = body_text

        try:
            mail.send(msg)
            flash(f'Your form has submitted successfully', 'success')
        except Exception as e:
            flash(f'An error occured: {e}', 'danger')

    return render_template('contact.html', form=form)

#Handle large file 
@app.errorhandler(413)
def file_too_large(e):
    flash('File is too large!\nMaximum allowed size is 100MB', 'danger')
    return redirect(url_for('contact'))

# --- Admin Controller Core ---
@app.route('/admin')
@admin_required
def admin_dashboard():
    with get_db_connection() as conn:
        users = conn.execute("SELECT * FROM users").fetchall()
    return render_template('admin_dashboard.html', users=users)

@app.route('/admin/add', methods=['POST'])
@admin_required
def admin_add():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']
    try:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)", (username, email, password, role))
            conn.commit()
        flash("New profile successfully registered inside cluster database.", "success")
    except sqlite3.IntegrityError:
        flash("Username already exists inside system registry.", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit/<int:id>', methods=['POST'])
@admin_required
def admin_edit(id):
    username = request.form['username']
    email = request.form['email']
    role = request.form['role']
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET username = ?, email = ?, role = ? WHERE id = ?", (username, email, role, id))
        conn.commit()
    flash("System records patched successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:id>')
@admin_required
def admin_delete(id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (id,))
        conn.commit()
    flash("Profile successfully terminated from database core.", "warning")
    return redirect(url_for('admin_dashboard'))

# --- User Profile Self Updates ---
@app.route('/user/update', methods=['POST'])
@login_required
def user_update():
    email = request.form['email']
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, session['user_id']))
        conn.commit()
    flash("Contact email reference updated.", "success")
    return redirect(url_for('dashboard'))

@app.route('/user/reset-password', methods=['POST'])
@login_required
def user_reset_password():
    password = request.form['password']
    with get_db_connection() as conn:
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (password, session['user_id']))
        conn.commit()
    flash("Security token updated securely.", "success")
    return redirect(url_for('dashboard'))

# --- Agile Leaves, Meetings & Scrum Tasks Modules ---
@app.route('/leaves')
@login_required
def leaves():
    return render_template('leaves.html', active_tab='leaves', page_title="Leave Management", target_heading="Time-Off Approvals Module")

@app.route('/meetings')
@login_required
def meetings():
    return render_template('meetings.html', active_tab='meetings', page_title="Corporate Sync", target_heading="Ecosystem Scheduled Syncs")

@app.route('/tasks')
@login_required
def tasks():
    with get_db_connection() as conn:
        todo = conn.execute("SELECT * FROM tasks WHERE status = 'todo'").fetchall()
        progress = conn.execute("SELECT * FROM tasks WHERE status = 'progress'").fetchall()
        done = conn.execute("SELECT * FROM tasks WHERE status = 'done'").fetchall()
        users = conn.execute("SELECT id, username FROM users").fetchall()
    return render_template('tasks.html', active_tab='tasks', page_title="Agile Scrum Workspace", todo_tasks=todo, progress_tasks=progress, done_tasks=done, users=users)

@app.route('/tasks/add', methods=['POST'])
@login_required
def add_scrum_task():
    title = request.form['title']
    description = request.form['description']
    user_id = request.form.get('user_id') or None
    with get_db_connection() as conn:
        conn.execute("INSERT INTO tasks (title, description, status, user_id) VALUES (?, ?, 'todo', ?)", (title, description, user_id))
        conn.commit()
    flash("Scrum item committed to backlog.", "success")
    return redirect(url_for('tasks'))

@app.route('/tasks/move/<int:id>/<string:status>')
@login_required
def move_scrum_task(id, status):
    if status in ['todo', 'progress', 'done']:
        with get_db_connection() as conn:
            conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, id))
            conn.commit()
        flash("Task sprint classification transitioned.", "success")
    return redirect(url_for('tasks'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)