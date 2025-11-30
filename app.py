from flask import Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
@app.route('/')
def hello():
    return 'SR-Manager is running! '
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
