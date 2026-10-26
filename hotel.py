"""
Mkwaju Bay Hotel - full-stack Flask site in ONE file.

Run:
    pip install flask
    python app.py
Open http://127.0.0.1:5000   |   Admin: http://127.0.0.1:5000/admin

Set ADMIN_PASSWORD and SECRET_KEY environment variables before going live.
Edit HOTEL below to rebrand. Rooms are seeded in seed() on the first run.
"""
import os, sqlite3, secrets, string
from datetime import date, datetime, timedelta
from flask import (Flask, request, session, redirect, url_for, render_template,
                   flash, g, abort, jsonify)
from jinja2 import DictLoader

HOTEL = dict(name="Mkwaju Bay Hotel", place="Diani Beach, Kenya",
             phone="+254 700 000 000", email="stay@mkwajubay.example",
             address="Beach Road, Diani, Kwale County", currency="KES")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hotel.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
print("Vivian")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ---------------------------------------------------------------- database
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    c = g.pop("db", None)
    if c: c.close()

def q(sql, args=(), one=False):
    rows = db().execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows

def run(sql, args=()):
    cur = db().execute(sql, args); db().commit(); return cur

def init_db():
    c = sqlite3.connect(DB)
    c.executescript("""
    create table if not exists rooms(id integer primary key, name text, blurb text,
        price integer, qty integer, sleeps integer, hue integer);
    create table if not exists bookings(id integer primary key, ref text unique,
        room_id integer, name text, email text, phone text, check_in text,
        check_out text, guests integer, total integer,
        status text default 'confirmed', created text);
    create table if not exists messages(id integer primary key, name text,
        email text, body text, created text);""")
    if not c.execute("select count(*) from rooms").fetchone()[0]:
        c.executemany("insert into rooms(name,blurb,price,qty,sleeps,hue) values(?,?,?,?,?,?)", [
            ("Garden Room", "Quiet room under the palms with a private veranda and king bed.", 9500, 8, 2, 150),
            ("Ocean View Room", "First-floor balcony facing the reef, with sunrise over the water.", 14500, 6, 2, 190),
            ("Family Suite", "Two bedrooms, a lounge and a kitchenette, 30 seconds from the sand.", 22000, 3, 5, 30),
            ("Beach Villa", "Standalone villa with a plunge pool, outdoor shower and a private path to the beach.", 38000, 2, 4, 340)])
        c.commit()
    c.close()

# ------------------------------------------------------------------ helpers
def pd(s):
    try: return datetime.strptime(s or "", "%Y-%m-%d").date()
    except ValueError: return None

def valid_range(a, b):
    return bool(a and b and a >= date.today() and b > a and (b - a).days <= 30)

def free_units(room, a, b):
    rows = q("select check_in,check_out from bookings where room_id=? and status='confirmed' "
             "and check_in<? and check_out>?", (room["id"], b.isoformat(), a.isoformat()))
    worst, d = 0, a
    while d < b:
        n = sum(1 for r in rows if r["check_in"] <= d.isoformat() < r["check_out"])
        worst = max(worst, n); d += timedelta(1)
    return room["qty"] - worst

def make_ref():
    return "MB-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

def token():
    session.setdefault("t", secrets.token_hex(16)); return session["t"]

app.jinja_env.globals.update(token=token, H=HOTEL, today=lambda: date.today().isoformat(),
                             tomorrow=lambda: (date.today() + timedelta(1)).isoformat())

@app.before_request
def csrf():
    if request.method == "POST":
        sent = request.form.get("t", "").encode()
        if not secrets.compare_digest(session.get("t", "").encode(), sent): abort(400)

def admin_only(f):
    from functools import wraps
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"): return redirect(url_for("admin_login"))
        return f(*a, **k)
    return w

# ------------------------------------------------------------------- routes
@app.route("/")
def index():
    return render_template("home.html", rooms=q("select * from rooms"))

