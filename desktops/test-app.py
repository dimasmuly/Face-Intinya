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
    # Hapus isi json file ketika reset
    if os.path.exists(json_file):
        with open(json_file, 'w') as f:
            json.dump({}, f)
    face_encodings = load_encodings_from_json()
    face_encodings[id] = {"encoding": encoding.tolist(), "name": name, "image_path": image_path, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
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

        # Reset button
        self.reset_button = tk.Button(window, text="Reset", command=self.reset_app)
        self.reset_button.pack(pady=10)

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

                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
            self.canvas.imgtk = imgtk

        self.window.after(10, self.update_frame)

    def switch_camera(self):
        self.restart_camera()

    def reset_app(self):
        global known_face_encodings, known_face_ids, employee_status
        known_face_encodings = []
        known_face_ids = []
        employee_status = {}

        def reset_task():
            try:
                self.process_new_images()
                messagebox.showinfo("Info", "Application has been reset")
                tkinter_app.status_label.config(text="Application has been reset at " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            except Exception as e:
                print(f"Error resetting application: {e}")

        tkinter_app.window.after(0, reset_task)

def run_flask_app():
    app = Flask(__name__)

    @app.route('/reset', methods=['POST'])
    def reset():
        try:
            # reset app on class FaceRecognitionApp
            tkinter_app.reset_app()
            return jsonify({"message": "Application has been reset"}), 200
        except Exception as e:
            print(f"Error handling /reset request: {e}")
            return jsonify({"error": "Failed to reset application"}), 500

    app.run(port=5000, debug=False, host='0.0.0.0')

def start_flask_server():
    threading.Thread(target=run_flask_app, daemon=True).start()

def get_local_ipv4():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    return local_ip

def notify_ip_change(ip):
    url = f"http://{ip}:8081/save_ip"
    data ={
        "ip": get_local_ipv4(),
        "port": "5000",
        "device_id": DEVICE_ID
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        print(response.json())
    except requests.RequestException as e:
        print(f"Error sending IP change notification: {e}")

def monitor_ip_change():
    current_ip = get_local_ipv4()
    notify_ip_change(current_ip)
    while True:
        time.sleep(10)  # Check every 10 seconds
        new_ip = get_local_ipv4()
        if new_ip != current_ip:
            current_ip = new_ip
            print("IP address has changed:", current_ip)
            notify_ip_change(current_ip)

local_ip = get_local_ipv4()
notify_ip_change(local_ip)

# Membuat aplikasi Tkinter
root = tk.Tk()
root.title("Face Recognition App")
root.geometry("600x700")

# Mulai server Flask
start_flask_server()

# Mulai monitoring perubahan IP
threading.Thread(target=monitor_ip_change, daemon=True).start()

tkinter_app = FaceRecognitionApp(root)
root.mainloop()