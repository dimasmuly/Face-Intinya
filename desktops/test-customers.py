import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import numpy as np
import tensorflow as tf
from pygrabber.dshow_graph import FilterGraph
import threading
import time
import face_recognition
import json
from datetime import datetime
import os
import random
import string
from tensorflow.keras.optimizers import Adam
import uuid

# Load pre-trained models age and gender
age_model = tf.keras.models.load_model('./models/age_model.h5')
gen_model = tf.keras.models.load_model('./models/gen_model.h5')
# Load pre-trained model for facial expression
fe_model = tf.keras.models.load_model('./models/fer2013_mini_XCEPTION.102-0.66.hdf5', compile=False)
# Kompilasi ulang model dengan optimizer yang sesuai
fe_model.compile(optimizer=Adam(learning_rate=0.0001), loss='categorical_crossentropy', metrics=['accuracy'])
# Labels emosi yang sesuai dengan model
expression_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

# Initialize OpenCV's face cascade
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Load known customers if they exist
customers = {}
try:
    if os.path.exists("./desktops/json/customers.json") and os.path.getsize("./desktops/json/customers.json") > 0:
        with open("./desktops/json/customers.json", "r") as file:
            customers = json.load(file)
except json.JSONDecodeError:
    print("Error loading JSON file. Starting with an empty customers list.")
    customers = {}

class FaceRecognitionApp:
    def __init__(self, window):
        self.window = window
        self.window.title("Face Recognition App")

        self.canvas = tk.Canvas(window, width=640, height=480)
        self.canvas.pack()

        # Get list of available cameras and their names
        self.camera_info = self.get_available_cameras()
        self.selected_camera_index = 1
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

        self.update()

    def get_available_cameras(self):
        """Returns a dictionary of available cameras with their indices and names."""
        devices = FilterGraph().get_input_devices()
        available_cameras = {device_index: device_name for device_index, device_name in enumerate(devices)}
        return available_cameras

    def on_camera_selected(self, event):
        """Callback when a new camera is selected from the combobox."""
        selected_index = self.camera_selection.current()
        if selected_index != self.selected_camera_index:
            self.selected_camera_index = selected_index
            self.selected_camera_name = self.camera_info[selected_index]
            self.camera_label.config(text=f"Selected Camera: {self.selected_camera_name}")
            # Start a thread to switch camera
            threading.Thread(target=self.switch_camera).start()

    def switch_camera(self):
        """Switches camera in a separate thread with loading indication."""
        self.progress_bar.start()
        time.sleep(1)  # Simulate camera switching delay (adjust as needed)
        self.cap.release()  # Release the current camera
        self.cap = cv2.VideoCapture(self.selected_camera_index)  # Initialize with the new camera index
        self.progress_bar.stop()

    def update(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1)  # Flip frame horizontally
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            for (x, y, w, h) in faces:
                face_img = frame[y:y+h, x:x+w]
                face_img_resized = cv2.resize(face_img, (200, 200))
                face_encoding = face_recognition.face_encodings(rgb_frame, [(y, x+w, y+h, x)])

                # Facial expression recognition
                roi_gray = gray[y:y+h, x:x+w]
                roi_gray = cv2.resize(roi_gray, (64, 64))  # Mengubah ukuran menjadi 64x64
                roi = roi_gray.astype('float') / 255.0
                roi = np.expand_dims(roi, axis=-1)  # Menambahkan saluran ke dalam gambar grayscale
                roi = np.expand_dims(roi, axis=0)
                
                # Prediksi emosi
                fe_preds = fe_model.predict(roi)[0]
                expression = expression_labels[fe_preds.argmax()]

                if face_encoding:
                    face_encoding = face_encoding[0]
                    # Check if the face is recognized
                    matches = face_recognition.compare_faces([np.array(c['encoding']) for c in customers.values()], face_encoding)
                    name = "Unknown"
                    if True in matches:
                        first_match_index = matches.index(True)
                        name = list(customers.keys())[first_match_index]
                    else:
                        # generate a unique ID for the new customer random alphanumeric characters
                        name = str(uuid.uuid4())
                        gender_pred = gen_model.predict(face_img_resized.reshape(-1, 200, 200, 3) / 255.0)
                        age_pred = age_model.predict(face_img_resized.reshape(-1, 200, 200, 3) / 255.0)
                        customers[name] = {
                            "encoding": face_encoding.tolist(),
                            "gender": "Male" if gender_pred < 0.5 else "Female",
                            "age": int(age_pred),
                            "expression": expression,
                            "time": datetime.now().isoformat()
                        }
                        with open("./desktops/json/customers.json", "w") as file:
                            json.dump(customers, file)

                    cv2.putText(frame, f'{customers[name]["age"]}, {customers[name]["gender"]}, {expression}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    # Puttext di bawah kotak wajah
                    cv2.putText(frame, name, (x, y+h+20), cv2.FONT_HERSHEY_SIMPLEX, 0.2, (255, 255, 255), 1)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

            # Resize frame to fit the Tkinter window
            frame = cv2.resize(frame, (640, 480))
            # Convert frame to RGB format and display in tkinter canvas
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            img_tk = ImageTk.PhotoImage(image=img)
            self.canvas.img_tk = img_tk  # Keep reference to avoid garbage collection
            self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        self.window.after(10, self.update)

# Create Tkinter window
root = tk.Tk()
app = FaceRecognitionApp(root)
root.mainloop()

# Release camera and close OpenCV windows
app.cap.release()
cv2.destroyAllWindows()
