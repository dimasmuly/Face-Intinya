from flask import Flask, render_template, Response
import cv2
import numpy as np
import face_recognition
import json
import os
import random
import string
from datetime import datetime
from deepface import DeepFace

app = Flask(__name__)

# Initialize OpenCV's face cascade
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Ensure the directory exists
os.makedirs("./sites/json", exist_ok=True)

# Load known customers if they exist
customers = {}
try:
    if os.path.exists("./sites/json/customers.json") and os.path.getsize("./sites/json/customers.json") > 0:
        with open("./sites/json/customers.json", "r") as file:
            customers = json.load(file)
except json.JSONDecodeError:
    print("Error loading JSON file. Starting with an empty customers list.")
    customers = {}

def generate_frames():
    cap = cv2.VideoCapture(1)
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            frame = cv2.flip(frame, 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            for (x, y, w, h) in faces:
                face_img = frame[y:y+h, x:x+w]
                face_img_resized = cv2.resize(face_img, (200, 200))
                face_encoding = face_recognition.face_encodings(rgb_frame, [(y, x+w, y+h, x)])

                if face_encoding:
                    face_encoding = face_encoding[0]
                    matches = face_recognition.compare_faces([np.array(c['encoding']) for c in customers.values()], face_encoding)
                    name = "Unknown"
                    if True in matches:
                        first_match_index = matches.index(True)
                        name = list(customers.keys())[first_match_index]
                    else:
                        name = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10))
                        # Use DeepFace for gender and age prediction
                        obj = DeepFace.analyze(face_img_resized, actions=['age', 'gender'], enforce_detection=False, detector_backend='opencv')
                        if len(obj) > 0:
                            if 'gender' in obj[0]:
                                gender_pred = 'man' if obj[0]['gender'] == 'Male' else 'woman'
                            else:
                                gender_pred = 'Unknown'
                            if 'age' in obj[0]:
                                age_pred = obj[0]['age']
                            else:
                                age_pred = 'Unknown'
                        else:
                            gender_pred = 'Unknown'
                            age_pred = 'Unknown'
                        customers[name] = {
                            "encoding": face_encoding.tolist(),
                            "gender": gender_pred,
                            "age": age_pred,
                            "time": datetime.now().isoformat()
                        }
                        # Ensure the directory exists before writing
                        os.makedirs("./sites/json", exist_ok=True)
                        with open("./sites/json/customers.json", "w") as file:
                            json.dump(customers, file)

                    cv2.putText(frame, f'{name}, {customers[name]["age"]}, {customers[name]["gender"]}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True)