@app.route("/rooms")
def rooms():
    a, b = pd(request.args.get("check_in")), pd(request.args.get("check_out"))
    guests = request.args.get("guests", "2")
    items, nights = [], 0
    if a or b:
        if not valid_range(a, b):
            flash("Choose a check-in from today onward and a check-out after it (30 nights maximum).")
            a = b = None
    if a and b:
        nights = (b - a).days
    for r in q("select * from rooms order by price"):
        free = free_units(r, a, b) if nights else None
        items.append(dict(r=r, free=free))
    return render_template("rooms.html", items=items, a=a, b=b, nights=nights, guests=guests)

@app.route("/api/availability")
def api_availability():
    a, b = pd(request.args.get("check_in")), pd(request.args.get("check_out"))
    if not valid_range(a, b): return jsonify(error="Invalid dates"), 400
    return jsonify([dict(room=r["name"], available=free_units(r, a, b),
                         total=r["price"] * (b - a).days) for r in q("select * from rooms")])

@app.route("/book", methods=["GET", "POST"])
def book():
    src = request.form if request.method == "POST" else request.args
    room = q("select * from rooms where id=?", (src.get("room", type=int),), one=True)
    a, b = pd(src.get("check_in")), pd(src.get("check_out"))
    if not room or not valid_range(a, b):
        flash("Pick your dates first, then choose a room."); return redirect(url_for("rooms"))
    nights, total = (b - a).days, room["price"] * (b - a).days
    if request.method == "POST":
        f = {k: request.form.get(k, "").strip() for k in ("name", "email", "phone")}
        guests = request.form.get("guests", type=int) or 1
        if not f["name"] or "@" not in f["email"] or len(f["phone"]) < 6:
            flash("Enter your name, a valid email and a phone number.")
        elif guests < 1 or guests > room["sleeps"]:
            flash(f"The {room['name']} sleeps up to {room['sleeps']} guests.")
        elif free_units(room, a, b) < 1:
            flash("Sorry, that room was just taken for those dates. Try other dates or a different room.")
            return redirect(url_for("rooms", check_in=a, check_out=b))
        else:
            ref = make_ref()
            run("insert into bookings(ref,room_id,name,email,phone,check_in,check_out,guests,total,created) "
                "values(?,?,?,?,?,?,?,?,?,?)", (ref, room["id"], f["name"], f["email"], f["phone"],
                a.isoformat(), b.isoformat(), guests, total, datetime.now().isoformat(timespec="minutes")))
            return redirect(url_for("confirmation", ref=ref))
    return render_template("book.html", room=room, a=a, b=b, nights=nights, total=total,
                           guests=src.get("guests", "2"))

BOOKING = ("select b.*, r.name room from bookings b join rooms r on r.id=b.room_id ")

@app.route("/booking/<ref>")
def confirmation(ref):
    bk = q(BOOKING + "where ref=?", (ref,), one=True) or abort(404)
    return render_template("confirm.html", b=bk)

@app.route("/manage", methods=["GET", "POST"])
def manage():
    bk = None
    if request.method == "POST":
        ref, email = request.form.get("ref", "").strip().upper(), request.form.get("email", "").strip().lower()
        bk = q(BOOKING + "where ref=? and lower(email)=?", (ref, email), one=True)
        if not bk: flash("No booking matches that reference and email.")
        elif request.form.get("cancel") and bk["status"] == "confirmed":
            run("update bookings set status='cancelled' where id=?", (bk["id"],))
            flash("Your booking has been cancelled.")
            bk = q(BOOKING + "where id=?", (bk["id"],), one=True)
    return render_template("manage.html", b=bk)

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        n, e, m = (request.form.get(k, "").strip() for k in ("name", "email", "body"))
        if n and "@" in e and m:
            run("insert into messages(name,email,body,created) values(?,?,?,?)",
                (n, e, m, datetime.now().isoformat(timespec="minutes")))
            flash("Thanks, we received your message and will reply within a day.")
            return redirect(url_for("contact"))
        flash("Fill in your name, a valid email and a message.")
    return render_template("contact.html")

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", "").encode(), ADMIN_PASSWORD.encode()):
            session["admin"] = True; return redirect(url_for("dashboard"))
        flash("Wrong password.")
    return render_template("login.html")

