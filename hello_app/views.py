import base64
import contextlib
import os
import shutil
from datetime import date, timedelta
from zipfile import ZipFile
from werkzeug.utils import secure_filename
from slack_webhook import Slack
from . import app

import requests
import xml.etree.ElementTree as etree
from flask import Flask, render_template, request, send_file, session
from flask_mail import Mail, Message

# import application variables
from .config_prod import config
from .parameters import formdata

app.secret_key = config.get('secret_key')

# TODO: refactor to use azure web app configuation settings - issue with how to deal with local dev vars
# app.secret_key = os.environ.get('MY_SECRET_KEY')
# my_deposit_username = os.environ.get('MY_DEPOSIT_USERNAME')

# generate dates for embargo in the form
def getdates():
    today = date.today()
    dates = {'today': today,
             'oneyear': today + timedelta(weeks=52),
             'twoyears': today + timedelta(weeks=104),
             'eighteenmonths': today + timedelta(weeks=78)}
    return dates


# end session
def clearsession():
    session.pop('deposittype', None)
    session.pop('step', None)
    # print('session clear')


def slackmsg(fullname):
    msg = "New ETD submission to Esploro from " + fullname
    webhook = config.get('slack_webhook')
    slack = Slack(url=webhook)
    slack.post(text=msg)


def sendemail(email_data):
    try:
        mail = Mail()
        msg = Message("ETD Submission: A new thesis/dissertation uploaded by " + email_data['authoremail'],
                      sender="noreply@miami.edu",
                      recipients=[formdata['app_admin'],
                                  formdata['app_developer'],
                                  formdata['grad_service_account'],
                                  formdata['grad_admin'],
                                  formdata['repository_manager_email']
                                  ])

        msg.html = render_template("email.html", email_data=email_data)
        mail.send(msg)
    except Exception as ex:
        return str(ex)


