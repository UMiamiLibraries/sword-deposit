from flask import Flask  # Import the Flask class
from flask_ckeditor import CKEditor
from flask_mail import Mail
app = Flask(__name__)    # Create an instance of the class for our use
ckeditor = CKEditor(app)

app.config.update(
    DEBUG=True,#EMAIL SETTINGS
    MAIL_SERVER='smtp.umail.miami.edu',
    MAIL_PORT=25
    #MAIL_USE_SSL=True
    )
mail = Mail(app)
