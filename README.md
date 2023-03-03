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

example:
```
{
  "id": "1000",
  "name": "PyDoc GmbH"
}
```

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
The data is stored as txt files in the directory to the tenant and read on demand.

Example:
``` 
{"entities": [
  { 
    "id": "LIFNR/70000", 
    "name": "Hans Müller-Lüdenscheid", 
    "receiver_id": "BUKRS/1000", 
    "sender_id": "", 
    "address": "Hauptstr. 100, 1000 Berlin", 
    "tax_id": "", 
    "iban": "", 
    "tel": "", 
    "email": "hans.mueller-luedenscheid@gmail.com", 
    "exact": "", 
    "similar": "", 
    "regexp": ""
  }, { 
    "id": "LIFNR/70001", 
    "name": "Krueger", 
    "receiver_id": "BUKRS/1000", 
    "sender_id": "", 
    "address": "Hauptstr 101, 1000 Berlin", 
    "tax_id": "", 
    "iban": "", 
    "tel": "", 
    "email": "hans-juergen.krueger@gmail.com", 
    "exact": "", 
    "similar": "", 
    "regexp": ""
  }]
}
```

## POST "/api/classes/{tenant}" - Define classification classes
Example:
```
{"labels": [
  "Rechnung", "Schlussrechnung", "Abschlag", "Abschlagsrechnung", "Zahlungsaufforderung", "Zahlung", "Vorauszahlung", 
  "Mahnung", "Zahlungserinnerung", "Auftrag", "Auftragsbest\u00e4tigung", "B\u00fcrgschaft", "K\u00fcndigung", 
  "Jahresrechnung", "Monatsrechnung", "Miete", "Mietrechnung", 
  "Geb\u00fchr", "Geb\u00fchrenbescheid", "Bescheid", "Guthaben"
  ]
}
```

## POST "/api/new_document/{tenant}" - new document for processing
Transfer a new document for processing.

example:
``` 
{
  "id": "",
  "ext_id": "20230203/18:00:01",
  "inputpath": "pdf",
  "base64": "<****>",
  "email_text": "",
  "langu": "deu"
}
```
An ID can be provided, otherwise it will be generated. The ID is used to access the document later to read the status and the results.

A base64 data block is required, in which the document is stored as a pdf.

The processing takes place in the background in various steps:
10 - save as pdf
20 - convert page to jpg
30 - ocr
40 - classification
41 - find receiver
42 - find sender
43 - find entities
51 - find date 
99 - end

## POST "/api/do_parse/{tenant}/{id}" - Perform parse text-data from template
This function parses with the library invoice2data based on yaml-templates based on regex formulas

see <a href="https://pypi.org/project/invoice2data/">invoice2data</a>

The files must be located in the  ```template``` subdirectory of the tenant.

## GET "/api/document/{tenant}/{id}" - Provides the status and data for the document
With this function the processing status is read out - when the step "99 - end" is reached, the processing is also finished. The result of the processing is available.

The sender, the receiver and the entities with the highest score.

