# Connect to sqlite.db and create tables
import sqlite3
import bcrypt

def rollback():
    conn = sqlite3.connect("./api/databases/sqlite.db")
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS devices")
    c.execute("DROP TABLE IF EXISTS employees")
    conn.commit()
    conn.close()

def migrate():
    conn = sqlite3.connect("./api/databases/sqlite.db")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT, password TEXT)"""
    )
    # create table devices with column id, device, ip, port, location
    c.execute(
        """CREATE TABLE IF NOT EXISTS devices
                 (id TEXT PRIMARY KEY, device TEXT, ip_address TEXT, port TEXT, location TEXT)"""
    )
    
    # create table employees with column uuid, device_id, name, link
    c.execute(
        """CREATE TABLE IF NOT EXISTS employees
                 (uuid TEXT PRIMARY KEY, device_id TEXT, name TEXT, link TEXT)"""
    )
    conn.commit()
    conn.close()

def seed():
    conn = sqlite3.connect("./api/databases/sqlite.db")
    c = conn.cursor()
    # insert data to users table
    c.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        ("admin", bcrypt.hashpw("password".encode(), bcrypt.gensalt()).decode()),
    )
    # insert data to devices table
    c.execute(
        "INSERT INTO devices (id, device, ip_address, port, location) VALUES (?, ?, ?, ?, ?)",
        ("device-001", "device-001", "192.0.0.1", "8081", "Jakarta"),
    )
    c.execute(
        "INSERT INTO devices (id, device, ip_address, port, location) VALUES (?, ?, ?, ?, ?)",
        ("device-002", "device-002", "192.0.0.1", "8081", "Bandung"),
    )
    c.execute(
        "INSERT INTO devices (id, device, ip_address, port, location) VALUES (?, ?, ?, ?, ?)",
        ("device-003", "device-003", "192.0.0.1", "8081", "Surabaya"),
    )
    # insert data to employees table
    c.execute(
        "INSERT INTO employees (uuid, device_id, name, link) VALUES (?, ?, ?, ?)",
        (
            "123e4567-e89b-12d3-a456-426614174000",
            "device-001",
            "Mochammad Hairullah",
            "images/hoy.jpg",
        ),
    )
    c.execute(
        "INSERT INTO employees (uuid, device_id, name, link) VALUES (?, ?, ?, ?)",
        (
            "123e4567-e89b-12d3-a456-426614174001",
            "device-002",
            "Azizi Azhari",
            "images/Azizi.webp",
        ),
    )
    c.execute(
        "INSERT INTO employees (uuid, device_id, name, link) VALUES (?, ?, ?, ?)",
        (
            "123e4567-e89b-12d3-a456-426614174002",
            "device-003",
            "Freya Jayawardana",
            "images/freya.jpg",
        ),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    rollback()
    migrate()
    seed()
