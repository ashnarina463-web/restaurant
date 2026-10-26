import os
import sqlite3
from flask import Flask, g, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "books.db")
STATUSES = ("to-read", "reading", "finished")

app = Flask(__name__, static_folder="static")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'to-read',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/books")
def list_books():
    rows = get_db().execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/books")
def add_book():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    if not title:
        return jsonify(error="Enter a title to add a book."), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO books (title, author) VALUES (?, ?)", (title, author)
    )
    db.commit()
    row = db.execute("SELECT * FROM books WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.patch("/api/books/<int:book_id>")
def update_book(book_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in STATUSES:
        return jsonify(error=f"Status must be one of: {', '.join(STATUSES)}."), 400
    db = get_db()
    cur = db.execute("UPDATE books SET status = ? WHERE id = ?", (status, book_id))
    db.commit()
    if cur.rowcount == 0:
        return jsonify(error="Book not found."), 404
    row = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.delete("/api/books/<int:book_id>")
def delete_book(book_id):
    db = get_db()
    cur = db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    db.commit()
    if cur.rowcount == 0:
        return jsonify(error="Book not found."), 404
    return "", 204


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)