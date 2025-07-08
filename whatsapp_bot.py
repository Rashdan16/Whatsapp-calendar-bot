from flask import Flask, request
app = Flask(__name__)

@app.route('/')
def home():
    return '🚀 WhatsApp–Calendar Bot is up and running!'

if __name__ == '__main__':
    app.run(debug=True)
