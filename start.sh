source env/bin/activate
export HF_HOME=./build 
uvicorn main:app --reload --workers 10
