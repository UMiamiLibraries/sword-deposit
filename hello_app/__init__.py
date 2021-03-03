from flask import Flask # Import the Flask class
from flask_mail import Mail

app = Flask(__name__) # Create an instance of the class for our use
mail = Mail(app)
