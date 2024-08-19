import sqlite3

# Initialize database
conn = sqlite3.connect('./desktops/db/face_recognition.db')
cursor = conn.cursor()

# rollback database
cursor.execute("DROP TABLE IF EXISTS customers")
cursor.execute("DROP TABLE IF EXISTS counters")


# Create tables if they don't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT UNIQUE PRIMARY KEY,
    encoding BLOB,
    gender TEXT,
    age INTEGER,
    time TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS counters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT,
    expression TEXT,
    time TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
)''')

conn.commit()
conn.close()
