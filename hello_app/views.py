import base64
import contextlib
import os
# import logging
import shutil
from datetime import date, timedelta
from zipfile import ZipFile
from werkzeug.utils import secure_filename
# import smtplib
# from email.message import EmailMessage
from . import app

import requests
import xml.etree.ElementTree as etree
from flask import Flask, render_template, request, send_file, session

from .config_local_docker import config
from .parameters import formdata

app.secret_key = config.get('secret_key')
# logging.basicConfig(filename='deposits.log', level=logging.INFO)


def getdates():
    today = date.today()
    dates = {'today': today,
             'oneyear': today + timedelta(weeks=52),
             'twoyears': today + timedelta(weeks=104),
             'eighteenmonths': today + timedelta(weeks=78)}
    return dates


def clearsession():
    session.pop('deposittype', None)
    session.pop('step', None)


def processdeposit(deposittype):

    print("current directory: " + os.getcwd())
    # Parent Directory path 
    # home_path = '/home/site/wwwroot'
    home_path = config.get('fileserver_path')
    # home_path = "C:/users/eprieto/Desktop/Submission/"

    # Output Directory 
    directory = 'output/'
    
    # mode writable
    # mode = 0o222 PREVIOUS FOR AZURE
    mode = 0o775

    app_path = config.get('app_path')

    # Output Path 
    app.config['UPLOAD_FOLDER'] = os.path.join(home_path, directory) 

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

    print(request.form)
    print(request.files['primaryfile'].filename)
    print(request.files.getlist('supplementalfiles'))

    #save files
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
    metadata_tree = etree.parse(app_path+'/static/metadata_template.xml')

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

    print('about to make a ',deposittype,'deposit')

    # set project type
    if deposittype == "dissertation":
        metadata_tree.find(".//DISS_description//DISS_project_type").text = request.form['degreetype']

    print('type done')

    # set dates
    #DEGREE DATE REQUIRED
    metadata_tree.find(".//DISS_description//DISS_dates//DISS_degree_date").text = request.form['pubdate']
    metadata_tree.find(".//DISS_description//DISS_dates//DISS_manuscript_date").text = request.form['pubdate']
    metadata_tree.find(".//DISS_description//DISS_dates//DISS_defense_date").text = request.form['defensedate']

    print('dates done')

    # set degree
    metadata_tree.find(".//DISS_description//DISS_degree//DISS_degree_abbreviation").text = request.form['degreename']
    metadata_tree.find(".//DISS_description//DISS_degree//DISS_degree_name").text = formdata[deposittype]["degreename"].get(request.form['degreename'])
    #set department
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
    if request.form['availability'] == "open access":
        metadata_tree.find(".//DISS_repository//DISS_access_option").text = "9623461160002976"
        # metadata_tree.find(".//DISS_repository//DISS_access_option").text = "Research:open"
    else:
        # only date is needed, embargo is automatically set
        metadata_tree.find(".//DISS_repository//DISS_delayed_release").text = request.form['availability']

    # set categories
    #metadata_tree.find(".//DISS_description//DISS_categorization//DISS_category//DISS_cat_code").text = parameters.topics.get(request.form['topic'])
    #metadata_tree.find(".//DISS_description//DISS_categorization//DISS_category//DISS_cat_desc").text = request.form['topic']

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
     ##    
    
    # set temporary file names
    file_name = ''.join(
        e for e in request.form['authorlname'] if e.isalnum()
    ) + "_" + request.form['authorfname'] + "_" + ''.join(
        e for e in request.form['title'] if e.isalnum()
    )
    # the xml file MUST be called "metadata.xml"
    xml_file = "metadata.xml"
    txt_file = file_name + ".txt"
    zip_file = file_name + ".zip"

    # write XML to temp file
    metadata_tree = metadata_tree.getroot()
    with open(app.config['UPLOAD_FOLDER'] + xml_file, 'w+') as fh:
        fh.write(etree.tostring(metadata_tree, encoding='unicode')) # , pretty_print=True (for lxml)

    # create the zip file and write uploaded files and metadata to it
    # contextlib.closing needed for python 2.6
    with contextlib.closing(ZipFile(app.config['UPLOAD_FOLDER'] + zip_file, "w")) as depositzip:
        depositzip.write(xml_file)
        depositzip.write(request.files['primaryfile'].filename)
        for file in request.files.getlist("supplementalfiles"):
            if file.filename != '':
                depositzip.write(file.filename)

    # encode the zip file and create sword call file
    encodedzip = base64.b64encode(open(app.config['UPLOAD_FOLDER'] + zip_file, 'rb').read()).decode()

    # copy the deposit.txt file to app.config['UPLOAD_FOLDER']
    shutil.copyfile(app_path + 'static/deposit.txt', app.config['UPLOAD_FOLDER'] + txt_file)
    sword_call = open(app.config['UPLOAD_FOLDER'] + txt_file, 'r').read().format(encoding=encodedzip)
    open(app.config['UPLOAD_FOLDER'] + txt_file, 'w').write(sword_call)

    # set request variables and make call
    deposit_url = config.get('deposit_url').format(
        username=config.get('deposit_username'), 
        password=config.get('deposit_password')
    )
    print (deposit_url)

    headers = {
        'Content-Type': 'multipart/related; boundary=---------------1605871705;  type="application/atom+xml"',
        "On-behalf-of": config.get('deposit_obo'),
    }

    data = open(app.config['UPLOAD_FOLDER'] + txt_file, 'rb').read()
    print("sending file")
    r = requests.post(deposit_url, headers=headers, data=data, verify=False)

    #logging.info("---------------------")
    #logging.info('deposit made for ' + request.form['authorfname'] + request.form['authorlname'])
    #logging.info('title: ' + request.form['title'])
    #logging.info('date: ' + request.form['pubdate'])
    #logging.info('status: ' + str(r.status_code) + "  " + r.text)

    clearsession()

    # delete the files
    os.remove(app.config['UPLOAD_FOLDER'] + '/' + request.files['primaryfile'].filename)
    for file in request.files.getlist("supplementalfiles"):
       if file.filename != '':
           os.remove(app.config['UPLOAD_FOLDER'] + '/' + file.filename)
    os.remove(app.config['UPLOAD_FOLDER'] + '/' + zip_file)
    os.remove(app.config['UPLOAD_FOLDER'] + '/' + xml_file)
    os.remove(app.config['UPLOAD_FOLDER'] + '/' + txt_file)

    return r.status_code
    #return 201


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(415)
@app.errorhandler(500)
def http_error_handler(error):
    #msg = EmailMessage()
    #msg.set_content('Dear UM SWORD admin,\n\nThere has been an error on the SWORD deposit server with the following message:\n\n%s\n\nkind regards\nfrom the server' % (error))
    #msg['Subject'] = 'SWORD error'
    #msg['From'] = 'tibben@ocf.berkeley.edu'
    #msg['To'] = 'tibben@huaylas.com'
    #s = smtplib.SMTP('localhost')
    #s.send_message(msg)
    #s.quit()
    print(error)
    return render_template('error.html')


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
                #return render_template('error.html')
        if session['step'] == "depositform":
            depositresult = processdeposit(request.form['deposittype'])
            if depositresult == 201:
                return render_template("deposit_result.html", form=request.form, files=request.files)
            else:
                # return render_template('error.html')
                return http_error_handler(depositresult)
        else:
            return http_error_handler('bad path')
            # return render_template('error.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0')

