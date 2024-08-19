import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import face_recognition
import glob
import json
import os
from datetime import datetime
import uuid
from PIL import Image, ImageTk
from tkinter import filedialog
import threading
import time
import shutil
from flask import Flask, jsonify, request
import socket
import requests
from pygrabber.dshow_graph import FilterGraph
import subprocess

DEVICE_ID = 'device-001'

# Inisialisasi data wajah yang dikenal
known_face_encodings = []
known_face_ids = []

# Path ke file JSON
json_file = './desktops/json/employees.json'

# Fungsi untuk memuat encoding wajah dari file JSON
def load_encodings_from_json():
    face_encodings = {}
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            try:
                face_encodings = json.load(f)
            except json.JSONDecodeError:
                face_encodings = {}
    return face_encodings

# Fungsi untuk menyimpan encoding wajah ke file JSON
def save_encodings_to_json(id, encoding, image_path, name):
    data = {
        "encoding": encoding.tolist(),
        "name": name,
        "time": datetime.now().isoformat(),
        "path_image": image_path
    }

    face_encodings = load_encodings_from_json()
    face_encodings[id] = data

    with open(json_file, 'w') as f:
        json.dump(face_encodings, f, indent=4)

# Memuat encoding wajah dari file JSON
face_encodings = load_encodings_from_json()
for face_id, data in face_encodings.items():
    known_face_encodings.append(data["encoding"])
    known_face_ids.append(face_id)

# Inisialisasi webcam
cap = cv2.VideoCapture(0)

# Dictionary untuk melacak status karyawan (masuk/keluar)
employee_status = {face_id: "out" for face_id in known_face_ids}

# Tentukan batas area dalam frame
frame_top_left = (150, 150)
frame_bottom_right = (400, 400)

def save_log(data):
    log_file = './desktops/json/employee-counter.json'
    logs = []

    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []

    logs.append(data)

    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=4)

