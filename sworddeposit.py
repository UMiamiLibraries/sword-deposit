import requests, config, base64, contextlib, os
from lxml import etree
from datetime import date, timedelta
from flask import Flask, render_template, request, send_file
from zipfile import ZipFile

app = Flask(__name__)
app_root = ''


@app.route('/')
def index():
    return render_template("select-type.html", action=app_root + "/agreement/")


@app.route('/agreement/', methods=['POST'])
def agreement():
    deposittype = request.form['deposittype']
    return render_template('agreement.html', action=app_root + "/deposit-form/", deposittype=deposittype)


@app.route('/deposit-form/', methods=['POST'])
def depositform():
    today = date.today()
    dates = {'today': today,
             'oneyear': today + timedelta(weeks=52),
             'twoyears': today + timedelta(weeks=104),
             'eighteenmonths': today + timedelta(weeks=78)}
    deposittype = request.form['deposittype']
    if deposittype == "dissertation":
        return render_template("dissertation_form_card.html", action=app_root + "/deposit/", dates=dates)
    # masters
    else:
        return render_template("masters_form.html", action=app_root + "/deposit/", dates=dates)


@app.route("/um-agreement-pdf/", methods=['GET'])
def downloadagreement():
    try:
        return send_file(filename_or_fp='static/um_agreement.pdf')
    except Exception as e:
        #return str(e)
        return str("There was an issue prossesing your request. Please contact an administrator")


@app.route('/deposit/', methods=['POST'])
def deposit():
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
    metadata_tree.find("//DISS_author//DISS_name//DISS_surname").text = request.form['lname']
    metadata_tree.find("//DISS_author//DISS_name//DISS_fname").text = request.form['fname']
    metadata_tree.find("//DISS_author//DISS_name//DISS_middle").text = request.form['mname']
    metadata_tree.find("//DISS_author//DISS_permanent_email").text = request.form['email']
    # set title
    metadata_tree.find("//DISS_description//DISS_title").text = request.form['title']
    # set pub dates
    metadata_tree.find("//DISS_description//DISS_dates//DISS_degree_date").text = "2017-01-01"
    metadata_tree.find("//DISS_description//DISS_dates//DISS_manuscript_date").text = request.form['pubdate']
    # set degree
    metadata_tree.find("//DISS_description//DISS_degree//DISS_degree_abbreviation").text = request.form['degreename'].split(",")[0]
    metadata_tree.find("//DISS_description//DISS_degree//DISS_degree_name").text = request.form['degreename'].split(",")[1]

    metadata_tree.find("//DISS_description//DISS_inst_department").text = "Accounting"
    # set advisors
    metadata_tree.find("//DISS_description//DISS_advisor//DISS_name//DISS_surname").text = "AdvisorL"
    metadata_tree.find("//DISS_description//DISS_advisor//DISS_name//DISS_fname").text = "AdvisorF"
    metadata_tree.find("//DISS_description//DISS_advisor//DISS_name//DISS_order").text = "1"
    # set committe members
    metadata_tree.find("//DISS_description//DISS_cmte_member//DISS_name//DISS_surname").text = "CmteL"
    metadata_tree.find("//DISS_description//DISS_cmte_member//DISS_name//DISS_fname").text = "CmteF"
    metadata_tree.find("//DISS_description//DISS_cmte_member//DISS_name//DISS_order").text = "1"
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
    for keyword in request.form.getlist('keywords'):
        if keyword:
            keywords[request.form.getlist('keywords').index(keyword)].text = keyword
    # set abstract
    abstractparagraphs = request.form['abstract'].split('\n\n')
    for paragraph in abstractparagraphs:
        metadata_tree.find("//DISS_content//DISS_abstract//DISS_para").text = paragraph
    # set language - default is en
    # metadata_tree.find("//DISS_description//DISS_categorization//DISS_language").text = request.form['language']

    # set file names
    file_name = request.form['lname'] + "_" + request.form['fname'] + "_" + ''.join(e for e in request.form['title'] if e.isalnum())
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

    headers = {'Content-Type': 'multipart/related; boundary=---------------1605871705;  type="application/atom+xml"',
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

    return render_template("deposit_result.html", response=r.text, status=r.status_code, form=request.form, files=request.files)


@app.route('/test/', methods=['POST'])
def test():
    print(request.form)
    return render_template("deposit_result.html", response="test", status="test")


if __name__ == '__main__':
    app.run(debug=True)

