from flask import Flask, request, jsonify, send_from_directory, send_file, render_template, flash, session, redirect, url_for
import requests
import os
import bcrypt
import sqlite3

app = Flask(__name__)

# Secret key
app.secret_key = 'secret'

data_json = [
  {
      'uuid': '123e4567-e89b-12d3-a456-426614174000',
      'device_id': 'device-001',
      'name': 'Mochammad Hairullah',
      'link': 'http://localhost:8081/images/hoy.jpg'
  },
  {
      'uuid': '123e4567-e89b-12d3-a456-426614174001',
      'device_id': 'device-002',
      'name': 'Azizi Azhari',
      'link': 'http://localhost:8081/images/Azizi.webp'
  },
  {
      'uuid': '123e4567-e89b-12d3-a456-426614174002',
      'device_id': 'device-003',
      'name': 'Freya Jayawardana',
      'link': 'http://localhost:8081/images/freya.jpg'
  },
]

# Folder untuk menyimpan gambar yang diunggah
UPLOAD_FOLDER = os.path.join('static', 'images')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return 'No image file found', 400

    image = request.files['image']
    # Menyimpan gambar dengan nama yang sama
    image_path = os.path.join(UPLOAD_FOLDER, image.filename)
    image.save(image_path)

    return 'Image uploaded successfully', 200

@app.route('/image', methods=['GET'])
def get_image():
    # Contoh JSON untuk merespons permintaan gambar with 2 data
    image_info = data_json
    return jsonify(image_info)

@app.route('/image/<device_id>', methods=['GET'])
def get_image_by_device_id(device_id):
    # Contoh JSON untuk merespons permintaan gambar with 1 data
    image_info = next((item for item in data_json if item['device_id'] == device_id), None)
    if image_info is None:
        return 'Device ID not found', 404
    return jsonify(image_info)

@app.route('/images/<filename>', methods=['GET'])
def serve_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/trigger_reset', methods=['POST'])
def trigger_reset():
    try:
        # with body ip_address
        ip = request.json.get('ip')
        response = requests.post('http://' + ip + ':5000/reset')
        if response.status_code == 200:
            return jsonify({"message": "Reset successful"}), 200
        else:
            return jsonify({"message": "Reset failed"}), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"message": "Error connecting to Tkinter server", "error": str(e)}), 500

# save IP
@app.route('/save_ip', methods=['POST'])
def save_ip():
    print(request.json)
    try:
        conn = sqlite3.connect("./api/databases/sqlite.db")
        c = conn.cursor()
        # save to database table devices where id 
        c.execute(f"UPDATE devices SET ip_address = '{request.json.get('ip')}', port = '{request.json.get('port')}' WHERE id = '{request.json.get('device_id')}'")
        conn.commit()
        conn.close()
        return jsonify({"message": "IP saved"}), 200
    except Exception as e:
        return jsonify({"message": "Error saving IP", "error": str(e)}), 500

# home page
@app.route('/')
def index():
    return redirect('/login')

# Login page with render template and bcrypt
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("./api/databases/sqlite.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        if user is None:
            # render_template with message
            flash('Username not found', 'danger')
            return render_template('login.html')

        if bcrypt.checkpw(password.encode(), user[2].encode()):
            # set session
            session['username'] = username
            return redirect('/home')
        else:
            # render template with message
            flash('Wrong password', 'danger')
            return render_template('login.html')

    if 'username' in session:
        return redirect('/home')
    else:
        return render_template('login.html')

# Home page with session
@app.route('/home', methods=['GET'])
def home():
    if 'username' in session:
        return render_template('home.html')
    else:
        return redirect('/login')

# Logout with session
@app.route('/logout', methods=['GET'])
def logout():
    session.pop('username', None)
    return redirect('/login')

# device page with session crud
@app.route('/devices', methods=['GET', 'POST'])
def device():
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect("./api/databases/sqlite.db")
    c = conn.cursor()

    if request.method == 'POST':
        device = request.form['device']
        ip_address = request.form['ip_address']
        port = request.form['port']
        location = request.form['location']
        c.execute(
            "INSERT INTO devices (id, device, ip_address, port, location) VALUES (?, ?, ?, ?, ?)",
            (device, device, ip_address, port, location),
        )
        conn.commit()

    c.execute("SELECT * FROM devices")
    devices = c.fetchall()
    conn.close()

    return render_template('device.html', devices=devices)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8081)
