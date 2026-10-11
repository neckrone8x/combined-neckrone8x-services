import sqlite3

db = sqlite3.connect("stories.db")

tables = db.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

print("TABLES:")

for table in tables:
    print(table[0])

db.close()