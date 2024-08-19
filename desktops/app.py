import tkinter as tk
from tkinter import ttk
import cv2
import face_recognition
import glob
import json
import os
from datetime import datetime
import uuid
from PIL import Image, ImageTk
from tkinter import filedialog
import time
import threading
import shutil  # Import shutil for file operations

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

# Memuat encoding wajah dari file JSON
face_encodings = load_encodings_from_json()
for face_id, data in face_encodings.items():
    known_face_encodings.append(data["encoding"])
    known_face_ids.append(face_id)

# Mengambil path gambar dari direktori ./desktops/employees/ dengan berbagai ekstensi gambar
image_files = glob.glob('./desktops/employees/*.jpg') + glob.glob('./desktops/employees/*.jpeg') + glob.glob('./desktops/employees/*.png') + glob.glob('./desktops/employees/*.webp')

# Memuat encoding wajah dari gambar baru yang belum ada di file JSON
for image_path in image_files:
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
cap = cv2.VideoCapture(0)

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

class FaceRecognitionApp:
    def __init__(self, window):
        self.window = window
        self.window.title("Face Recognition App")

        self.canvas = tk.Canvas(window, width=640, height=480)
        self.canvas.pack()

        # Get list of available cameras and their names
        self.camera_info = self.get_available_cameras()
        self.selected_camera_index = 0
        self.selected_camera_name = self.camera_info[self.selected_camera_index]

        # Create combobox for camera selection
        self.camera_selection = ttk.Combobox(window, values=list(self.camera_info.values()))
        self.camera_selection.current(0)
        self.camera_selection.pack(pady=10)
        self.camera_selection.bind("<<ComboboxSelected>>", self.on_camera_selected)

        # Label to display current camera name
        self.camera_label = tk.Label(window, text=f"Selected Camera: {self.selected_camera_name}")
        self.camera_label.pack()

        # Progress bar for camera switching
        self.progress_bar = ttk.Progressbar(window, orient="horizontal", mode="indeterminate", length=200)
        self.progress_bar.pack(pady=10)

        # Initialize camera with the selected index
        self.cap = cv2.VideoCapture(self.selected_camera_index)
        self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

        # Add "Pengaturan" button
        self.settings_button = tk.Button(window, text="Pengaturan", bg="blue", fg="white", command=self.open_settings)
        self.settings_button.pack(pady=10)

        # Label to display status
        self.status_label = tk.Label(window, text="")
        self.status_label.pack(pady=10)

        self.update_frame()

    def get_available_cameras(self):
        camera_info = {}
        for i in range(10):  # Coba hingga 10 kamera
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                camera_info[i] = f"Camera {i}" if i == 0 else f"External Camera {i}"
                cap.release()
        return camera_info
    
    def on_camera_selected(self, event):
        """Callback when a new camera is selected from the combobox."""
        selected_index = self.camera_selection.current()
        if selected_index != self.selected_camera_index:
            self.selected_camera_index = selected_index
            self.selected_camera_name = self.camera_info[selected_index]
            self.camera_label.config(text=f"Selected Camera: {self.selected_camera_name}")
            # Start a thread to switch camera
            threading.Thread(target=self.switch_camera).start()

    def open_settings(self):
        settings_window = tk.Toplevel(self.window)
        settings_window.title("Pengaturan")

        # Create and place widgets in the settings window
        tk.Label(settings_window, text="Pilih Kamera").pack(pady=10)
        
        self.settings_camera_selection = ttk.Combobox(settings_window, values=list(self.camera_info.values()))
        self.settings_camera_selection.current(self.selected_camera_index)
        self.settings_camera_selection.pack(pady=10)

        tk.Label(settings_window, text="Input File Foto").pack(pady=10)

        self.file_path = tk.StringVar()
        tk.Entry(settings_window, textvariable=self.file_path, width=40).pack(pady=10)

        tk.Button(settings_window, text="Browse", command=self.browse_file).pack(pady=10)
        
        self.save_button = tk.Button(settings_window, text="Simpan", command=lambda: self.save_settings(settings_window))
        self.save_button.pack(pady=10)

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg;*.jpeg;*.png;*.webp")])
        self.file_path.set(file_path)

    def save_settings(self, settings_window):
        # Show loading indicator
        self.progress_bar.start()
        settings_window.update()  # Refresh the window to show the progress bar

        # Handle the file path and save it
        file_path = self.file_path.get()
        if file_path:
            # Determine the file name and save path
            file_name = os.path.basename(file_path)
            save_path = os.path.join('./desktops/employees/', file_name)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Copy the file to the destination directory
            shutil.copy(file_path, save_path)
            
            print(f"File saved: {save_path}")
            # Process the newly added image
            self.process_new_images()

        # Save new camera selection
        self.selected_camera_index = self.settings_camera_selection.current()
        self.selected_camera_name = self.camera_info[self.selected_camera_index]

        # Close settings window
        settings_window.destroy()

        # Stop loading indicator
        self.progress_bar.stop()

        # Restart camera
        self.restart_camera()

    def restart_camera(self):
        """Stops and restarts the camera."""
        if self.cap.isOpened():
            self.cap.release()
        self.cap = cv2.VideoCapture(self.selected_camera_index)
        self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    def process_new_images(self):
        """Process all images in the employees directory."""
        # Get list of all image files
        image_files = glob.glob('./desktops/employees/*.jpg') + glob.glob('./desktops/employees/*.jpeg') + glob.glob('./desktops/employees/*.png') + glob.glob('./desktops/employees/*.webp')
        
        # Load existing encodings
        existing_encodings = load_encodings_from_json()

        for image_path in image_files:
            # Generate a unique ID for each face
            face_id = str(uuid.uuid4())
            # Load image and get encoding
            image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(image)
            if encoding:  # Ensure at least one encoding is found
                encoding = encoding[0]
                if encoding.tolist() not in [data["encoding"] for data in existing_encodings.values()]:
                    known_face_encodings.append(encoding)
                    known_face_ids.append(face_id)
                    # Save encoding to JSON
                    save_encodings_to_json(face_id, encoding, image_path)

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # Draw boundary rectangle on frame
            cv2.rectangle(frame, frame_top_left, frame_bottom_right, (255, 0, 0), 2)  # Blue color, thickness 2

            # Find face locations and encodings in the frame
            face_locations = face_recognition.face_locations(frame)
            face_encodings = face_recognition.face_encodings(frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                # Calculate face center
                face_center = (left + (right - left) // 2, top + (bottom - top) // 2)

                # Match face encoding with known faces
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                name = "Unknown"  # Default name if no match is found

                if True in matches:
                    first_match_index = matches.index(True)
                    face_id = known_face_ids[first_match_index]
                    name = face_id

                    # Ensure face_id is in employee_status
                    if face_id not in employee_status:
                        # Initialize status if not present
                        employee_status[face_id] = "out"  # or any default value

                    # Check if face center is within the boundary
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
                            self.status_label.config(text=f"Employee {name} checked in.")
                    else:
                        if employee_status[face_id] == "in":
                            employee_status[face_id] = "out"
                            log_data = {
                                "id": face_id,
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "type": "out"
                            }
                            save_log(log_data)
                            self.status_label.config(text=f"Employee {name} checked out.")

                # Draw rectangle around face
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)

                # Display ID above the face box
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Resize frame to fit Tkinter window
            frame = cv2.resize(frame, (640, 480))
            # Convert frame to RGB and display in Tkinter canvas
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            img_tk = ImageTk.PhotoImage(image=img)
            self.canvas.img_tk = img_tk  # Keep reference to avoid garbage collection
            self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        
        # Schedule the next update
        self.window.after(10, self.update_frame)

# Create Tkinter window
root = tk.Tk()
app = FaceRecognitionApp(root)
root.mainloop()

# Release camera and close OpenCV windows
cap.release()
cv2.destroyAllWindows()


