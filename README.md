# pydocu

fastapi server for classification of documents and extraction of data

## start server
```
source env/bin/activate
export TRANSFORMERS_CACHE=./build 
uvicorn main:app --reload --workers 10
```

openpai starts at 
```
http://127.0.0.1:8000/docs
```

The following directories must be provided on the server:
</br>```/home/pydoc``` - all temporary files for the processing
</br>```/home/build``` - the AI models buffered

These directories are Azure compliant under /home for persistent data.
Otherwise the directories ```./pydoc```und ```./build``` used. In an Azure instance, these directories are no longer available after a restart - please note that.

## Function overview

### login
we use bearer token via url
```
/token
```
with username and password, example ist "admin" password "test" - change please.

All further accesses must be made with the token

Attention: the application does not manage a user DB; there is a user "Admin" in the code with the hash - this must be implemented individually. There is a servcies that provides the hash for a password, so that you can write this hash into the code for testing. This is not a productive solution and must be adapted individually.

### GET "/" - get main info
Overview of the installed information, about the user and the tenants used.

```
{
  "name": "pydocu",
  "description": "Services for processing documents.",
  "version": "0.1.0",
  "datetime": "2023-01-22T11:25:32.455365+01:00",
  "ghostscript": "GPL Ghostscript 9.56.1 (2022-04-04)",
  "tesseract": "tesseract 5.3.0",
  "models": "yes",
  "temp_dir": "./pydoc",
  "status": {
    "tenants": [
      "1000"
    ],
    "background_tasks": 0
  },
  "user": {
    "username": "<...>",
    "email": "<...>",
    "full_name": "<...>",
    "tenants": [
      "1000"
    ],
    "roles": [
      "admin"
    ],
    "disabled": false,
    "hashed_password": "<...>"
  }
}

```

The application uses ghostscript for conversion and tesseract for OCR. These applications can be installed via a service. The call is done via shel commands.

## POST "/install/{phrase}" - Installed asynchronously
args: phrase with gs, tesseract or models

The installation is performed via ```/usr/bin/apt-get``` a linux installation - alternatively, the applications can also be installed manually.

Tesseract is installed in the German variant.

## POST "/api/tenant" - define a new tenant
A separate directory is created for the tenant. Master data - e.g. sender and recipient search can be defined for each tenant. If a new document is transferred for processing, the tenant ID must also be entered. The permissible tenant ID can be specified in the user authorization.

## GET "/api/tenant/{id}" - provides all current information on a tenant
```
    return {"data": {
        "id": tenant.id,
        "name": tenant.name,
        "files": files, 
        "count": len(files),
        "classes": classes_count,
        "senders": senders_count,
        "receivers": receivers_count,
        "entities": entities_count,
        "documents counter": tenant.count_documents,
        "pages counter": tenant.count_pages,
        }}
```

## POST "/api/delete_tenant/{id}" - delete the tenant files and directory
All files and the directory to the tenant will be deleted - be careful.

## POST "/api/master_data/{list_name}/{tenant}" - Transfer of master data for "sender", "receiver" or "entities" to a tenant
Die Daten werden als txt Dateien im Verzeichnis zum Tenant abgelegt und bei Bedarf gelesen.

## AI Models
<a href="https://huggingface.co/Sahajtomar/German_Zeroshot?candidateLabels=Verbrechen%2CTrag%C3%B6die%2CStehlen&multiClass=false&text=Letzte+Woche+gab+es+einen+Selbstmord+in+einer+nahe+gelegenen+kolonie">german zero shot</a> 
is used for the classification of the forms

<a href="https://huggingface.co/Sahajtomar/German-semantic">compares semantics of two german sentences</a>
is used for determination of business partners, if no match was found via discrete comparison, e.g. bank account or order number

Attention: the models are so big that the application will only run on a virtual machine with at least 6 GB. Installing the models of about 1 GB each takes time and bandwidth. The models are buffered on the machine - space must be provided for this.

The application runs on a virtual Azure instance Basic B3 with 7GB. Additional memory can be mounted under /home/build, then the buffered models are located there.