@app.route("/admin/dashboard")
@admin_only
def dashboard():
    return render_template("admin.html", bookings=q(BOOKING + "order by b.id desc"),
                           messages=q("select * from messages order by id desc"),
                           stats=q("select count(*) n, coalesce(sum(total),0) t from bookings "
                                   "where status='confirmed'", one=True))

@app.post("/admin/cancel/<int:i>")
@admin_only
def admin_cancel(i):
    run("update bookings set status='cancelled' where id=?", (i,))
    return redirect(url_for("dashboard"))

@app.post("/admin/logout")
def logout():
    session.pop("admin", None); return redirect(url_for("index"))

# ---------------------------------------------------------------- templates
CSS = """
:root{--ink:#14232b;--lagoon:#0e5a63;--deep:#093b42;--mist:#f4f8f7;--sand:#e3d6b4;--coral:#e0485b;--line:#d5e0de;color-scheme:light}
@media(prefers-color-scheme:dark){:root{--ink:#e7f0ee;--mist:#0d1a1e;--line:#26393e;--sand:#8c7f5c;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;font:17px/1.6 Figtree,system-ui,sans-serif;background:var(--mist);color:var(--ink)}
h1,h2,h3{font-family:'Bricolage Grotesque',Georgia,serif;line-height:1.1;margin:0 0 .5em;letter-spacing:-.01em}
h1{font-size:clamp(2.4rem,6vw,4.4rem)}h2{font-size:clamp(1.6rem,3.5vw,2.4rem)}a{color:inherit}
.wrap{max-width:1080px;margin:auto;padding:0 20px}.muted{opacity:.7}
nav{display:flex;justify-content:space-between;align-items:center;padding:16px 0;flex-wrap:wrap;gap:8px}
nav b{font:700 1.25rem 'Bricolage Grotesque',serif}nav a{margin-left:18px;text-decoration:none}nav a:hover{text-decoration:underline}
.hero{background:var(--deep);color:#f4f8f7;position:relative;padding-bottom:90px}.hero nav a,.hero nav b{color:#f4f8f7}
.hero p{max-width:46ch;font-size:1.15rem;opacity:.9}.hero .wrap{padding-top:10px}.hero h1{margin-top:60px;max-width:13ch}
.wave{position:absolute;bottom:-1px;left:0;width:100%;height:60px;display:block}
.search{display:flex;flex-wrap:wrap;gap:12px;align-items:end;background:var(--mist);color:var(--ink);padding:18px;border-radius:14px;margin-top:30px;box-shadow:0 12px 30px #0006}
.search label,.f label{display:flex;flex-direction:column;font-size:.85rem;gap:4px;flex:1;min-width:130px}
input,select,textarea{font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--mist);color:var(--ink)}
.btn{font:600 1rem Figtree,sans-serif;background:var(--coral);color:#fff;border:0;border-radius:8px;padding:12px 22px;cursor:pointer;text-decoration:none;display:inline-block}
.btn.alt{background:transparent;color:var(--ink);border:1px solid var(--line)}.btn:focus-visible,input:focus-visible,a:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid var(--coral);outline-offset:2px}
section{padding:56px 0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:22px}
.room{border:1px solid var(--line);border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
.room svg{width:100%;height:auto;display:block}.room div{padding:16px;display:flex;flex-direction:column;gap:6px;flex:1}
.room p{margin:0;font-size:.95rem}.price{font:700 1.3rem 'Bricolage Grotesque',serif}.spacer{flex:1}
.two{display:grid;grid-template-columns:1fr 1fr;gap:40px}@media(max-width:700px){.two{grid-template-columns:1fr}}
ul.clean{list-style:none;padding:0;margin:0}ul.clean li{padding:9px 0;border-bottom:1px solid var(--line)}
.flash{background:var(--sand);color:#14232b;padding:12px 16px;border-radius:8px;margin:16px 0}
.f{display:grid;gap:14px;max-width:520px}.f textarea{min-height:130px}
table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
.tbl{overflow-x:auto}.tag{padding:2px 8px;border-radius:99px;border:1px solid var(--line);font-size:.8rem}
footer{border-top:1px solid var(--line);padding:30px 0;font-size:.9rem}
"""

