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

### "/" - get main info

