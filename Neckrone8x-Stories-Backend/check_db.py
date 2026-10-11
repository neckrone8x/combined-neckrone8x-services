import sqlite3
import os

databases = [
    "stories.db",
    os.path.join("instance", "stories.db")
]

for database in databases:

    print()
    print("=" * 50)
    print("DATABASE:", os.path.abspath(database))
    print("=" * 50)

    if not os.path.exists(database):
        print("MISSING")
        continue

    connection = sqlite3.connect(database)

    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    print("TABLES:", tables)

    try:

        stories = connection.execute(
            "SELECT id, title, published, read_count FROM story"
        ).fetchall()

        print("STORIES:", stories)

    except Exception as error:

        print("ERROR:", error)

    connection.close()