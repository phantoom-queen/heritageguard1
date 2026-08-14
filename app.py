import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "heritageguard.db")
SECRET_KEY = os.environ.get("HERITAGEGUARD_SECRET_KEY", "change-this-secret-key")

DEFAULT_USERS = [
    {"username": "admin", "password": "Heritage@123", "role": "admin"},
    {"username": "reporter", "password": "Report@123", "role": "user"},
]

NAV_LINKS = [
    {"endpoint": "home", "label": "Home"},
    {"endpoint": "heritage_sites", "label": "Heritage Sites"},
    {"endpoint": "report", "label": "Report Threat"},
    {"endpoint": "reports", "label": "Reports"},
    {"endpoint": "about", "label": "About Us"},
    {"endpoint": "contact", "label": "Contact"},
]

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def init_db():
    should_create = not os.path.exists(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    if should_create:
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS heritage_sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                region TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        now = datetime.utcnow().isoformat()
        for user in DEFAULT_USERS:
            cur.execute(
                "INSERT OR IGNORE INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                (user["username"], generate_password_hash(user["password"]), user["role"], now),
            )

        sample_sites = [
            ("Kasese Archaeological Zone", "Western Region", "Ancient rock art and ruins threatened by erosion and unauthorized access.", "Monitored", now),
            ("Jinja Heritage Path", "Eastern Region", "A sacred cultural site with historic pathways and hill shrines.", "Protected", now),
            ("Gulu Rock Shelter", "Northern Region", "Important heritage shelter containing artifacts and traditional carvings.", "Under Review", now),
        ]

        cur.executemany(
            "INSERT INTO heritage_sites (name, region, description, status, created_at) VALUES (?, ?, ?, ?, ?)",
            sample_sites,
        )

        sample_reports = [
            ("Illegal Excavation", "Kasese, Western Region", "Traces of unauthorized digging were observed near the protected rock shelters.", "Pending", now),
            ("Artifact Removal", "Jinja, Eastern Region", "Locals reported suspicious removal of historical objects from a known heritage trail.", "Under Review", now),
            ("Site Damage", "Gulu, Northern Region", "Recent flooding exposed damage to an archaeological site.", "Resolved", now),
        ]

        cur.executemany(
            "INSERT INTO reports (title, location, description, status, created_at) VALUES (?, ?, ?, ?, ?)",
            sample_reports,
        )

    else:
        for user in DEFAULT_USERS:
            existing = cur.execute("SELECT id FROM users WHERE username = ?", (user["username"],)).fetchone()
            if not existing:
                cur.execute(
                    "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                    (user["username"], generate_password_hash(user["password"]), user["role"], datetime.utcnow().isoformat()),
                )

    db.commit()
    db.close()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login", next=request.endpoint))

            if role is not None and session.get("role") != role:
                flash("You do not have permission to view that page.", "warning")
                return redirect(url_for("home"))

            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def get_stats():
    return {
        "reports": query_db("SELECT COUNT(*) AS count FROM reports", one=True)["count"],
        "sites": query_db("SELECT COUNT(*) AS count FROM heritage_sites", one=True)["count"],
        "resolved": query_db("SELECT COUNT(*) AS count FROM reports WHERE status = 'Resolved'", one=True)["count"],
        "users": query_db("SELECT COUNT(*) AS count FROM users", one=True)["count"],
    }


@app.context_processor
def inject_globals():
    return {
        "nav_links": NAV_LINKS,
        "current_user": session.get("username"),
    }


@app.route("/")
def home():
    stats = get_stats()
    reports = query_db("SELECT * FROM reports ORDER BY created_at DESC LIMIT 5")
    return render_template(
        "home.html",
        current_page="home",
        stats=stats,
        reports=reports,
    )


@app.route("/heritage-sites")
def heritage_sites():
    sites = query_db("SELECT * FROM heritage_sites ORDER BY id ASC")
    return render_template(
        "heritage_sites.html",
        current_page="heritage_sites",
        sites=sites,
    )


@app.route("/report", methods=["GET", "POST"])
def report():
    if request.method == "POST":
        title = request.form.get("title", "Untitled Report").strip()
        location = request.form.get("location", "Location not provided").strip()
        description = request.form.get("description", "").strip()

        if not title or not location:
            flash("A title and location are required to submit a report.", "danger")
            return redirect(url_for("report"))

        db = get_db()
        db.execute(
            "INSERT INTO reports (title, location, description, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (title, location, description, "Pending", datetime.utcnow().isoformat()),
        )
        db.commit()
        flash("Thank you. Your report has been submitted for review.", "success")
        return redirect(url_for("reports"))

    return render_template("report.html", current_page="report")


@app.route("/reports")
def reports():
    reports = query_db("SELECT * FROM reports ORDER BY created_at DESC")
    return render_template("reports.html", current_page="reports", reports=reports)


@app.route("/about")
def about():
    return render_template("about.html", current_page="about")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        flash("Thank you for your message. We will review your inquiry shortly.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html", current_page="contact")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Successfully signed in.", "success")
            return redirect(url_for("admin") if user["role"] == "admin" else url_for("home"))

        flash("Invalid username or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html", current_page="login")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/admin")
@login_required(role="admin")
def admin():
    stats = get_stats()
    recent_reports = query_db("SELECT * FROM reports ORDER BY created_at DESC LIMIT 5")
    sites = query_db("SELECT * FROM heritage_sites ORDER BY id ASC")
    return render_template(
        "admin.html",
        current_page="admin",
        stats=stats,
        recent_reports=recent_reports,
        sites=sites,
    )


@app.route("/api/public/stats")
def public_stats():
    return jsonify(get_stats())


@app.route("/api/public/reports")
def public_reports():
    reports = query_db("SELECT title, location, status, created_at FROM reports ORDER BY created_at DESC LIMIT 10")
    return jsonify([dict(row) for row in reports])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
