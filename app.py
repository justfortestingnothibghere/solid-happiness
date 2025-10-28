import os
import uuid
import re  # Added for range parsing
from flask import Flask, render_template, request, redirect, url_for, send_file, abort, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = '045794b417c591b76ce84b5abbf127ea'  # Change in prod (use env var)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///videos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOADED_VIDEOS_DEST'] = 'uploads'
db = SQLAlchemy(app)

# Ensure uploads dir
os.makedirs(app.config['UPLOADED_VIDEOS_DEST'], exist_ok=True)

# Models
class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    filename = db.Column(db.String(200), nullable=False)  # Secure filename

with app.app_context():
    db.create_all()

# Admin login check (simple session-based)
def admin_login():
    if 'admin_logged_in' not in session:
        if request.method == 'POST' and request.form.get('username') == 'admin' and request.form.get('password') == 'admin123':
            session['admin_logged_in'] = True
            return True
        return False
    return True

# Routes

@app.route('/')
def index():
    videos_list = Video.query.all()
    return render_template('index.html', videos=videos_list)

@app.route('/watch/<int:video_id>')
def watch(video_id):
    video = Video.query.get_or_404(video_id)
    video_url = url_for('video_file', filename=video.filename, _external=True)
    return render_template('watch.html', video=video, video_url=video_url)

@app.route('/uploads/<filename>')
def video_file(filename):
    filepath = os.path.join(app.config['UPLOADED_VIDEOS_DEST'], filename)
    if not os.path.exists(filepath):
        abort(404)
    range_header = request.headers.get('Range', None)
    if not range_header:
        return send_file(filepath, mimetype='video/mp4', as_attachment=False, conditional=True)
    # Parse range (e.g., bytes=0-)
    size = os.path.getsize(filepath)
    byte1, byte2 = 0, None
    m = re.search(r'(\d+)-(\d*)', range_header.split('=')[1])
    if m:
        byte1 = int(m.group(1))
        byte2 = int(m.group(2)) if m.group(2) else size - 1
    length = byte2 - byte1 + 1 if byte2 else size - byte1
    with open(filepath, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)
    resp = app.response_class(data, 206, mimetype='video/mp4', direct_passthrough=True)
    resp.headers.add('Content-Range', f'bytes {byte1}-{byte2 or size-1}/{size}')
    resp.headers.add('Accept-Ranges', 'bytes')
    resp.headers.add('Content-Length', str(length))
    return resp

# Admin
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not admin_login():
        return '''
            <form method="POST">
                Username: <input name="username"><br>
                Password: <input name="password" type="password"><br>
                <button>Login</button>
            </form>
        '''
    if request.method == 'POST' and 'add_video' in request.form:
        name = request.form['name']
        title = request.form['title']
        description = request.form['description']
        if 'video' not in request.files:
            flash('No file part')
            return redirect(url_for('admin'))
        file = request.files['video']
        if file.filename == '':
            flash('No selected file')
            return redirect(url_for('admin'))
        if file and file.content_type.startswith('video/'):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            filepath = os.path.join(app.config['UPLOADED_VIDEOS_DEST'], unique_filename)
            file.save(filepath)
            new_video = Video(name=name, title=title, description=description, filename=unique_filename)
            db.session.add(new_video)
            db.session.commit()
            flash('Video added successfully!')
        else:
            flash('Invalid file type')
        return redirect(url_for('admin'))
    videos_list = Video.query.all()
    return render_template('admin.html', videos=videos_list)

@app.route('/admin/edit/<int:video_id>', methods=['POST'])
def edit(video_id):
    if not session.get('admin_logged_in'):
        abort(403)
    video = Video.query.get_or_404(video_id)
    video.title = request.form['title']
    video.description = request.form['description']
    db.session.commit()
    flash('Video updated!')
    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:video_id>', methods=['POST'])
def delete(video_id):
    if not session.get('admin_logged_in'):
        abort(403)
    video = Video.query.get_or_404(video_id)
    filepath = os.path.join(app.config['UPLOADED_VIDEOS_DEST'], video.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(video)
    db.session.commit()
    flash('Video deleted!')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
