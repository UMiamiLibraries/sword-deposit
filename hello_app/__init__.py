from flask import Flask  # Import the Flask class
from flask_ckeditor import CKEditor
app = Flask(__name__)    # Create an instance of the class for our use
ckeditor = CKEditor(app)
