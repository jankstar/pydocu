source env/bin/activate
export TRANSFORMERS_CACHE=./build 
uvicorn main:app --reload --workers 10