MACROS = """
{% macro art(h) %}<svg viewBox="0 0 400 220" role="img" aria-label="Illustration of the room view"><defs><linearGradient id="g{{h}}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="hsl({{h}} 60% 82%)"/><stop offset="1" stop-color="hsl({{h}} 55% 55%)"/></linearGradient></defs><rect width="400" height="220" fill="url(#g{{h}})"/><circle cx="310" cy="70" r="28" fill="hsl({{h}} 90% 94%)"/><path d="M0 150Q50 130 100 150T200 150T300 150T400 150V220H0Z" fill="hsl({{h}} 50% 35%)" opacity=".55"/><path d="M0 180Q50 160 100 180T200 180T300 180T400 180V220H0Z" fill="hsl({{h}} 55% 22%)"/></svg>{% endmacro %}
{% macro card(r, free=None, a=None, b=None, nights=0, guests=2) %}
<article class="room">{{ art(r.hue) }}<div><h3>{{ r.name }}</h3><p>{{ r.blurb }}</p>
<p class="muted">Sleeps {{ r.sleeps }}</p><span class="spacer"></span>
<span class="price">{{ H.currency }} {{ '{:,}'.format(r.price) }} <small class="muted">/ night</small></span>
{% if free is none %}<a class="btn alt" href="{{ url_for('rooms') }}">Check dates</a>
{% elif free > 0 %}<p>{{ nights }} night{{ 's' if nights > 1 }}: <b>{{ H.currency }} {{ '{:,}'.format(r.price*nights) }}</b>{% if free < 3 %} <span class="tag">{{ free }} left</span>{% endif %}</p>
<a class="btn" href="{{ url_for('book', room=r.id, check_in=a, check_out=b, guests=guests) }}">Book this room</a>
{% else %}<p><b>Sold out for these dates</b></p>{% endif %}</div></article>{% endmacro %}
"""

