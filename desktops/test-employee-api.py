import cv2
import face_recognition
import json
import os
import requests
from datetime import datetime
import uuid
from tkinter import messagebox

DEVICE_ID = 'device-003'
DEVICE_BOOL = True

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
def save_encodings_to_json(id, encoding, image_path):
    data = {
        "encoding": encoding.tolist(),  # Convert encoding to list for JSON serialization
        "time": datetime.now().isoformat(),
        "path_image": image_path
    }

    face_encodings = load_encodings_from_json()
    face_encodings[id] = data

    with open(json_file, 'w') as f:
        json.dump(face_encodings, f, indent=4)

# Fungsi untuk mengambil gambar dari API
def fetch_image_from_api():
    url = 'http://localhost:8081/image/' + DEVICE_ID
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['device_id'] != DEVICE_ID:
            # message box with error tkinter
            messagebox.showerror('Error', 'Invalid device ID')
            exit()  
            return None
        image_url = data['link']
        image_response = requests.get(image_url)
        if image_response.status_code == 200:
            # Simpan gambar yang diunduh
            image_path = os.path.join('./desktops/employees/', os.path.basename(image_url))
            # Selain file yang terbaca maka file lainnya dihapus
            for file in os.listdir('./desktops/employees/'):
                if file != os.path.basename(image_url):
                    os.remove(os.path.join('./desktops/employees/', file))

            with open(image_path, 'wb') as f:
                f.write(image_response.content)
            return image_path
    return None

# Memuat encoding wajah dari file JSON
face_encodings = load_encodings_from_json()
for face_id, data in face_encodings.items():
    known_face_encodings.append(data["encoding"])
    known_face_ids.append(face_id)

# Mengambil gambar dari API dan memprosesnya
image_path = fetch_image_from_api()
print(image_path)
if image_path:
    # Generate a unique ID for each face
    face_id = str(uuid.uuid4())
    # Muat gambar dan ambil encoding
    image = face_recognition.load_image_file(image_path)
    encoding = face_recognition.face_encodings(image)
    if encoding:  # Pastikan ada encoding yang ditemukan
        encoding = encoding[0]
        if encoding.tolist() not in [data["encoding"] for data in face_encodings.values()]:
            known_face_encodings.append(encoding)
            known_face_ids.append(face_id)
            # Simpan encoding ke file JSON
            save_encodings_to_json(face_id, encoding, image_path)

# Inisialisasi webcam
cap = cv2.VideoCapture(1)

# Dictionary untuk melacak status karyawan (masuk/keluar)
employee_status = {face_id: "out" for face_id in known_face_ids}

# Tentukan batas area dalam frame (contoh: batas atas kiri dan batas bawah kanan)
frame_top_left = (150, 150)  # Koordinat titik atas kiri
frame_bottom_right = (400, 400)  # Koordinat titik bawah kanan

def save_log(data):
    log_file = './desktops/json/employee-counter.json'
    logs = []

    # Load existing logs if the file exists
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []

    logs.append(data)

    # Save updated logs to JSON file
    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=4)

while True:
    ret, frame = cap.read()

    # Gambar batas area dalam frame
    cv2.rectangle(frame, frame_top_left, frame_bottom_right, (255, 0, 0), 2)  # Warna biru, ketebalan 2

    # Temukan lokasi dan encoding wajah dalam frame
    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
        # Hitung titik tengah wajah
        face_center = (left + (right - left) // 2, top + (bottom - top) // 2)

        # Cocokkan encoding wajah dengan data yang dikenal yang terdaftar. Yang tidak terdaftar akan dianggap sebagai tamu/customer.
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"  # Default name if no match is found

        # Jika ada kecocokan, gunakan ID yang sesuai
        if True in matches:
            first_match_index = matches.index(True)
            face_id = known_face_ids[first_match_index]
            name = face_id

            # Periksa apakah titik tengah wajah berada di dalam batas area frame
            if (frame_top_left[0] < face_center[0] < frame_bottom_right[0] and
                frame_top_left[1] < face_center[1] < frame_bottom_right[1]):
                if employee_status[face_id] == "out":
                    employee_status[face_id] = "in"
                    log_data = {
                        "id": face_id,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": "in"
                    }
                    save_log(log_data)
            else:
                if employee_status[face_id] == "in":
                    employee_status[face_id] = "out"
                    log_data = {
                        "id": face_id,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": "out"
                    }
                    save_log(log_data)

        # Gambar kotak di sekitar wajah
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)

        # Tampilkan ID di atas kotak wajah
        cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Tampilkan frame
    cv2.imshow('Video', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
