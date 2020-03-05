import requests, config, base64, contextlib, os
from datetime import date
from lxml import etree
from flask import Flask, render_template, request, send_file
from zipfile import ZipFile

app = Flask(__name__)

@app.route('/')
def index():
    return render_template("select-type.html", action="/agreement/")


@app.route('/agreement/', methods=['POST'])
def agreement():
    deposittype = request.form['deposittype']
    return render_template('agreement.html', action="/deposit-form/", deposittype=deposittype)


@app.route('/deposit-form/', methods=['POST'])
def depositform():
    deposittype = request.form['deposittype']
    if deposittype == "dissertation":
        return render_template("dissertation_form.html", action="/deposit/")
    elif deposittype == "masters":
        return render_template("masters_form.html", action="/deposit/")


@app.route("/um-agreement-pdf/", methods=['GET'])
def downloadagreement():
    try:
        return send_file(filename='um_agreement.pdf')
    except Exception as e:
        return str(e)


@app.route('/deposit/', methods=['POST'])
def deposit():
    print("in deposit)")
    # load blank metadata tree
    metadata_tree = etree.parse('metadata_template.xml')
    # populate fields from form
    metadata_tree.find("//DISS_author//DISS_name//DISS_surname").text = request.form['lname']
    metadata_tree.find("//DISS_author//DISS_name//DISS_fname").text = request.form['fname']
    metadata_tree.find("//DISS_author//DISS_name//DISS_middle").text = request.form['mname']
    metadata_tree.find("//DISS_author//DISS_permanent_email").text = request.form['email']
    metadata_tree.find("//DISS_description//DISS_title").text = request.form['title']
    metadata_tree.find("//DISS_description//DISS_dates//DISS_degree_date").text = "2017-01-01"
    metadata_tree.find("//DISS_description//DISS_dates//DISS_manuscript_date").text = date.today().strftime("%Y-%m-%d")
    metadata_tree.find("//DISS_description//DISS_degree//DISS_degree_abbreviation").text = "Ph.D."
    metadata_tree.find("//DISS_description//DISS_degree//DISS_degree_name").text = "Ph.D."
    metadata_tree.find("//DISS_description//DISS_inst_department").text = "Ph.D"
    metadata_tree.find("//DISS_description//DISS_advisor//DISS_name//DISS_surname").text = "AdvisorL"
    metadata_tree.find("//DISS_description//DISS_advisor//DISS_name//DISS_fname").text = "AdvisorF"
    metadata_tree.find("//DISS_description//DISS_advisor//DISS_name//DISS_order").text = "1"
    metadata_tree.find("//DISS_description//DISS_cmte_member//DISS_name//DISS_surname").text = "CmteL"
    metadata_tree.find("//DISS_description//DISS_cmte_member//DISS_name//DISS_fname").text = "CmteF"
    metadata_tree.find("//DISS_description//DISS_cmte_member//DISS_name//DISS_order").text = "1"
    metadata_tree.find("//DISS_description//DISS_categorization//DISS_category//DISS_cat_code").text = "0537"
    metadata_tree.find("//DISS_description//DISS_categorization//DISS_category//DISS_cat_desc").text = "Engineering"
    keywords = metadata_tree.findall("//DISS_description//DISS_categorization//DISS_keyword")
    for keyword in request.form.getlist('keywords'):
        if keyword:
            keywords[request.form.getlist('keywords').index(keyword)].text = keyword
    metadata_tree.find("//DISS_content//DISS_abstract//DISS_para").text = request.form['abstract']

    file_name = request.form['lname'] + "_" + request.form['fname'] + "_" + ''.join(e for e in request.form['title'] if e.isalnum())
    # the xml file MUST be called "metadata.xml"
    xml_file = "metadata.xml"
    txt_file = file_name + ".txt"
    zip_file = file_name + ".zip"
    print(xml_file + " - " + txt_file + " - " + zip_file)
    open(xml_file, 'wb').write(etree.tostring(metadata_tree, pretty_print=True))

    file = ''
    if 'file' in request.files:
        file = request.files['file']
        file.save(file.filename)
    print("file created")
    # create the zip file
    # contextlib.closing needed for python 2.6
    with contextlib.closing(ZipFile(zip_file, "w")) as depositzip:
        depositzip.write(xml_file)
        if file:
            depositzip.write(file.filename)

    # encode the zip file and create sword call file
    encodedzip = base64.b64encode(open(zip_file, 'rb').read()).decode()
    sword_call = open('deposit.txt', 'r').read().format(encoding=encodedzip)
    open(txt_file, 'w').write(sword_call)

    # set request variables
    deposit_url = config.deposit_url.format(username=config.deposit_username, password=config.deposit_password)
    # DO NOT TOUCH BELOW
    headers = {'Content-Type': 'multipart/related; boundary=---------------1605871705;  type="application/atom+xml"',
               "On-behalf-of": config.deposit_obo}

    data = open(txt_file, 'rb').read()
    print("sending file")
    r = requests.post(deposit_url, headers=headers, data=data)

    # delete the files
    #if file:
    #    os.remove(file.filename)
    #os.remove(zip_file)
    #os.remove(xml_file)
    #os.remove(txt_file)

    return render_template("deposit_result.html", response=r.text, status=r.status_code)


@app.route('/test/', methods=['POST'])
def test():
    print(date.today().strftime("%Y-%m-%d"))
    print(request.form)
    metadata_tree = etree.parse('metadata_template.xml')
    keywords = metadata_tree.findall("//DISS_description//DISS_categorization//DISS_keyword")
    for keyword in request.form.getlist('keywords'):
        print(keyword)
        keywords[request.form.getlist('keywords').index(keyword)].text = keyword


    file_name = request.form['lname'] + "_" + request.form['fname'] + "_" + ''.join(e for e in request.form['title'] if e.isalnum())
    # the xml file MUST be called "metadata.xml"
    xml_file = "metadata.xml"
    txt_file = file_name + ".txt"
    zip_file = file_name + ".zip"
    print(xml_file + " - " + txt_file + " - " + zip_file)
    open(xml_file, 'wb').write(etree.tostring(metadata_tree, pretty_print=True))
    return render_template("deposit_result.html", response="hi", status="hi")


if __name__ == '__main__':
    app.run(debug=True)