# process form data and make sword request to Esploro server
def processdeposit(deposittype):
    mode = 0o775

    # Set working directories
    fileserver_path = config.get('fileserver_path')
    app_path = config.get('app_path')
    directory = 'output/'
    app.config['UPLOAD_FOLDER'] = os.path.join(fileserver_path, directory)

    # Check whether the specified path is an existing directory or not
    isdir = os.path.isdir(app.config['UPLOAD_FOLDER'])
    if not isdir:
        try:
            original_umask = os.umask(0)
            os.makedirs(app.config['UPLOAD_FOLDER'], mode)
        finally:
            os.umask(original_umask)

    # change into app.config['UPLOAD_FOLDER'] diretory - it is a temporary directory
    os.chdir(app.config['UPLOAD_FOLDER'])

    # provide feedback
    print(request.form)
    print(request.files['primaryfile'].filename)
    print(request.files.getlist('supplementalfiles'))

    # save files
    if request.files['primaryfile']:
        file = request.files['primaryfile']
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        file.filename = filename
    for file in request.files.getlist("supplementalfiles"):
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file.filename = filename

    # load blank metadata tree
    metadata_tree = etree.parse(os.path.join(app_path, 'static/metadata_template.xml'))

    ##
    # Populate metadata fields from form
    ##

    # set type
    if deposittype == "dissertation":
        metadata_tree.find(".//DISS_description").set("type", "doctoral")
    else:
        metadata_tree.find(".//DISS_description").set("type", "masters")

    # set files
    metadata_tree.find(".//DISS_content//DISS_binary").text = request.files['primaryfile'].filename
    for file in request.files.getlist("supplementalfiles"):
        if file:
            attachment = etree.SubElement(metadata_tree.find(".//DISS_content"), "DISS_attachment")
            attachmentname = etree.SubElement(metadata_tree.find(".//DISS_attachment[last()]"), "DISS_file_name")
            attachmentname.text = file.filename
            attachmenttype = etree.SubElement(metadata_tree.find(".//DISS_attachment[last()]"), "DISS_file_category")
            attachmenttype.text = "supplemental"

    print('files done')

    # set author name and email
    metadata_tree.find(".//DISS_author//DISS_name//DISS_surname").text = request.form['authorlname']
    metadata_tree.find(".//DISS_author//DISS_name//DISS_fname").text = request.form['authorfname']
    metadata_tree.find(".//DISS_author//DISS_name//DISS_middle").text = request.form['authormname']
    metadata_tree.find(".//DISS_author//DISS_permanent_email").text = request.form['authoremail']

    # set title
    metadata_tree.find(".//DISS_description//DISS_title").text = request.form['title']

    print('about to make a ', deposittype, 'deposit')

    # set project type
    if deposittype == "dissertation":
        metadata_tree.find(".//DISS_description//DISS_project_type").text = request.form['degreetype']
    elif deposittype == "masters":
        metadata_tree.find(".//DISS_description//DISS_project_type").text = 'thesis'
    print('type done')

    # set dates
    # DEGREE DATE REQUIRED
    metadata_tree.find(".//DISS_description//DISS_dates//DISS_degree_date").text = request.form['pubdate']
    metadata_tree.find(".//DISS_description//DISS_dates//DISS_manuscript_date").text = request.form['pubdate']
    metadata_tree.find(".//DISS_description//DISS_dates//DISS_defense_date").text = request.form['defensedate']

    print('dates done')

    # set degree
    # metadata_tree.find(".//DISS_description//DISS_degree//DISS_degree_abbreviation").text = request.form['degreename']
    # metadata_tree.find(".//DISS_description//DISS_degree//DISS_degree_name").text = formdata[deposittype]["degreename"].get(request.form['degreename'])
    metadata_tree.find(".//DISS_description//DISS_degree//DISS_degree_name").text = request.form['degreename']

    # set department
    metadata_tree.find(".//DISS_description//DISS_inst_department").text = request.form['department']
    # set advisors
    # metadata_tree.find(".//DISS_description//DISS_advisor//DISS_name//DISS_surname").text = "AdvisorL"
    # metadata_tree.find(".//DISS_description//DISS_advisor//DISS_name//DISS_fname").text = "AdvisorF"
    # metadata_tree.find(".//DISS_description//DISS_advisor//DISS_name//DISS_order").text = "1"

    print('basic meta done')

    # set committee members
    cmtemembers = metadata_tree.findall(".//DISS_description//DISS_cmte_member")
    if request.form.getlist('firstcmtemember'):
        cmtemembers[0].find(".//DISS_name//DISS_fname").text = request.form.getlist('firstcmtemember')[0]
        if len(request.form.getlist('firstcmtemember')) == 3:
            cmtemembers[0].find(".//DISS_name//DISS_middle").text = request.form.getlist('firstcmtemember')[1]
            cmtemembers[0].find(".//DISS_name//DISS_surname").text = request.form.getlist('firstcmtemember')[2]
        else:
            cmtemembers[0].find(".//DISS_name//DISS_surname").text = request.form.getlist('firstcmtemember')[1]
    if request.form.getlist('secondcmtemember'):
        cmtemembers[1].find(".//DISS_name//DISS_fname").text = request.form.getlist('secondcmtemember')[0]
        if len(request.form.getlist('firstcmtemember')) == 3:
            cmtemembers[1].find(".//DISS_name//DISS_middle").text = request.form.getlist('secondcmtemember')[1]
            cmtemembers[1].find(".//DISS_name//DISS_surname").text = request.form.getlist('secondcmtemember')[2]
        else:
            cmtemembers[1].find(".//DISS_name//DISS_surname").text = request.form.getlist('secondcmtemember')[1]
    if request.form.getlist('thirdcmtemember'):
        cmtemembers[2].find(".//DISS_name//DISS_fname").text = request.form.getlist('thirdcmtemember')[0]
        if len(request.form.getlist('firstcmtemember')) == 3:
            cmtemembers[2].find(".//DISS_name//DISS_middle").text = request.form.getlist('thirdcmtemember')[1]
            cmtemembers[2].find(".//DISS_name//DISS_surname").text = request.form.getlist('thirdcmtemember')[2]
        else:
            cmtemembers[2].find(".//DISS_name//DISS_surname").text = request.form.getlist('thirdcmtemember')[1]
    if request.form.getlist('fourthcmtemember'):
        cmtemembers[3].find(".//DISS_name//DISS_fname").text = request.form.getlist('fourthcmtemember')[0]
        if len(request.form.getlist('firstcmtemember')) == 3:
            cmtemembers[3].find(".//DISS_name//DISS_middle").text = request.form.getlist('fourthcmtemember')[1]
            cmtemembers[3].find(".//DISS_name//DISS_surname").text = request.form.getlist('fourthcmtemember')[2]
        else:
            cmtemembers[3].find(".//DISS_name//DISS_surname").text = request.form.getlist('fourthcmtemember')[1]
    if request.form.getlist('fifthcmtemember'):
        cmtemembers[4].find(".//DISS_name//DISS_fname").text = request.form.getlist('fifthcmtemember')[0]
        if len(request.form.getlist('firstcmtemember')) == 3:
            cmtemembers[4].find(".//DISS_name//DISS_middle").text = request.form.getlist('fifthcmtemember')[1]
            cmtemembers[4].find(".//DISS_name//DISS_surname").text = request.form.getlist('fifthcmtemember')[2]
        else:
            cmtemembers[4].find(".//DISS_name//DISS_surname").text = request.form.getlist('fifthcmtemember')[1]
    if request.form.getlist('sixthcmtemember'):
        cmtemembers[5].find(".//DISS_name//DISS_fname").text = request.form.getlist('sixthcmtemember')[0]
        if len(request.form.getlist('firstcmtemember')) == 3:
            cmtemembers[5].find(".//DISS_name//DISS_middle").text = request.form.getlist('sixthcmtemember')[1]
            cmtemembers[5].find(".//DISS_name//DISS_surname").text = request.form.getlist('sixthcmtemember')[2]
        else:
            cmtemembers[5].find(".//DISS_name//DISS_surname").text = request.form.getlist('sixthcmtemember')[1]
    if request.form.getlist('seventhcmtemember'):
        cmtemembers[6].find(".//DISS_name//DISS_fname").text = request.form.getlist('seventhcmtemember')[0]
        if len(request.form.getlist('firstcmtemember')) == 3:
            cmtemembers[6].find(".//DISS_name//DISS_middle").text = request.form.getlist('seventhcmtemember')[1]
            cmtemembers[6].find(".//DISS_name//DISS_surname").text = request.form.getlist('seventhcmtemember')[2]
        else:
            cmtemembers[6].find(".//DISS_name//DISS_surname").text = request.form.getlist('seventhcmtemember')[1]
    # metadata_tree.find(".//DISS_description//DISS_cmte_member//DISS_name//DISS_surname").text = "CmteL"
    # metadata_tree.find(".//DISS_description//DISS_cmte_member//DISS_name//DISS_fname").text = "CmteF"
    # metadata_tree.find(".//DISS_description//DISS_cmte_member//DISS_name//DISS_order").text = "1"

    print('committee done')

    # set availability
    if request.form['availability'] == "open":
        metadata_tree.find(".//DISS_repository//DISS_access_option").text = 'Open'
        # metadata_tree.find(".//DISS_repository//DISS_access_option").text = "Research:open"
    else:
        # only date is needed, embargo is automatically set
        metadata_tree.find(".//DISS_repository//DISS_delayed_release").text = request.form['availability']

    # set categories
    # metadata_tree.find(".//DISS_description//DISS_categorization//DISS_category//DISS_cat_code").text = parameters.topics.get(request.form['topic'])
    # metadata_tree.find(".//DISS_description//DISS_categorization//DISS_category//DISS_cat_desc").text = request.form['topic']

    # set keywords
    keywords = metadata_tree.findall(".//DISS_description//DISS_categorization//DISS_keyword")
    for i, keyword in enumerate(request.form.getlist('keywords')):
        if keyword:
            keywords[i].text = keyword
    # set abstract
    for i, paragraph in enumerate(request.form['abstract'].split('\r\n')):
        if paragraph.strip():
            para = etree.SubElement(metadata_tree.find(".//DISS_content//DISS_abstract"), "DISS_para")
            para.text = paragraph
    # set language - default is en
    metadata_tree.find(".//DISS_description//DISS_categorization//DISS_language").text = request.form['language']
    # set policy accepted
    metadata_tree.find(".//DISS_repository//DISS_agreement_decision_date").text = request.form['pubdate']

    ##
    # End of metadata capture from form
    #
    # Begin request
    ##

    # set temporary file names using title and author
    file_name = secure_filename(request.form['authorlname'] + '_' + request.form['title'])

    # the xml file MUST be called "metadata.xml"
    xml_file = "metadata.xml"
    txt_file = file_name + ".txt"
    zip_file = file_name + ".zip"

    # write XML to temp file
    metadata_tree = metadata_tree.getroot()
    with open(os.path.join(app.config['UPLOAD_FOLDER'], xml_file), 'w+') as fh:
        fh.write(etree.tostring(metadata_tree, encoding='unicode'))  # , pretty_print=True (for lxml)

    # create the zip file and write uploaded files and metadata to it
    # contextlib.closing needed for python 2.6
    with contextlib.closing(ZipFile(os.path.join(app.config['UPLOAD_FOLDER'], zip_file), "w")) as depositzip:
        depositzip.write(xml_file)
        depositzip.write(request.files['primaryfile'].filename)
        for file in request.files.getlist("supplementalfiles"):
            if file.filename != '':
                depositzip.write(file.filename)

    # encode the zip file and create sword call file
    encodedzip = base64.b64encode(open(os.path.join(app.config['UPLOAD_FOLDER'], zip_file), 'rb').read()).decode()

    # copy the deposit.txt file to app.config['UPLOAD_FOLDER']
    shutil.copyfile(os.path.join(app_path, 'static/deposit.txt'), os.path.join(app.config['UPLOAD_FOLDER'], txt_file))
    sword_call = open(os.path.join(app.config['UPLOAD_FOLDER'], txt_file), 'r').read().format(encoding=encodedzip)
    open(os.path.join(app.config['UPLOAD_FOLDER'], txt_file), 'w').write(sword_call)

    # set request url and authentication
    deposit_url = config.get('deposit_url').format(
        username=config.get('deposit_username'),
        password=config.get('deposit_password')
    )
    print(deposit_url)

    # set the headers
    headers = {
        'Content-Type': 'multipart/related; boundary=---------------1605871705;  type="application/atom+xml"',
        "On-behalf-of": config.get('deposit_obo'),
    }

    # get saved text blob and make the call
    data = open(os.path.join(app.config['UPLOAD_FOLDER'], txt_file), 'rb').read()
    print("sending file")
    r = requests.post(deposit_url, headers=headers, data=data)

    # logging.info("---------------------")
    # logging.info('deposit made for ' + request.form['authorfname'] + request.form['authorlname'])
    # logging.info('title: ' + request.form['title'])
    # logging.info('date: ' + request.form['pubdate'])
    # logging.info('status: ' + str(r.status_code) + "  " + r.text)

    # delete the files
    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], request.files['primaryfile'].filename))
    for file in request.files.getlist("supplementalfiles"):
        if file.filename != '':
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], zip_file))
    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], xml_file))
    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], txt_file))

    print(r.status_code)
    return r.status_code
    # return 201


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(415)
@app.errorhandler(500)
@app.errorhandler(502)
@app.errorhandler(504)
def http_error_handler(error):
    # msg = EmailMessage()
    # msg.set_content('Dear UM SWORD admin,\n\nThere has been an error on the SWORD deposit server with the following message:\n\n%s\n\nkind regards\nfrom the server' % (error))
    # msg['Subject'] = 'SWORD error'
    # msg['From'] = 'tibben@ocf.berkeley.edu'
    # msg['To'] = 'tibben@huaylas.com'
    # s = smtplib.SMTP('localhost')
    # s.send_message(msg)
    # s.quit()
    print(error)
    return render_template('error.html', formdata=formdata, error=error)


