source env/bin/activate
export HF_HOME=./build 
export MKL_THREADING_LAYER=TBB
uvicorn main:app --reload --workers 10
