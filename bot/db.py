"""SQLite: ученик, прогресс по темам, ошибки, сообщения."""
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS student(
  tg_id INTEGER PRIMARY KEY, name TEXT, goal TEXT, created_at REAL,
  onboarding TEXT DEFAULT 'name', current_topic TEXT DEFAULT 'fractions_add', lang TEXT DEFAULT 'uz');
CREATE TABLE IF NOT EXISTS topic_progress(
  student_id INTEGER, topic TEXT, stage TEXT DEFAULT 'explain', attempts INTEGER DEFAULT 0,
  wrong_explanations INTEGER DEFAULT 0, wrong_streak INTEGER DEFAULT 0,
  bobr_belief TEXT DEFAULT '', passed INTEGER DEFAULT 0, task_idx INTEGER DEFAULT 0,
  hint_level INTEGER DEFAULT 0, humo_active INTEGER DEFAULT 0, last_score TEXT DEFAULT '',
  PRIMARY KEY(student_id, topic));
CREATE TABLE IF NOT EXISTS mistakes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, topic TEXT, kind TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, role TEXT, persona TEXT, text TEXT, ts REAL);
"""


class DB:
    def __init__(self, path: str = ":memory:"):
        self.c = sqlite3.connect(path)
        self.c.row_factory = sqlite3.Row
        self.c.executescript(SCHEMA)
        self.c.commit()

    # --- ученик
    def get_student(self, tg_id: int):
        return self.c.execute("SELECT * FROM student WHERE tg_id=?", (tg_id,)).fetchone()

    def create_student(self, tg_id: int):
        self.c.execute("INSERT OR IGNORE INTO student(tg_id, created_at) VALUES(?,?)", (tg_id, time.time()))
        self.c.commit()
        return self.get_student(tg_id)

    def update_student(self, tg_id: int, **kw):
        if not kw:
            return
        sets = ",".join(f"{k}=?" for k in kw)
        self.c.execute(f"UPDATE student SET {sets} WHERE tg_id=?", (*kw.values(), tg_id))
        self.c.commit()

    def delete_student(self, tg_id: int):
        for t in ("topic_progress", "mistakes", "messages"):
            self.c.execute(f"DELETE FROM {t} WHERE student_id=?", (tg_id,))
        self.c.execute("DELETE FROM student WHERE tg_id=?", (tg_id,))
        self.c.commit()

    # --- прогресс
    def get_progress(self, tg_id: int, topic: str):
        self.c.execute("INSERT OR IGNORE INTO topic_progress(student_id, topic) VALUES(?,?)", (tg_id, topic))
        self.c.commit()
        return self.c.execute("SELECT * FROM topic_progress WHERE student_id=? AND topic=?", (tg_id, topic)).fetchone()

    def update_progress(self, tg_id: int, topic: str, **kw):
        sets = ",".join(f"{k}=?" for k in kw)
        self.c.execute(f"UPDATE topic_progress SET {sets} WHERE student_id=? AND topic=?", (*kw.values(), tg_id, topic))
        self.c.commit()

    def reset_progress(self, tg_id: int, topic: str):
        self.c.execute("DELETE FROM topic_progress WHERE student_id=? AND topic=?", (tg_id, topic))
        self.c.commit()
        return self.get_progress(tg_id, topic)

    # --- ошибки и сообщения
    def add_mistake(self, tg_id: int, topic: str, kind: str):
        self.c.execute("INSERT INTO mistakes(student_id, topic, kind, ts) VALUES(?,?,?,?)", (tg_id, topic, kind, time.time()))
        self.c.commit()

    def mistakes_summary(self, tg_id: int):
        return self.c.execute(
            "SELECT topic, kind, COUNT(*) n FROM mistakes WHERE student_id=? GROUP BY topic, kind ORDER BY n DESC", (tg_id,)
        ).fetchall()

    def add_message(self, tg_id: int, role: str, persona: str, text: str):
        self.c.execute("INSERT INTO messages(student_id, role, persona, text, ts) VALUES(?,?,?,?,?)",
                       (tg_id, role, persona, text, time.time()))
        self.c.commit()

    def last_messages(self, tg_id: int, n: int = 8):
        rows = self.c.execute("SELECT role, persona, text FROM messages WHERE student_id=? ORDER BY id DESC LIMIT ?",
                              (tg_id, n)).fetchall()
        return list(reversed(rows))

    def all_progress(self, tg_id: int):
        return self.c.execute("SELECT * FROM topic_progress WHERE student_id=?", (tg_id,)).fetchall()
