import base64
import contextlib
import os
import logging
from datetime import date, timedelta
from zipfile import ZipFile

import requests
from lxml import etree
from flask import Flask, render_template, request, send_file, session

import config

app = Flask(__name__)
app.secret_key = b'22g`?lJ[z-Ue)D.'
logging.basicConfig(filename='deposits.log', level=logging.INFO)


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


@app.errorhandler(400)
def bad_request_error(error):
    logging.error('400 error')
    return render_template("error.html"), 400


@app.errorhandler(404)
def internal_server_error(error):
    logging.error('404 error')
    return render_template("error.html"), 404


@app.errorhandler(500)
def page_not_found(error):
    logging.error('500 error')
    return render_template("error.html"), 500


@app.route('/')
def index():
    return "click <a href='/etd-deposit'>here</a>"


@app.route("/um-agreement-pdf/", methods=['GET'])
def downloadagreement():
    try:
        return send_file(filename_or_fp='static/um_agreement.pdf')
    except Exception as e:
        #return str(e)
        return str("There was an issue processing your request. Please contact an administrator")


@app.route('/etd-deposit/', methods=['GET', 'POST'])
def etddeposit():
    if request.method == "GET":
        session['step'] = "selecttype"
        return render_template("select_type.html")
    elif request.method == "POST":
        if session['step'] == "selecttype":
            session['deposittype'] = request.form['deposittype']
            session['step'] = "agreement"
            return render_template('agreement.html', deposittype=session['deposittype'])
        if session['step'] == "agreement":
            dates = getdates()
            session['step'] = "depositform"
            if session['deposittype'] == "dissertation":
                return render_template("dissertation_form.html", dates=dates)
            # masters
            elif session['deposittype'] == "masters":
                return render_template("masters_form.html", dates=dates)
        if session['step'] == "depositform":
            print(request.form)
            # load blank metadata tree
            metadata_tree = etree.parse('static/metadata_template.xml')
            # populate fields from form
            # set type
            if request.form['deposittype'] == "dissertation":
                metadata_tree.find("//DISS_description").set("type", "doctoral")
            else:
                metadata_tree.find("//DISS_description").set("type", "masters")
            # set author name and email
            metadata_tree.find("//DISS_author//DISS_name//DISS_surname").text = request.form['authorlname']
            metadata_tree.find("//DISS_author//DISS_name//DISS_fname").text = request.form['authorfname']
            metadata_tree.find("//DISS_author//DISS_name//DISS_middle").text = request.form['authormname']
            metadata_tree.find("//DISS_author//DISS_permanent_email").text = request.form['authoremail']
            # set title
            metadata_tree.find("//DISS_description//DISS_title").text = request.form['title']
            # set pub dates
            metadata_tree.find("//DISS_description//DISS_dates//DISS_degree_date").text = "2017-01-01"
            metadata_tree.find("//DISS_description//DISS_dates//DISS_manuscript_date").text = request.form['pubdate']
            # set degree
            metadata_tree.find("//DISS_description//DISS_degree//DISS_degree_abbreviation").text = \
            request.form['degreename'].split(",")[0]
            metadata_tree.find("//DISS_description//DISS_degree//DISS_degree_name").text = \
            request.form['degreename'].split(",")[1]

            metadata_tree.find("//DISS_description//DISS_inst_department").text = "Accounting"
            # set advisors
            # metadata_tree.find("//DISS_description//DISS_advisor//DISS_name//DISS_surname").text = "AdvisorL"
            # metadata_tree.find("//DISS_description//DISS_advisor//DISS_name//DISS_fname").text = "AdvisorF"
            # metadata_tree.find("//DISS_description//DISS_advisor//DISS_name//DISS_order").text = "1"

            # set committe members
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
                    cmtemembers[1].find("//DISS_name//DISS_surname").text = request.form.getlist('secondcmtemember')[1]
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
                    cmtemembers[6].find("//DISS_name//DISS_surname").text = request.form.getlist('seventhcmtemember')[1]
            # metadata_tree.find("//DISS_description//DISS_cmte_member//DISS_name//DISS_surname").text = "CmteL"
            # metadata_tree.find("//DISS_description//DISS_cmte_member//DISS_name//DISS_fname").text = "CmteF"
            # metadata_tree.find("//DISS_description//DISS_cmte_member//DISS_name//DISS_order").text = "1"
            # set categories
            metadata_tree.find("//DISS_description//DISS_categorization//DISS_category//DISS_cat_code").text = "0537"
            metadata_tree.find("//DISS_description//DISS_categorization//DISS_category//DISS_cat_desc").text = "Engineering"
            # set embargo
            if request.form['availability'] == "open access":
                metadata_tree.find("//DISS_repository//DISS_access_option").text = "Research:open"
            else:
                metadata_tree.find("//DISS_repository//DISS_access_option").text = "9575220150002976"
                metadata_tree.find("//DISS_repository//DISS_delayed_release").text = request.form['availability']
            # set keywords
            keywords = metadata_tree.findall("//DISS_description//DISS_categorization//DISS_keyword")
            for i, keyword in enumerate(request.form.getlist('keywords')):
                if keyword:
                    keywords[i].text = keyword
            # set abstract
            for i, paragraph in enumerate(request.form['abstract'].split('\r\n')):
                if paragraph.strip():
                    para = etree.SubElement(metadata_tree.find("//DISS_content//DISS_abstract"), "DISS_para")
                    para.text = paragraph
            # set language - default is en
            # metadata_tree.find("//DISS_description//DISS_categorization//DISS_language").text = request.form['language']

            # set file names
            file_name = request.form['authorlname'] + "_" + request.form['authorfname'] + "_" + ''.join(
                e for e in request.form['title'] if e.isalnum())
            # the xml file MUST be called "metadata.xml"
            xml_file = "metadata.xml"
            txt_file = file_name + ".txt"
            zip_file = file_name + ".zip"

            open(xml_file, 'wb').write(etree.tostring(metadata_tree, pretty_print=True))

            # create the zip file and write uploaded files and metadata to it
            # contextlib.closing needed for python 2.6
            with contextlib.closing(ZipFile(zip_file, "w")) as depositzip:
                depositzip.write(xml_file)
                for file in request.files.getlist("files"):
                    file.save(file.filename)
                    depositzip.write(file.filename)

            # encode the zip file and create sword call file
            encodedzip = base64.b64encode(open(zip_file, 'rb').read()).decode()
            sword_call = open('static/deposit.txt', 'r').read().format(encoding=encodedzip)
            open(txt_file, 'w').write(sword_call)

            # set request variables and make call
            deposit_url = config.deposit_url.format(username=config.deposit_username, password=config.deposit_password)

            headers = {
                'Content-Type': 'multipart/related; boundary=---------------1605871705;  type="application/atom+xml"',
                "On-behalf-of": config.deposit_obo}

            data = open(txt_file, 'rb').read()
            print("sending file")
            r = requests.post(deposit_url, headers=headers, data=data)

            # delete the files
            for file in request.files.getlist("files"):
                os.remove(file.filename)
            os.remove(zip_file)
            os.remove(xml_file)
            os.remove(txt_file)

            logging.info('deposit made for ' + request.form['authorfname'] + request.form['authorlname'])
            clearsession()

            return render_template("deposit_result.html", response=r.text, status=r.status_code, form=request.form,
                                   files=request.files)

if __name__ == '__main__':
    app.run()

