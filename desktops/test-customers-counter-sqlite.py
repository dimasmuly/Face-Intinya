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
import sqlite3
import random
import string
from tensorflow.keras.optimizers import Adam
import uuid

# Load pre-trained models
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

# To keep track of faces currently in the detection box
current_faces_in_box = set()

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

        # Define the detection box coordinates (left, top, right, bottom)
        self.detection_box = (50, 50, 600, 400)  # You can adjust these coordinates

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

            # Temporary set to keep track of faces detected in this frame
            faces_in_current_frame = set()

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
                    customer_id = self.get_customer_id(face_encoding)
                    if customer_id is None:
                        # generate a unique ID for the new customer random alphanumeric characters
                        customer_id = str(uuid.uuid4())
                        gender_pred = gen_model.predict(face_img_resized.reshape(-1, 200, 200, 3) / 255.0)
                        age_pred = age_model.predict(face_img_resized.reshape(-1, 200, 200, 3) / 255.0)
                        self.add_customer(customer_id, face_encoding, "Male" if gender_pred < 0.5 else "Female", int(age_pred))

                    # Add the face to the set for this frame
                    faces_in_current_frame.add(customer_id)

                    # Check if face is within detection box
                    if (x > self.detection_box[0] and y > self.detection_box[1] and (x + w) < self.detection_box[2] and (y + h) < self.detection_box[3]):
                        if customer_id not in current_faces_in_box:
                            self.add_counter(customer_id, expression)
                            current_faces_in_box.add(customer_id)

                    customer_data = self.get_customer_data(customer_id)
                    cv2.putText(frame, f'{customer_data["age"]}, {customer_data["gender"]}, {expression}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    # Puttext di bawah kotak wajah
                    cv2.putText(frame, customer_id, (x, y+h+20), cv2.FONT_HERSHEY_SIMPLEX, 0.2, (255, 255, 255), 1)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

            # Remove faces that are no longer in the box
            current_faces_in_box.difference_update(current_faces_in_box - faces_in_current_frame)

            # Draw detection box
            cv2.rectangle(frame, (self.detection_box[0], self.detection_box[1]), (self.detection_box[2], self.detection_box[3]), (0, 255, 0), 2)

            # Resize frame to fit the Tkinter window
            frame = cv2.resize(frame, (640, 480))
            # Convert frame to RGB format and display in tkinter canvas
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            img_tk = ImageTk.PhotoImage(image=img)
            self.canvas.img_tk = img_tk  # Keep reference to avoid garbage collection
            self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        self.window.after(10, self.update)

    def get_customer_id(self, face_encoding):
        """Returns the customer_id if the face is recognized, else None."""
        conn = sqlite3.connect('./desktops/db/face_recognition.db')
        cursor = conn.cursor()
        cursor.execute("SELECT customer_id, encoding FROM customers")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            customer_id, encoding = row
            if face_recognition.compare_faces([np.frombuffer(encoding)], face_encoding)[0]:
                return customer_id
        return None

    def add_customer(self, customer_id, face_encoding, gender, age):
        """Adds a new customer to the database."""
        conn = sqlite3.connect('./desktops/db/face_recognition.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO customers (customer_id, encoding, gender, age, time) VALUES (?, ?, ?, ?, ?)",
                       (customer_id, face_encoding.tobytes(), gender, age, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def add_counter(self, customer_id, expression):
        """Adds a new counter entry to the database."""
        conn = sqlite3.connect('./desktops/db/face_recognition.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO counters (customer_id, expression, time) VALUES (?, ?, ?)",
                       (customer_id, expression, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_customer_data(self, customer_id):
        """Returns customer data for the given customer_id."""
        conn = sqlite3.connect('./desktops/db/face_recognition.db')
        cursor = conn.cursor()
        cursor.execute("SELECT gender, age FROM customers WHERE customer_id = ?", (customer_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            gender, age = row
            return {"gender": gender, "age": age}
        return None

# Create Tkinter window
root = tk.Tk()
app = FaceRecognitionApp(root)
root.mainloop()

# Release camera and close OpenCV windows
app.cap.release()
cv2.destroyAllWindows()
