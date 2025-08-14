import os
import sqlite3
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from sudoku_generator import generate_puzzle

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")
DB_PATH = os.path.join(os.path.dirname(__file__), "sudoku.db")

# Email config
EMAIL_DEBUG = os.getenv("EMAIL_DEBUG", "0") == "1"
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "Sudoku App <no-reply@example.com>")
OTP_EXP_MINUTES = int(os.getenv("OTP_EXP_MINUTES", "10"))

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            purpose TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()

@app.before_request
def startup():
    if not getattr(app, "_db_initialized", False):
        init_db()
        app._db_initialized = True

# ---- Email sender ----
def send_email(to: str, subject: str, body: str) -> bool:
    """Send email via SMTP using env config. Returns True if sent, False otherwise."""
    if EMAIL_DEBUG:
        # In debug mode, we simulate success but do not print OTP
        return True
    try:
        msg = EmailMessage()
        msg["From"] = EMAIL_SENDER
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        # log to console for debugging (server log); don't expose to user
        print("[EMAIL ERROR]", e)
        return False

def create_and_send_otp(user_id: int, email: str, purpose: str):
    import random
    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXP_MINUTES)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO otps (user_id, code, purpose, expires_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, code, purpose, expires_at.isoformat()))
    conn.commit()
    conn.close()
    body = f"Your {purpose.title()} OTP is: {code}\nThis code expires in {OTP_EXP_MINUTES} minutes."
    ok = send_email(email, f"{purpose.title()} OTP - Sudoku App", body)
    if not ok:
        raise RuntimeError("email_send_failed")
    return code

def login_required(view):
    from functools import wraps
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if not session.get("otp_ok"):
            return redirect(url_for("otp"))
        return view(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    if session.get("user_id") and session.get("otp_ok"):
        return redirect(url_for("sudoku"))
    return redirect(url_for("login"))

# Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("register.html")
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)",
                        (email, generate_password_hash(password)))
            conn.commit()
            user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            conn.close()
            flash("Email already registered.", "danger")
            return render_template("register.html")
        try:
            create_and_send_otp(user_id, email, "register")
        except Exception:
            flash("Could not send verification email. Please check SMTP settings and try again.", "danger")
            return render_template("register.html")
        conn.close()
        session["pending_verify_user_id"] = user_id
        return redirect(url_for("otp", next=url_for("login"), purpose="register"))
    return render_template("register.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, email, password_hash, is_verified FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            conn.close()
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        if not user["is_verified"]:
            try:
                create_and_send_otp(user["id"], user["email"], "register")
            except Exception:
                flash("Could not send verification email. Please check SMTP settings.", "danger")
                return render_template("login.html")
            session["pending_verify_user_id"] = user["id"]
            conn.close()
            flash("Please verify your email first. We sent you an OTP.", "info")
            return redirect(url_for("otp", purpose="register", next=url_for("login")))
        # Verified: send login OTP
        try:
            create_and_send_otp(user["id"], user["email"], "login")
        except Exception:
            flash("Could not send login OTP. Please check SMTP settings.", "danger")
            return render_template("login.html")
        session["pending_login_user_id"] = user["id"]
        conn.close()
        return redirect(url_for("otp", purpose="login", next=url_for("sudoku")))
    return render_template("login.html")

# OTP page
@app.route("/otp", methods=["GET", "POST"])
def otp():
    purpose = request.args.get("purpose", "") or request.form.get("purpose", "")
    next_url = request.args.get("next", "") or request.form.get("next", "")
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        purpose = request.form.get("purpose", purpose)
        next_url = request.form.get("next", next_url)

        user_id = session.get("pending_verify_user_id") if purpose == "register" else session.get("pending_login_user_id")
        if not user_id:
            flash("Session expired. Please try again.", "danger")
            return redirect(url_for("login"))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, code, expires_at, used FROM otps
            WHERE user_id=? AND purpose=? AND used=0
            ORDER BY id DESC LIMIT 1
        """, (user_id, purpose))
        rec = cur.fetchone()
        if not rec:
            conn.close()
            flash("No OTP found. Please request a new one.", "danger")
            return redirect(url_for("login" if purpose == "login" else "register"))

        if datetime.fromisoformat(rec["expires_at"]) < datetime.utcnow():
            conn.close()
            flash("OTP expired. Please request a new one.", "danger")
            return redirect(url_for("login" if purpose == "login" else "register"))

        if code != rec["code"]:
            conn.close()
            flash("Incorrect OTP.", "danger")
            return render_template("otp.html", purpose=purpose, next=next_url)

        cur.execute("UPDATE otps SET used=1 WHERE id=?", (rec["id"],))
        if purpose == "register":
            cur.execute("UPDATE users SET is_verified=1 WHERE id=?", (user_id,))
            conn.commit(); conn.close()
            session.pop("pending_verify_user_id", None)
            flash("Email verified! Please log in.", "success")
            return redirect(url_for("login"))
        else:
            conn.commit(); conn.close()
            session.pop("pending_login_user_id", None)
            session["user_id"] = user_id
            session["otp_ok"] = True
            return redirect(next_url or url_for("sudoku"))
    return render_template("otp.html", purpose=purpose, next=next_url)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# Sudoku page & API
@app.route("/sudoku")
@login_required
def sudoku():
    return render_template("sudoku.html")

@app.route("/api/new_puzzle")
@login_required
def api_new_puzzle():
    level = request.args.get("level", "easy").lower()
    if level not in ("easy", "medium", "hard"):
        level = "easy"
    puzzle, solution = generate_puzzle(level)
    # store solution in session for server-side reference if needed
    session["last_solution"] = solution
    return jsonify({"level": level, "puzzle": puzzle, "solution": solution})

if __name__ == "__main__":
    app.run(debug=True)