example:
```
{
  "id": "a8fb6152-fc2f-4d35-a257-243b68242217",
  "ext_id": null,
  "inputpath": "pdf",
  "base64": "<***>",
  "email_text": null,
  "langu": "deu",
  "created_at": "2022-09-11T17:50:42.933206+02:00",
  "task": "99 - end",
  "tenant_id": "1000",
  "filename": "./pydoc/1000/a8fb6152-fc2f-4d35-a257-243b68242217",
  "ocr_all": "<* all pages *>",
  "ocr_p1": "<* page 1 *>",
  "pages": 1,
  "protocol": [
    "2022-09-11T17:50:42.933172+02:00/I - init new document",
    "2022-09-11T17:50:42.934290+02:00/10 - save as pdf",
    "2022-09-11T17:50:42.935085+02:00/20 - convert page to jpg",
    "2022-09-11T17:50:43.621445+02:00/ GPL Ghostscript 9.56.1 (2022-04-04)\nCopyright (C) 2022 Artifex Software, Inc.  All rights reserved.\nThis software is supplied under the GNU AGPLv3 and comes with NO WARRANTY:\nsee the file COPYING for details.\nProcessing pages 1 through 1.\nPage 1\n",
    "2022-09-11T17:50:43.622931+02:00/30 - ocr",
    "2022-09-11T17:50:43.623012+02:00/03 - ocr file:a8fb6152-fc2f-4d35-a257-243b68242217page001.jpg",
    "2022-09-11T17:50:58.183496+02:00/ tesseract ready",
    "2022-09-11T17:50:58.185273+02:00/40 - classification",
    "2022-09-11T17:51:39.655181+02:00/41 - find receiver",
    "2022-09-11T17:51:46.139791+02:00/42 - find sender",
    "2022-09-11T17:51:46.141156+02:00/43 - find entities",
    "2022-09-11T17:51:50.285902+02:00/51 - find date ",
    "2022-09-11T17:51:50.286054+02:00/99 - end"
  ],
  "classification": [
    { "label": "Rechnung", "score": 6.586556136608124 },
    { "label": "Schlussrechnung", "score": 6.088626384735107 },
    { "label": "Abschlag", "score": 5.9678588062524796 },
    { "label": "Abschlagsrechnung", "score": 5.68193644285202 },
    { "label": "Zahlungsaufforderung", "score": 5.645296350121498 }
  ],
  "senders": [
    {
      "item": {
        "id": "LIFNR/70000",
        "name": "xyz",
        "receiver_id": "BUKRS/1000",
        "sender_id": "",
        "address": "xyz",
        "tax_id": "",
        "iban": "",
        "tel": "",
        "email": "xyz@gmail.com",
        "exact": "",
        "similar": "",
        "regexp": ""
      },
      "score": 100.0,
      "method": ""
    }
  ],
  "receiver": [
    {
      "item": {
        "id": "BUKRS/1000",
        "name": "abc",
        "receiver_id": "",
        "sender_id": "",
        "address": "",
        "tax_id": "",
        "iban": "",
        "tel": "",
        "email": "",
        "exact": "",
        "similar": "abc",
        "regexp": ""
      },
      "score": 38.43818008899689,
      "method": "similar"
    },
    {
      "item": {
        "id": "BUKRS/1001",
        "name": "def",
        "receiver_id": "",
        "sender_id": "",
        "address": "",
        "tax_id": "",
        "iban": "",
        "tel": "",
        "email": "",
        "exact": "",
        "similar": "def",
        "regexp": ""
      },
      "score": 36.11149191856384,
      "method": "similar"
    },
    {
      "item": {
        "id": "BUKRS/1002",
        "name": "ghj",
        "receiver_id": "",
        "sender_id": "",
        "address": "",
        "tax_id": "",
        "iban": "",
        "tel": "",
        "email": "",
        "exact": "",
        "similar": "ghj",
        "regexp": ""
      },
      "score": 34.47766900062561,
      "method": "similar"
    }
  ],
  "entities": [
    {
      "item": {
        "id": "1000/WE1000",
        "name": "lmn",
        "receiver_id": "BUKRS/1000",
        "sender_id": "",
        "address": "",
        "tax_id": "",
        "iban": "",
        "tel": "",
        "email": "",
        "exact": "",
        "similar": "lmn",
        "regexp": ""
      },
      "score": 22.262464463710785,
      "method": "similar"
    }
  ],
  "data": {
    "sender_id": "LIFNR/70000",
    "receiver_id": "BUKRS/1000",
    "datum": null
  }
}

```

## POST "/api/delete_document/{tenant}/{id}" 
Delete the data for a document.


## test functions
```POST "/api/predict_sts" ``` - compares semantics of two sentences</br>
```POST "/api/predict_zs"``` - semantic classification of a sentence</br>

```GET "/api/find_date"``` - find date in param string by regexe as document date (testing regex)</br>


```GET "/api/hash_password/{password}"```- print hash of an string

## AI Models
<a href="https://huggingface.co/Sahajtomar/German_Zeroshot?candidateLabels=Verbrechen%2CTrag%C3%B6die%2CStehlen&multiClass=false&text=Letzte+Woche+gab+es+einen+Selbstmord+in+einer+nahe+gelegenen+kolonie">german zero shot</a> 
is used for the classification of the forms

<a href="https://huggingface.co/Sahajtomar/German-semantic">compares semantics of two german sentences</a>
is used for determination of business partners, if no match was found via discrete comparison, e.g. bank account or order number

Attention: the models are so big that the application will only run on a virtual machine with at least 6 GB. Installing the models of about 1 GB each takes time and bandwidth. The models are buffered on the machine - space must be provided for this.

The application runs on a virtual Azure instance Basic B3 with 7GB. Additional memory can be mounted under /home/build, then the buffered models are located there.