# pydocu

fastapi server for classification of documents and extraction of data

##start
```
source env/bin/activate
export TRANSFORMERS_CACHE=./build 
uvicorn main:app --reload --workers 10
```

openpai starts at 
```
http://127.0.0.1:8000/docs
```

## Function overview

### login
we use bearer token via url
```
/token
```
with username and password

### GET "/" - get main info
Overview of the installed information, about the user and the tenants used.

```
{
  "name": "pydocu",
  "description": "Services for processing documents.",
  "version": "0.1.0",
  "datetime": "2023-01-22T11:25:32.455365+01:00",
  "ghostscript": "GPL Ghostscript 9.56.1 (2022-04-04)",
  "tesseract": "tesseract 5.2.0",
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
