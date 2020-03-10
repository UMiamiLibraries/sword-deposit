# Flask SWORD deposit
This application is a web form for depositing ETDs into UMs Esploro environment.

For more information on Esploro, visit  [Ex Libris Esploro](https://www.exlibrisgroup.com/products/esploro-research-services-platform/)

## Components
* This is built on [Flask](https://flask.palletsprojects.com/en/1.1.x/), a web app framework for Python.
* Front end uses [Jinja](https://jinja.palletsprojects.com/en/2.11.x/) (built into Flask) and [Bootstrap](https://getbootstrap.com/) for styling.
* For the full list of required Python libraries, check requirements.txt, but in general it requires [lxml](https://lxml.de/) and [requests](https://requests.readthedocs.io/en/master/).
All other libraries are built in to Python Standard Library.

## How it works
### User journey
1. User will select a deposit type, either Dissertation or Master's.
2. User will be provided the UM Institutional Deposit Agreement. They are required to agree before proceeding.
3. User will fill out form according to the ETD they are depositing, attach the full text and any other necessary files, and submit
   * see "Deposit" section for backend logic
4. User will see the result of their deposit and a summary of their deposit form.

### Deposit
Each deposit requires three files to be created (plus files uploaded by user).
Two templates exist to be copied and filled out for each request: medata_template.xml and deposit.txt. 
The third file is a zip file containing metadatal.xml and all content files.

For each deposit:
1. Create a copy of metadata_template.xml -> metadata.xml and deposit.txt -> <deposit_name>.txt
2. Fill out metadata.xml with the form data
3. The metadata.xml and uploaded content files are zipped together -> <deposit_name>.zip
4. Generate the base64 encoding of the <deposit_name>.zip and insert that into the <deposit_name>.txt file
5. Create a requests 'POST' call to the sword server, attaching deposit.txt as data
   * a successful deposit yields a 201

