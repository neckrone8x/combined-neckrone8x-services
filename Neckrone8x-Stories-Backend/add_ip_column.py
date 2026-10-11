import sqlite3


DB_NAME = "stories.db"


connection = sqlite3.connect(DB_NAME)

cursor = connection.cursor()


# Check existing columns

columns = cursor.execute(
    "PRAGMA table_info(story_reads)"
).fetchall()


column_names = [
    column[1]
    for column in columns
]


if "ip_address" not in column_names:

    cursor.execute(
        """
        ALTER TABLE story_reads
        ADD COLUMN ip_address VARCHAR(45)
        """
    )

    connection.commit()

    print("ip_address column added successfully.")

else:

    print("ip_address column already exists.")


connection.close()