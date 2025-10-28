import os
import uuid
import re
from flask import Flask, render_template, request, redirect, url_for, send_file, abort, session, flash, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# ---------------------------
# Flask Config
# ---------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = '045794b417c591b76ce84b5abbf127ea'  # Change for production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///videos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)

# Ensure uploads directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------------------------
# Database Model
# ---------------------------
class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    filename = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

# ---------------------------
# Admin Auth (Simple)
# ---------------------------
def require_admin():
    if not session.get("admin_logged_in"):
        return False
    return True


@app.route("/admin", methods=["GET", "POST"])
def admin():
    # login form
    if not session.get("admin_logged_in"):
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            if username == "admin" and password == "admin123":
                session["admin_logged_in"] = True
                return redirect(url_for("admin"))
            flash("Invalid credentials!")
        return '''
            <h2>Admin Login</h2>
            <form method="POST">
                <input name="username" placeholder="Username"><br>
                <input name="password" type="password" placeholder="Password"><br>
                <button type="submit">Login</button>
            </form>
        '''

    # add new video
    if request.method == "POST" and 'add_video' in request.form:
        name = request.form['name']
        title = request.form['title']
        description = request.form['description']
        file = request.files.get('video')

        if not file or file.filename == "":
            flash("No video selected.")
            return redirect(url_for("admin"))

        if not file.content_type.startswith("video/"):
            flash("Invalid file type.")
            return redirect(url_for("admin"))

        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(filepath)

        new_video = Video(name=name, title=title, description=description, filename=unique_filename)
        db.session.add(new_video)
        db.session.commit()
        flash("Video uploaded successfully!")
        return redirect(url_for("admin"))

    videos_list = Video.query.all()
    return render_template("admin.html", videos=videos_list)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logged out.")
    return redirect(url_for("admin"))


@app.route("/admin/delete/<int:video_id>", methods=["POST"])
def admin_delete(video_id):
    if not require_admin():
        abort(403)
    video = Video.query.get_or_404(video_id)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], video.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(video)
    db.session.commit()
    flash("Video deleted successfully.")
    return redirect(url_for("admin"))


@app.route("/admin/edit/<int:video_id>", methods=["POST"])
def admin_edit(video_id):
    if not require_admin():
        abort(403)
    video = Video.query.get_or_404(video_id)
    video.title = request.form["title"]
    video.description = request.form["description"]
    db.session.commit()
    flash("Video updated successfully.")
    return redirect(url_for("admin"))

# ---------------------------
# Public Routes
# ---------------------------

@app.route("/")
def index():
    videos = Video.query.all()
    return render_template("index.html", videos=videos)


@app.route("/watch/<int:video_id>")
def watch(video_id):
    video = Video.query.get_or_404(video_id)
    video_url = url_for("serve_video", filename=video.filename)
    return render_template("watch.html", video=video, video_url=video_url)


@app.route("/uploads/<filename>")
def serve_video(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        abort(404)

    range_header = request.headers.get('Range', None)
    if not range_header:
        return send_file(filepath, mimetype="video/mp4")

    # Handle partial content
    size = os.path.getsize(filepath)
    byte1, byte2 = 0, None
    m = re.search(r'bytes=(\d+)-(\d*)', range_header)
    if m:
        byte1 = int(m.group(1))
        if m.group(2):
            byte2 = int(m.group(2))
    length = size - byte1 if byte2 is None else byte2 - byte1 + 1

    with open(filepath, "rb") as f:
        f.seek(byte1)
        data = f.read(length)

    resp = Response(data, 206, mimetype="video/mp4", direct_passthrough=True)
    resp.headers.add("Content-Range", f"bytes {byte1}-{byte1 + length - 1}/{size}")
    resp.headers.add("Accept-Ranges", "bytes")
    resp.headers.add("Content-Length", str(length))
    return resp


# ---------------------------
# Run the App
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
