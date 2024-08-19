from flask import Flask, render_template, Response
import cv2
import tensorflow as tf
import numpy as np
import face_recognition
import json
import os
import random
import string
from datetime import datetime
from tensorflow.keras.optimizers import Adam

app = Flask(__name__)

# Load pre-trained models
age_model = tf.keras.models.load_model('./models/age_model.h5')
gen_model = tf.keras.models.load_model('./models/gen_model.h5')
fe_model = tf.keras.models.load_model('./models/fer2013_mini_XCEPTION.102-0.66.hdf5', compile=False)
fe_model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001), loss='categorical_crossentropy', metrics=['accuracy'])
expression_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

customers = {}
if os.path.exists("./sites/json/customers.json") and os.path.getsize("./sites/json/customers.json") > 0:
    with open("./sites/json/customers.json", "r") as file:
        customers = json.load(file)

counter = []
if os.path.exists("./sites/json/counter.json") and os.path.getsize("./sites/json/counter.json") > 0:
    with open("./sites/json/counter.json", "r") as file:
        counter = json.load(file)

current_faces_in_box = set()
cap = cv2.VideoCapture(1)

def get_frame():
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        faces_in_current_frame = set()
        for (x, y, w, h) in faces:
            face_img = frame[y:y+h, x:x+w]
            face_img_resized = cv2.resize(face_img, (200, 200))
            face_encoding = face_recognition.face_encodings(rgb_frame, [(y, x+w, y+h, x)])

            roi_gray = gray[y:y+h, x:x+w]
            roi_gray = cv2.resize(roi_gray, (64, 64))
            roi = roi_gray.astype('float') / 255.0
            roi = np.expand_dims(roi, axis=-1)
            roi = np.expand_dims(roi, axis=0)
            fe_preds = fe_model.predict(roi)[0]
            expression = expression_labels[fe_preds.argmax()]

            if face_encoding:
                face_encoding = face_encoding[0]
                matches = face_recognition.compare_faces([np.array(c['encoding']) for c in customers.values()], face_encoding)
                name = "Unknown"
                if True in matches:
                    first_match_index = matches.index(True)
                    name = list(customers.keys())[first_match_index]
                else:
                    name = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
                    gender_pred = gen_model.predict(face_img_resized.reshape(-1, 200, 200, 3) / 255.0)
                    age_pred = age_model.predict(face_img_resized.reshape(-1, 200, 200, 3) / 255.0)
                    customers[name] = {
                        "encoding": face_encoding.tolist(),
                        "gender": "Male" if gender_pred[0][0] < 0.5 else "Female",
                        "age": int(age_pred),
                        "time": datetime.now().isoformat()
                    }
                    with open("./sites/json/customers.json", "w") as file:
                        json.dump(customers, file)

                faces_in_current_frame.add(name)
                detection_box = (50, 50, 600, 400)
                if (x > detection_box[0] and y > detection_box[1] and (x + w) < detection_box[2] and (y + h) < detection_box[3]):
                    if name not in current_faces_in_box:
                        counter.append({
                            "ID": name,
                            "expression": expression,
                            "time": datetime.now().isoformat()
                        })
                        with open("./sites/json/counter.json", "w") as file:
                            json.dump(counter, file)
                        current_faces_in_box.add(name)

                cv2.putText(frame, f'{name}, {customers[name]["age"]}, {customers[name]["gender"]}, {expression}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

        current_faces_in_box.difference_update(current_faces_in_box - faces_in_current_frame)
        cv2.rectangle(frame, (50, 50), (600, 400), (0, 255, 0), 2)
        ret, jpeg = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(get_frame(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True)