class FaceRecognitionApp:
    def __init__(self, window):
        self.window = window
        self.window.title("Face Recognition App")

        self.canvas = tk.Canvas(window, width=640, height=480)
        self.canvas.pack()

        self.camera_info = self.get_available_cameras()
        self.selected_camera_index = 0
        self.selected_camera_name = self.camera_info[self.selected_camera_index]

        self.camera_selection = ttk.Combobox(window, values=list(self.camera_info.values()))
        self.camera_selection.current(0)
        self.camera_selection.pack(pady=10)
        self.camera_selection.bind("<<ComboboxSelected>>", self.on_camera_selected)

        self.camera_label = tk.Label(window, text=f"Selected Camera: {self.selected_camera_name}")
        self.camera_label.pack()

        self.progress_bar = ttk.Progressbar(window, orient="horizontal", mode="indeterminate", length=200)
        self.progress_bar.pack(pady=10)

        self.cap = cv2.VideoCapture(self.selected_camera_index)
        self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

        self.status_label = tk.Label(window, text="")
        self.status_label.pack(pady=10)

        self.update_frame()

    def get_available_cameras(self):
        try:
            devices = FilterGraph().get_input_devices()
            camera_info = {device_index: device_name for device_index, device_name in enumerate(devices)}

        except Exception as e:
            print(f"Error getting available cameras: {e}")
            messagebox.showerror('Error', 'Failed to get available cameras')

        return camera_info
    
    def on_camera_selected(self, event):
        selected_index = self.camera_selection.current()
        if selected_index in self.camera_info:
            if selected_index != self.selected_camera_index:
                self.selected_camera_index = selected_index
                self.selected_camera_name = self.camera_info[selected_index]
                self.camera_label.config(text=f"Selected Camera: {self.selected_camera_name}")
                threading.Thread(target=self.switch_camera).start()
        else:
            messagebox.showerror('Error', 'Selected camera index is out of range')


    def restart_camera(self):
        if self.cap.isOpened():
            self.cap.release()
        self.cap = cv2.VideoCapture(self.selected_camera_index)
        if not self.cap.isOpened():
            print(f"Error: Camera index {self.selected_camera_index} could not be opened.")
            return
        self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    def process_new_images(self):
        # get data with /image/<device_id>
        url = 'http://localhost:8081/image/' + DEVICE_ID
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['device_id'] != DEVICE_ID:
                messagebox.showerror('Error', 'Invalid device ID')
                exit()
                return None
            image_url = data['link']
            image_response = requests.get(image_url)
            if image_response.status_code == 200:
                image_path = os.path.join('./desktops/employees/', os.path.basename(image_url))
                for file in os.listdir('./desktops/employees/'):
                    if file != os.path.basename(image_url):
                        os.remove(os.path.join('./desktops/employees/', file))
                with open(image_path, 'wb') as f:
                    f.write(image_response.content)
                self.add_new_face(image_path, data)
        else:
            print("Error fetching image from API")

    def add_new_face(self, image_path, data):
        face_id = data["uuid"]
        image = face_recognition.load_image_file(image_path)
        encoding = face_recognition.face_encodings(image)
        if encoding:
            encoding = encoding[0]
            if encoding.tolist() not in [data["encoding"] for data in face_encodings.values()]:
                known_face_encodings.append(encoding)
                known_face_ids.append(face_id)
                save_encodings_to_json(face_id, encoding, image_path, data["name"])
                # messagebox.showinfo("Info", "New image has been processed")
                self.restart_camera()
            else:
                messagebox.showinfo("Info", "Image already exists")
        else:
            messagebox.showerror("Error", "No face found in the image")

    def update_frame(self):
        ret, frame = self.cap.read()
        ret, frame = self.cap.read()
            
        if ret:
            cv2.rectangle(frame, frame_top_left, frame_bottom_right, (255, 0, 0), 2)

            face_locations = face_recognition.face_locations(frame)
            face_encodings = face_recognition.face_encodings(frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                face_center = (left + (right - left) // 2, top + (bottom - top) // 2)
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                name = "Unknown"

                if True in matches:
                    first_match_index = matches.index(True)
                    face_id = known_face_ids[first_match_index]
                    name = face_id

                    # get name from json file employees.json
                    get_name_json = load_encodings_from_json()
                    if face_id in get_name_json:
                        name = get_name_json[face_id]["name"]

                    if face_id not in employee_status:
                        employee_status[face_id] = "out"

                    if (frame_top_left[0] < face_center[0] < frame_bottom_right[0] and
                        frame_top_left[1] < face_center[1] < frame_bottom_right[1]):
                        if employee_status[face_id] == "out":
                            employee_status[face_id] = "in"
                            log_data = {
                                "id": face_id,
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "status": "in"
                            }
                            save_log(log_data)
                    else:
                        if employee_status[face_id] == "in":
                            employee_status[face_id] = "out"
                            log_data = {
                                "id": face_id,
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "status": "out"
                            }
                            save_log(log_data)
                            
                    color = (0, 255, 0) if employee_status[face_id] == "in" else (0, 0, 255)
                else:
                    color = (0, 0, 255)

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            self.process_new_images()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(frame))
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

        self.window.after(10, self.update_frame)

# Flask API
app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"message": "API is running"})

@app.route('/image/<device_id>', methods=['POST'])
def receive_image(device_id):
    if device_id != DEVICE_ID:
        return jsonify({"error": "Invalid device ID"}), 400

    try:
        data = request.get_json()
        image_path = data['image_path']
        image_name = image_path.split('/')[-1]

        # Salin file gambar ke direktori tujuan
        destination_path = os.path.join('desktops/employees', image_name)
        shutil.copy(image_path, destination_path)

        return jsonify({"message": "Image received successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Function to start the Flask API
def start_flask_app():
    app.run(port=5000, debug=False, host='0.0.0.0')

# Function to start Ngrok
def start_ngrok():
    command = "ngrok http 5000"
    process = subprocess.Popen(command, shell=True)
    process.wait()

# Function to get the public URL from Ngrok
def get_ngrok_url():
    url = "http://localhost:4040/api/tunnels"
    response = requests.get(url)
    data = response.json()
    public_url = data['tunnels'][0]['public_url']
    return public_url

if __name__ == "__main__":
    window = tk.Tk()

    # Start Flask API in a separate thread
    flask_thread = threading.Thread(target=start_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    # Start Ngrok in a separate thread
    ngrok_thread = threading.Thread(target=start_ngrok)
    ngrok_thread.daemon = True
    ngrok_thread.start()

    # Wait for Ngrok to start and get the public URL
    time.sleep(2)  # Adjust the sleep time if needed
    public_url = get_ngrok_url()
    print(f"Ngrok URL: {public_url}")

    app = FaceRecognitionApp(window)
    window.mainloop()
