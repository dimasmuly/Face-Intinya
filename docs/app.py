from flask import Flask
from flask import render_template

app = Flask(__name__)

@app.route('/')
def home():
  return render_template('index.html')

@app.route('/docs')
def docs():
  return render_template('docs.html') 

if __name__ == '__main__':
  app.run(debug=True, host='localhost', port=8080)