@app.route("/um-agreement-pdf/", methods=['GET'])
def downloadagreement():
    try:
        return send_file(filename_or_fp='static/um_agreement.pdf')
    except Exception:
        # return render_template('error.html')
        return http_error_handler('send agreement pdf failed')


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == "GET":
        session['step'] = "selecttype"

        return render_template("select_type.html")
    elif request.method == "POST":
        if session['step'] == "selecttype":
            session['deposittype'] = request.form['deposittype']
            session['step'] = "agreement"
            return render_template('agreement.html')
        if session['step'] == "agreement":
            formdata['dates'] = getdates()
            formdata['deposittype'] = session['deposittype']
            session['step'] = "depositform"
            if session['deposittype']:
                return render_template("deposit_form.html", formdata=formdata)
            else:
                return http_error_handler('no deposit type selected')
                # return render_template('error.html')
        if session['step'] == "depositform":
            depositresult = processdeposit(request.form['deposittype'])
            if depositresult == 201:

                fullname = request.form['authorfname'] + ' ' + request.form['authorlname']
                # send msg to slack
                slackmsg(fullname)

                # send email
                sendemail(request.form)

                # clear the session to make sure the deposit results page loads properly
                clearsession()

                # render template
                return render_template("deposit_result.html", form=request.form, files=request.files)
            else:
                slackmsg(depositresult)
                return http_error_handler(depositresult)
        else:
            return http_error_handler('bad path')


if __name__ == '__main__':
    app.run(host='0.0.0.0')