BASE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{% block title %}{{ H.name }}{% endblock %}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=Figtree:wght@400;600&display=swap" rel="stylesheet">
<style>{{ css|safe }}</style></head><body>
{% block top %}<div class="wrap"><nav><b>{{ H.name }}</b><span>{% include 'links.html' %}</span></nav></div>{% endblock %}
<main class="wrap">{% for m in get_flashed_messages() %}<div class="flash" role="alert">{{ m }}</div>{% endfor %}
{% block body %}{% endblock %}</main>
<footer><div class="wrap">{{ H.name }} &middot; {{ H.address }} &middot; <a href="tel:{{ H.phone }}">{{ H.phone }}</a> &middot; <a href="mailto:{{ H.email }}">{{ H.email }}</a></div></footer>
</body></html>"""

LINKS = """<a href="{{ url_for('rooms') }}">Rooms</a><a href="{{ url_for('index') }}#dining">Dining</a><a href="{{ url_for('manage') }}">My booking</a><a href="{{ url_for('contact') }}">Contact</a>"""

SEARCH = """<form class="search" action="{{ url_for('rooms') }}"><label>Check in<input type="date" name="check_in" min="{{ today() }}" value="{{ a or today() }}" required></label>
<label>Check out<input type="date" name="check_out" min="{{ tomorrow() }}" value="{{ b or tomorrow() }}" required></label>
<label>Guests<select name="guests">{% for n in range(1,7) %}<option {{ 'selected' if guests|string==n|string or (not guests and n==2) }}>{{ n }}</option>{% endfor %}</select></label>
<button class="btn">See availability</button></form>"""

HOME = """{% extends 'base.html' %}{% from 'm.html' import card %}
{% block top %}<div class="hero"><div class="wrap"><nav><b>{{ H.name }}</b><span>{% include 'links.html' %}</span></nav>
<h1>Wake up to the Indian Ocean.</h1><p>Forty rooms and villas on a white-sand beach at {{ H.place }}. Book direct and get breakfast included.</p>
{% set a=none %}{% set b=none %}{% set guests='2' %}{% include 'search.html' %}</div>
<svg class="wave" viewBox="0 0 1200 60" preserveAspectRatio="none" aria-hidden="true"><path d="M0 30Q150 0 300 30T600 30T900 30T1200 30V60H0Z" fill="var(--mist)"/></svg></div>{% endblock %}
{% block body %}<section><h2>Rooms and villas</h2><div class="grid">{% for r in rooms %}{{ card(r) }}{% endfor %}</div></section>
<section class="two"><div><h2>On the property</h2><ul class="clean"><li>Tide pool and a 25 m lap pool</li><li>Spa with massage and sauna</li><li>Dive and snorkel desk with boat trips to the reef</li><li>Airport transfers, arranged on request</li><li>Free Wi-Fi throughout</li></ul></div>
<div id="dining"><h2>Dining</h2><p>The Tamarind Kitchen cooks Swahili coast food over charcoal: coconut fish curry, pilau, grilled octopus and fresh mandazi at breakfast.</p>
<p class="muted">Breakfast 7:00 to 10:30, lunch 12:30 to 15:00, dinner 18:30 to 22:00.</p><a class="btn alt" href="{{ url_for('contact') }}">Ask about a table</a></div></section>{% endblock %}"""

ROOMS = """{% extends 'base.html' %}{% from 'm.html' import card %}
{% block title %}Rooms - {{ H.name }}{% endblock %}
{% block body %}<section><h2>{{ 'Available rooms' if nights else 'Rooms and villas' }}</h2>{% include 'search.html' %}
{% if nights %}<p class="muted">{{ a }} to {{ b }}, {{ nights }} night{{ 's' if nights > 1 }}</p>{% endif %}
<div class="grid" style="margin-top:24px">{% for i in items %}{{ card(i.r, i.free, a, b, nights, guests) }}{% endfor %}</div></section>{% endblock %}"""

BOOK = """{% extends 'base.html' %}{% block title %}Book {{ room.name }}{% endblock %}
{% block body %}<section class="two"><div><h2>Your details</h2><form class="f" method="post"><input type="hidden" name="t" value="{{ token() }}">
<input type="hidden" name="room" value="{{ room.id }}"><input type="hidden" name="check_in" value="{{ a }}"><input type="hidden" name="check_out" value="{{ b }}">
<label>Full name<input name="name" value="{{ request.form.name }}" required autocomplete="name"></label>
<label>Email<input type="email" name="email" value="{{ request.form.email }}" required autocomplete="email"></label>
<label>Phone<input name="phone" value="{{ request.form.phone }}" required autocomplete="tel"></label>
<label>Guests (up to {{ room.sleeps }})<input type="number" name="guests" min="1" max="{{ room.sleeps }}" value="{{ guests }}" required></label>
<button class="btn">Confirm booking</button></form></div>
<div><h2>{{ room.name }}</h2><p>{{ a }} to {{ b }}, {{ nights }} night{{ 's' if nights > 1 }}</p>
<p class="price">{{ H.currency }} {{ '{:,}'.format(total) }}</p><p class="muted">Pay at the hotel. Free cancellation any time before arrival.</p></div></section>{% endblock %}"""

CONFIRM = """{% extends 'base.html' %}{% block body %}<section><h2>Booking confirmed</h2>
<p>Keep your reference: <b class="price">{{ b.ref }}</b></p>
<ul class="clean"><li>{{ b.room }} for {{ b.guests }} guest{{ 's' if b.guests > 1 }}</li><li>{{ b.check_in }} to {{ b.check_out }}</li>
<li>Total {{ H.currency }} {{ '{:,}'.format(b.total) }}, payable at the hotel</li><li>Booked under {{ b.name }} ({{ b.email }})</li></ul>
<p><a class="btn alt" href="{{ url_for('manage') }}">View or cancel a booking</a></p></section>{% endblock %}"""

MANAGE = """{% extends 'base.html' %}{% block body %}<section><h2>Find your booking</h2>
<form class="f" method="post"><input type="hidden" name="t" value="{{ token() }}">
<label>Booking reference<input name="ref" placeholder="MB-XXXXXX" required></label>
<label>Email used to book<input type="email" name="email" required></label><button class="btn">Find booking</button>
{% if b and b.status == 'confirmed' %}<hr><ul class="clean"><li>{{ b.room }}, {{ b.check_in }} to {{ b.check_out }}</li><li>{{ H.currency }} {{ '{:,}'.format(b.total) }}</li></ul>
<button class="btn alt" name="cancel" value="1" onclick="return confirm('Cancel this booking?')">Cancel booking</button>
{% elif b %}<p>This booking is <b>{{ b.status }}</b>.</p>{% endif %}</form></section>{% endblock %}"""

CONTACT = """{% extends 'base.html' %}{% block body %}<section class="two"><div><h2>Send us a message</h2>
<form class="f" method="post"><input type="hidden" name="t" value="{{ token() }}"><label>Name<input name="name" required></label>
<label>Email<input type="email" name="email" required></label><label>Message<textarea name="body" required></textarea></label><button class="btn">Send message</button></form></div>
<div><h2>Find us</h2><p>{{ H.address }}<br>{{ H.place }}</p><p>Phone <a href="tel:{{ H.phone }}">{{ H.phone }}</a><br>Email <a href="mailto:{{ H.email }}">{{ H.email }}</a></p>
<p class="muted">Check-in from 14:00, check-out by 11:00. Front desk is open 24 hours.</p></div></section>{% endblock %}"""

LOGIN = """{% extends 'base.html' %}{% block body %}<section><h2>Staff sign in</h2><form class="f" method="post"><input type="hidden" name="t" value="{{ token() }}">
<label>Password<input type="password" name="password" required></label><button class="btn">Sign in</button></form></section>{% endblock %}"""

ADMIN = """{% extends 'base.html' %}{% block body %}<section><h2>Bookings</h2>
<p>{{ stats.n }} confirmed bookings worth {{ H.currency }} {{ '{:,}'.format(stats.t) }}</p>
<div class="tbl"><table><tr><th>Ref<th>Guest<th>Room<th>Dates<th>Total<th>Status<th></tr>
{% for b in bookings %}<tr><td>{{ b.ref }}<td>{{ b.name }}<br><small>{{ b.email }}<br>{{ b.phone }}</small><td>{{ b.room }} x{{ b.guests }}
<td>{{ b.check_in }} to {{ b.check_out }}<td>{{ '{:,}'.format(b.total) }}<td><span class="tag">{{ b.status }}</span>
<td>{% if b.status == 'confirmed' %}<form method="post" action="{{ url_for('admin_cancel', i=b.id) }}"><input type="hidden" name="t" value="{{ token() }}"><button class="btn alt">Cancel</button></form>{% endif %}</tr>
{% else %}<tr><td colspan="7">No bookings yet.</tr>{% endfor %}</table></div></section>
<section><h2>Messages</h2>{% for m in messages %}<p><b>{{ m.name }}</b> ({{ m.email }}, {{ m.created }})<br>{{ m.body }}</p>{% else %}<p>No messages yet.</p>{% endfor %}
<form method="post" action="{{ url_for('logout') }}"><input type="hidden" name="t" value="{{ token() }}"><button class="btn alt">Sign out</button></form></section>{% endblock %}"""

app.jinja_loader = DictLoader({"base.html": BASE, "m.html": MACROS, "links.html": LINKS,
    "search.html": SEARCH, "home.html": HOME, "rooms.html": ROOMS, "book.html": BOOK,
    "confirm.html": CONFIRM, "manage.html": MANAGE, "contact.html": CONTACT,
    "login.html": LOGIN, "admin.html": ADMIN})
app.jinja_env.globals["css"] = CSS

init_db()
if __name__ == "__main__":
    if ADMIN_PASSWORD == "admin123":
        print("Warning: using the default admin password. Set ADMIN_PASSWORD before going live.")
    app.run(debug=True)