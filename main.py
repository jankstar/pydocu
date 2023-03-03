import os
#from torch import margin_ranking_loss, tensor
if os.path.exists( '/home/build'):
    os.environ['TRANSFORMERS_CACHE'] = '/home/build'
else:
    os.environ['TRANSFORMERS_CACHE'] = './build'

import uvicorn
from typing import Tuple, Union, Any

import uuid
import base64
import json
import re

from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from jose import JWTError, jwt
from passlib.context import CryptContext

import asyncio
from typing import List
from enum import Enum
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import locale

from classification import Classification
pydocuClassfication = Classification()

from invoice2data_txt import main as invoice2data_txt_main


#Set time zone of the server
LOCAL_TIMEZONE = datetime.now(timezone.utc).astimezone().tzinfo
APT_GET_PATH = "/usr/bin/apt-get"
if os.path.exists( '/home/pydoc'):
    LOCAL_TEMPDIR = "/home/pydoc"
else:
    LOCAL_TEMPDIR = "./pydoc"

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "b9934564b9761d0734536bf821b67cc3883a58268aa80344e526551a62afd7e8"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "admin",
        "email": "admin.pydoc@gmail.com",
        "roles": ["admin"],
        "tenants": ["1000"],
        "hashed_password":"$2b$12$U51E9KvBGrXEnKSUHr4x7upkBTcT17jt7JKFgdwPcuwR3R7ZtRkV6", 
        #"$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "disabled": False,
    },
}

app = FastAPI(
    title="pyDocu",
    description="API for PDF documents with classification and data extraction. "+
        "The API call supports different tenants. Master data for the sender, "+
        "recipient and objects or cost centers can be stored for each tenant.",
    version="0.1.0")
""" Application for main data and function
"""

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Union[str, None] = None


class User(BaseModel):
    username: str
    email: Union[str, None] = None
    full_name: Union[str, None] = None
    tenants: list[str] = []
    roles: list[str] = []
    disabled: Union[bool, None] = None


class UserInDB(User):
    hashed_password: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """get assecc token by login """
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """get user data """
    return current_user


class PhraseEnum(str, Enum):
    gs = "gs"
    tesseract = "tesseract"
    models = "models"


class Application:
    def __init__(self):
        self.gs_path: str = ""
        self.tr_path: str = ""
        self.temp_dir: str = ""
        self.background_task: int = 0
        self.protocol: list[str] = []

    def check_options(self, tenant: str = "") -> bool:
        """check App options
        - working directory
        - tenant
        - installation of gs and tesseract

        return: True / False
        """
        if not self.temp_dir:
            self.temp_dir = LOCAL_TEMPDIR
            if not os.path.exists(self.temp_dir):
                os.mkdir(self.temp_dir)

            if not os.path.exists(self.temp_dir):
                self.temp_dir = ""
                return False

        if tenant:
            if not os.path.exists(self.temp_dir + "/" + tenant):
                return False

        if not self.gs_path:
            with os.popen("which gs") as output:
                while True:
                    lines = output.readlines()
                    if lines:
                        if "/gs" in lines[0]:
                            self.gs_path = lines[0].replace("\n", "")
                    else:
                        break

        if not self.tr_path:
            with os.popen("which tesseract") as output:
                while True:
                    lines = output.readlines()
                    if lines:
                        if "/tesseract" in lines[0]:
                            self.tr_path = lines[0].replace("\n", "")
                    else:
                        break

        return True

    def get_gs_version(self):
        if self.gs_path:
            with os.popen(self.gs_path + " -v") as output:
                while True:
                    line = output.readline().replace("\n", "")
                    break

            return line
        else:
            return ""

    def get_tr_version(self):
        if self.tr_path:
            with os.popen(self.tr_path + " -v") as output:
                while True:
                    line = output.readline().replace("\n", "")
                    break

            return line
        else:
            return ""

    def get_status(self):
        """
        get services status\n
        returns
            tenants list[str]\n
            background_tasks int
        """
        t_count = []
        files = os.listdir(self.temp_dir)
        for file in files:
            if not "." in file:
                t_count.append(file)

        return {
            "tenants": t_count,
            "background_tasks": app_data.background_task,
        }


app_data = Application()

class TenantApi(BaseModel):
    id: str = ""
    name: str = ""    

class MasterDataEnum(str, Enum):
    sender = "sender"
    receiver = "receiver"
    entities = "entities"

class EntityApi(BaseModel):
    id: str = None
    name: str = ""
    receiver_id: str = "" #
    sender_id: str = ""
    address: str = ""
    tax_id: str = ""
    iban: str = ""
    tel: str = ""
    email: str = ""
    exact: str = ""
    similar: str = ""
    regexp: str = ""

class PredictEntity(BaseModel):
    item: EntityApi
    score: float = 0.0
    method: str = ""

class Entity(EntityApi):
    def predict(self,i_str:str) -> PredictEntity:
        i_str_trim = i_str.replace(" ", "")
        if self.tax_id:
            if self.tax_id.replace(" ", "") in i_str_trim:
                 return (PredictEntity(score=100, item=self, methode="tax_id"))
                
        if self.iban:
            if self.iban.replace(" ", "").upper() in i_str_trim.upper():
                return (PredictEntity(score=100, item=self, methode="iban"))
                
        if self.tel:
            if self.tel.replace(" ", "") in i_str_trim:
                return (PredictEntity(score=100, item=self, methode="tel"))

        if self.email:
            if self.email.replace(" ", "").upper() in i_str_trim.upper():
                return (PredictEntity(score=100, item=self, methode="email"))

        if self.exact:
            if self.exact.replace("\n"," ").replace("  ", " ") in i_str.replace("\n"," ").replace("  ", " "):
                return (PredictEntity(score=100, item=self, methode="exact"))

        if self.regexp:
            if re.search(
                self.regexp,
                i_str,
                re.IGNORECASE + re.MULTILINE
            ):
                return (PredictEntity(score=100, item=self, methode="regexp"))

        if self.similar:
            perdict = pydocuClassfication.predict_sts([i_str],[self.similar])
            score: float = perdict["score"][0][0]
            return (PredictEntity(score=score*100, item=self, method="similar"))

        return None

class ModusEnum(str, Enum):
    append = "append"
    replace = "replace"
    delete = "delete"


class EntityList(BaseModel):
    entities: List[Entity] = []

class EntityListApi(EntityList):
    modus: ModusEnum = ModusEnum.append

class ClassesApi(BaseModel):
    labels: List[str] = []

class TenantSave(TenantApi):
    count_documents: int = 0
    count_pages: int = 0
    start: Union[str,None] = None

class Tenant(TenantSave):
    classes: Union[ClassesApi, None] = None
    sender: Union[EntityList,None] = None
    receiver: Union[EntityList,None] = None
    entities: Union[EntityList,None] = None

    def save(self):

        tenant_save = TenantSave.parse_obj(self)
        filename = app_data.temp_dir + "/" + self.id + "/tenant.txt"
        with open(filename, "wt") as file:
            file.write(json.dumps(jsonable_encoder(tenant_save)))        

        filename = app_data.temp_dir + "/" + self.id + "/classes.txt"
        if self.classes != None:
            with open(filename, "wt") as file:
                file.write(json.dumps(jsonable_encoder(self.classes)))

        filename = app_data.temp_dir + "/" + self.id + "/sender.txt"
        if self.sender != None:
            with open(filename, "wt") as file:
                file.write(json.dumps(jsonable_encoder(self.sender)))

        filename = app_data.temp_dir + "/" + self.id + "/receiver.txt"
        if self.receiver != None:
            with open(filename, "wt") as file:
                file.write(json.dumps(jsonable_encoder(self.receiver)))

        return

def load_tenant( id: str, classes:bool=False, sender:bool=False, receiver:bool=False, entities:bool=False) -> Tenant:
    """load all data for a tenant from txt files in tenant directory"""
    MyTenant = Tenant()
    MyTenant.id = id

    if not id:
        raise ValueError("tenant id wrong")

    filename = app_data.temp_dir + "/" + id + "/tenant.txt"
    if os.path.exists(filename):
        with open(filename, "rt") as file:
            tenant_save = TenantSave.parse_obj(json.load(file))
            MyTenant = Tenant.parse_obj(tenant_save)

    filename = app_data.temp_dir + "/" + MyTenant.id + "/classes.txt"
    if classes and os.path.exists(filename):
        with open(filename, "rt") as file:
            MyTenant.classes =  ClassesApi.parse_obj(json.load(file))

    filename = app_data.temp_dir + "/" + MyTenant.id + "/sender.txt"
    if sender and os.path.exists(filename):
        with open(filename, "rt") as file:
            MyTenant.sender = EntityList.parse_obj(json.load(file))

    filename = app_data.temp_dir + "/" + MyTenant.id + "/receiver.txt"
    if receiver and os.path.exists(filename):
        with open(filename, "rt") as file:
            MyTenant.receiver = EntityList.parse_obj(json.load(file))

    filename = app_data.temp_dir + "/" + MyTenant.id + "/entities.txt"
    if entities and os.path.exists(filename):
        with open(filename, "rt") as file:
            MyTenant.entities = EntityList.parse_obj(json.load(file))

    return MyTenant    

class ClassificationResult(BaseModel):
    label: str = ""
    score: float = 0.0

class LanguEnum(str, Enum):
    deu = "deu"
    eng = "eng"

class InputEnum(str, Enum):
    pdf = "pdf"
    email = "email"    

class DocumentApi(BaseModel):
    id: str = ""
    ext_id: Union[str, None] = None
    inputpath: InputEnum = InputEnum.pdf
    base64: Union[str, None] = None
    email_text: Union[str, None] = None
    langu: LanguEnum = LanguEnum.deu

class DocumentData(BaseModel):
    sender_id: Union[str, None] = None 
    receiver_id: Union[str, None] = None 
    datum: Union[datetime, None] = None

class Document(DocumentApi):
    created_at: str = ""
    task: str = ""
    tenant_id: str = ""
    filename: str = ""
    ocr_all: Union[str, None] = None
    ocr_p1: Union[str, None] = None
    pages: int = 0
    protocol: list[str] = []
    classification: list[ClassificationResult] = []
    senders: list[PredictEntity] = []
    receiver: list[PredictEntity] = []
    entities: list[PredictEntity] = []
    data: Union[DocumentData, None] = None
    parse: dict = None

    def save(self):
        """save data as json for async"""
        if not self.filename:
            raise ValueError("document "+self.id+" filename missing")
        with open(self.filename + ".json", "w") as file:
            file.write(json.dumps(jsonable_encoder(self)))

    def do_parse(self):
        """Perform parse text-data from template"""
        self.task = "60 - parse template "
        self.protocol.append(
            datetime.now(LOCAL_TIMEZONE).isoformat() + "/" + self.task
        )
        template_folder = app_data.temp_dir + "/" + self.tenant_id + "/template"

        if not os.path.exists(template_folder):
            #if the template directory does not exist, create it now
            os.mkdir(template_folder)
            msg = (
                datetime.now(LOCAL_TIMEZONE).isoformat()
                + "/W - "
                + self.task
                + " Warning: "
                + "template directory does not exist, create it now"
            )
            self.protocol.append(msg)            
            #there can be no templates then -> out
            return
        
        if self.ocr_all == None or self.ocr_all == "":
            msg = (
                datetime.now(LOCAL_TIMEZONE).isoformat()
                + "/W - "
                + self.task
                + " Warning: "
                + "no ocr/txt data found"
            )
            self.protocol.append(msg)            
            return

        #textfile für parsing erzeugen
        with open(app_data.temp_dir + "/"+self.id + "_parse.txt", "w") as file:
            file.write(self.ocr_all)
        
        MyArgs = dict(
            input_reader='textfile',
            emplate_folder=template_folder,
            exclude_built_in_templates=True,
            output_format='json',
            output_name=app_data.temp_dir + "/"+self.id + "_parse.json",
            input_files=app_data.temp_dir + "/"+self.id + "_parse.txt"
        )

        invoice2data_txt_main(args=MyArgs)

        with open(app_data.temp_dir + "/"+self.id + "_parse.json", "rt") as file:
            self.parse = json.load(file)

        if os.path.exists(app_data.temp_dir + "/"+self.id + "_parse.txt"):
            os.remove(app_data.temp_dir + "/"+self.id + "_parse.txt")

        if os.path.exists(app_data.temp_dir + "/"+self.id + "_parse.json"):
            os.remove(app_data.temp_dir + "/"+self.id + "_parse.json")

    def do_classification(self):
        """Performs classification for the document"""
        self.task = "40 - classification"
        self.protocol.append(
            datetime.now(LOCAL_TIMEZONE).isoformat() + "/" + self.task
        )

        tenant = load_tenant(self.tenant_id,classes=True)

        if tenant.classes != None and len(tenant.classes.labels) != 0 and self.ocr_p1:

            perdict = pydocuClassfication.predict_zs(self.ocr_p1,tenant.classes.labels)
            my_score = perdict["score"]

            result = []
            for i in range(len(tenant.classes.labels)):
                result.append({"label":tenant.classes.labels[i], "score":my_score[i]*100})

            def get_score(ele):
                return ele["score"]

            result.sort(reverse=True,key=get_score)
            self.classification = result[:5]

            self.save()

        return

    def do_find(self, list_name: str):

        if list_name == "receiver":
            self.task = "41 - find receiver"
            tenant_list = load_tenant(self.tenant_id,receiver=True).receiver
            result_list = self.receiver

        elif list_name == "sender":
            self.task = "42 - find sender"
            tenant_list = load_tenant(self.tenant_id,sender=True).sender
            result_list = self.senders
        
        elif list_name == "entities":
            self.task = "43 - find entities"
            tenant_list = load_tenant(self.tenant_id,entities=True).entities
            result_list = self.entities

        else:
            raise ValueError("list_name is wrong")

        self.protocol.append(
            datetime.now(LOCAL_TIMEZONE).isoformat() + "/" + self.task
        )

        save_true = False
        if self.ocr_all and tenant_list != None:
            for person in tenant_list.entities:
                if ((not self.data.receiver_id or 
                    ( not person.receiver_id or 
                    person.receiver_id == self.data.receiver_id)) and
                    (not self.data.sender_id or
                    ( not person.sender_id or
                    person.sender_id == self.data.sender_id))): 

                    predict = person.predict(self.ocr_all)
                    if predict != None:
                        result_list.append(predict)
                        save_true = True

        if save_true == True:

            def get_score_entity(ele:PredictEntity):
                return ele.score

            result_list.sort(reverse=True,key=get_score_entity)
            result_list = result_list[:5]

            self.save()

        return


async def async_job(command):
    line: str = ""
    with os.popen(command) as output:
        while True:
            line = output.readline()
            break
    return line


def find_date(i_str:str, langu: str="de-DE"):
    regex_list = [
        {"find": "Datum[ :]*(\d{1,2}\.\d{1,2}\.\d{4})[ \\s]*", "format": "%d.%m.%Y"},
        {"find":"(?:[A-Za-z])(?:,)(?: den)? (\d{1,2}\.\d{1,2}\.\d{4})[ \\s]", "format": "%d.%m.%Y"},

        {"find": "Datum[ :]*(\d{1,2}\.\d{1,2}\.\d{2})[ \\s]*", "format": "%d.%m.%y"},
        {"find":"(?:[A-Za-z])(?:,)(?: den)? (\d{1,2}\.\d{1,2}\.\d{2})[ \\s]", "format": "%d.%m.%y"},     

        {"find": "Datum[ :]*(\d{1,2}\. (?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember) \d{2,4})[ \\s]*", "format": "%d. %B %Y"},
        {"find":"(?:[A-Za-z])(?:,)(?: den)? (\d{1,2}\. (?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember) \d{2,4})[ \\s]", "format": "%d. %B %Y"},       
        
        {"find": " (\d{1,2}\. (?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember) \d{2,4})[ \\s]*", "format": "%d. %B %Y"},
        {"find": " (\d{1,2}\.\d{1,2}\.\d{4})[ \\s]*", "format": "%d.%m.%Y"},
        {"find": " (\d{1,2}\.\d{1,2}\.\d{2})[ \\s]*", "format": "%d.%m.%y"},

        ]

    try:
        locale.setlocale(locale.LC_TIME, )
        for ele in regex_list:
            match = re.search(ele["find"], i_str, re.MULTILINE)
            if match:
                return datetime.strptime(match.group(1), ele["format"]), None
    except Exception as err:
        return None, err
    return None, None

"""-----------------------------------"""
def background_task(document: Document, task: str = None):
    """background task for one document """
    try:
        app_data.background_task += 1
        """-----------------------------------"""
        if (task == None or task == "10") and document.inputpath == InputEnum.pdf:
            document.task = "10 - save as pdf"
            document.protocol.append(
                datetime.now(LOCAL_TIMEZONE).isoformat() + "/" + document.task
            )
            # convert to binary
            data = base64.b64decode(document.base64)

            with open(document.filename + ".pdf", "wb") as output_file:
                output_file.write(data)

            # save data as json for async
            document.save()

        """-----------------------------------"""
        if (task == None or task == "11") and document.inputpath == InputEnum.email:
            document.task = "11 - save as pdf from email"
            document.protocol.append(
                datetime.now(LOCAL_TIMEZONE).isoformat() + "/" + document.task
            )
            # convert to binary
            data = base64.b64decode(document.base64)

            with open(document.filename + ".pdf", "wb") as output_file:
                output_file.write(data)

            # save data as json for async
            document.save()

        """-----------------------------------"""
        if (task == None or task == "20") and document.inputpath == InputEnum.pdf:
            document.task = "20 - convert page to jpg"
            document.protocol.append(
                datetime.now(LOCAL_TIMEZONE).isoformat() + "/" + document.task
            )

            command = (
                app_data.gs_path
                + " -dSAFER -dBATCH -dNOPAUSE -r1200 -sDEVICE=jpeg"
                + " -sOutputFile="
                + document.filename
                + "page%03d.jpg  "
                + document.filename
                + ".pdf"
            )

            out = os.popen(command).read()
            if not out:
                out = "gs ready"
            document.protocol.append(
                datetime.now(LOCAL_TIMEZONE).isoformat() + "/ " + out
            )
            document.save()

        #todo: wenn das pdf quer gescannt wurden, dann ggf. drehen / oder tesseract mode 12 dreht automatisch 

        """-----------------------------------"""
        if task == None or task == "30":
            document.task = "30 - ocr"
            document.protocol.append(
                datetime.now(LOCAL_TIMEZONE).isoformat() + "/" + document.task
            )

            files = os.listdir(app_data.temp_dir + "/" + document.tenant_id)
            files.sort()
            document.pages = 0
            document.ocr_all = ""
            document.ocr_p1 = ""
            for file in files:
                if document.id in file:
                    if ".jpg" in file:
                        """-----------------------------------"""
                        document.task = "03 - ocr file:" + file
                        document.protocol.append(
                            datetime.now(LOCAL_TIMEZONE).isoformat()
                            + "/"
                            + document.task
                        )
                        document.pages += 1

                        command = (
                            app_data.tr_path
                            + " "
                            + app_data.temp_dir
                            + "/"
                            + document.tenant_id
                            + "/"
                            + file
                            + " "
                            + app_data.temp_dir
                            + "/"
                            + document.tenant_id
                            + "/"
                            + file
                            + " -l "
                            + document.langu
                            + " gosseract.ini"
                        )

                        out = os.popen(command).read()
                        if not out:
                            out = "tesseract ready"
                        document.protocol.append(
                            datetime.now(LOCAL_TIMEZONE).isoformat() + "/ " + out
                        )
                        document.save()

                        if os.path.exists(
                            app_data.temp_dir
                            + "/"
                            + document.tenant_id
                            + "/"
                            + file
                            + ".txt"
                        ):
                            with open(
                                app_data.temp_dir
                                + "/"
                                + document.tenant_id
                                + "/"
                                + file
                                + ".txt",
                                "rt",
                            ) as f:
                                document.ocr_all = document.ocr_all + f.read()
                                if document.pages == 1:
                                    document.ocr_p1 = document.ocr_all
                            os.remove(
                                app_data.temp_dir
                                + "/"
                                + document.tenant_id
                                + "/"
                                + file
                                + ".txt"
                            )
                        else:
                            document.protocol.append(
                                datetime.now(LOCAL_TIMEZONE).isoformat()
                                + "/ file:'"
                                + app_data.temp_dir
                                + "/"
                                + document.tenant_id
                                + "/"
                                + file
                                + ".txt' not found"
                            )
                        os.remove(
                            app_data.temp_dir + "/" + document.tenant_id + "/" + file
                        )
                        document.save()

        """-----------------------------------"""
        if task == None or task == "40":
            if pydocuClassfication.model_sts == None:
                document.task = "40 - load models for ai classification"
                document.protocol.append(
                    datetime.now(LOCAL_TIMEZONE).isoformat()
                    + "/"
                    + document.task
                )                
                pydocuClassfication.load_Models()
            document.do_classification()


        if not document.data:
            document.data = DocumentData()
                    
        """-----------------------------------"""
        if task == None or task == "41":
            document.do_find("receiver")
            if len(document.receiver) != 0:
                document.data.receiver_id = document.receiver[0].item.id  
 
        """-----------------------------------"""
        if task == None or task == "42":
            document.do_find("sender")
            if len(document.senders) != 0:
                document.data.sender_id = document.senders[0].item.id        

        """-----------------------------------"""
        if task == None or task == "43":
            document.do_find("entities")
            if len(document.entities) != 0:

                def find_first_receiver_id():
                    for entity in document.entities:
                        if entity.item.receiver_id:
                            return entity.item.receiver_id
                    return None

                def find_first_sender_id():
                    for entity in document.entities:
                        if entity.item.sender_id:
                            return entity.item.sender_id
                    return None

                if not document.data.receiver_id and find_first_receiver_id():
                    document.data.receiver_id = find_first_receiver_id()
                if not document.data.sender_id and find_first_sender_id():
                    document.data.sender_id = find_first_sender_id()

        """-----------------------------------"""
        if task == None or task == "51":

            document.task = "51 - find date "
            document.protocol.append(
                datetime.now(LOCAL_TIMEZONE).isoformat() + "/" + document.task
            )

        if document.langu == "deu":
            langu_iso = "de-DE"
        elif document.langu == "eng":
            langu_iso = "en_US"
        else:    
            langu_iso = "de-DE"

        finding_datum, err = find_date(document.ocr_p1,langu_iso)
        if finding_datum:
            if not document.data:
                document.data = DocumentData()
            document.data.datum = finding_datum
        if err:
            msg = (
                datetime.now(LOCAL_TIMEZONE).isoformat()
                + "/E - "
                + document.task
                + " Error: "
                + err.args[0]
            )
            document.protocol.append(msg)

        """-----------------------------------"""
        if task == None or task == "60":

            document.do_parse()

        """-----------------------------------"""
        document.task = "99 - end"
        document.protocol.append(
            datetime.now(LOCAL_TIMEZONE).isoformat() + "/" + document.task
        )
        # remove pdf-file
        if document.filename:
            os.remove(document.filename + ".pdf")
        document.save()

        tenant = load_tenant(document.tenant_id)
        tenant.count_documents += 1
        tenant.count_pages += document.pages
        tenant.save()

    except Exception as err:
        msg = (
            datetime.now(LOCAL_TIMEZONE).isoformat()
            + "/E - "
            + document.task
            + " Error: "
            + err.args[0]
        )
        document.protocol.append(msg)
        document.task = "99 - end"
        document.save()

        print(msg)

    app_data.background_task -= 1
    return


@app.get("/")
async def get_main(current_user: User = Depends(get_current_active_user)):
    """system informations"""
    if not len(current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect role",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # prüfen, ob gs und tesseract vorhanden
    if not app_data.check_options():
        raise HTTPException(status_code=500, detail="installation check is invalide")


    if pydocuClassfication.classifier_zs == None:
        l_msg = "no"
    else:
        l_msg = "yes"
    return {
        "name": "pydocu",
        "description": "Services for processing documents.",
        "version": "0.1.0",
        "datetime": datetime.now(LOCAL_TIMEZONE).isoformat(),  # [:-3] + 'Z',
        "ghostscript": app_data.get_gs_version(),
        "tesseract": app_data.get_tr_version(),
        "models": l_msg,
        "temp_dir": app_data.temp_dir,
        "status": app_data.get_status(),
        "user": current_user,
    }


@app.post("/install/{phrase}")
async def install_phrase(phrase: PhraseEnum, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_active_user)):
    """Installed asynchronously
    args: phrase with gs, tesseract or models"""
    if not "admin" in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect role",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not app_data.check_options():
        raise HTTPException(status_code=500, detail="installation check is invalide")

    l_msg = "{0} available".format(phrase)
    l_rcode = 0

    if phrase == PhraseEnum.gs:
        if not ("/gs" in app_data.gs_path):
            def inst_gs_taks():
                job = [
                    async_job(
                        APT_GET_PATH
                        + " -y update; "
                        + APT_GET_PATH
                        + " -y install ghostscript"
                    )
                ]
                asyncio.gather(*job)
                return

            background_tasks.add_task(inst_gs_taks)
            l_msg = "Installation {0} was started".format(phrase)

    else:
        if phrase == PhraseEnum.tesseract:
            if not ("/tesseract" in app_data.tr_path):
                def inst_tesse_taks():
                    job = [
                        async_job(
                            APT_GET_PATH
                            + " -y update; "
                            + APT_GET_PATH
                            + " -y install tesseract-ocr; "
                            + APT_GET_PATH
                            + " -y install tesseract-ocr-deu"
                        )
                    ]
                    asyncio.gather(*job)
                    return

                background_tasks.add_task(inst_tesse_taks)
                l_msg = "Installation {0} was started".format(phrase)
        else:
            if phrase == PhraseEnum.models:
                if pydocuClassfication.model_sts == None:
                    def inst_model_task():
                        app_data.background_task += 1
                        pydocuClassfication.load_Models()
                        app_data.background_task -= 1
                        return

                    background_tasks.add_task(inst_model_task)


                l_msg = "Installation {0} was started".format(phrase)
            else:

                l_msg = "phrase {0} unknown".format(phrase)
                l_rcode = 1

    if l_rcode != 0:
        raise HTTPException(status_code=500, detail=l_msg)
    return {"detail": l_msg}


@app.get("/api/tenant/{id}")
async def get_tenant(id: str, current_user: User = Depends(get_current_active_user)):
    '''provides all current information on a tenant'''
    if not id in current_user.tenants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not app_data.check_options(id):
        raise HTTPException(status_code=500, detail="installation or tenant check is invalide")

    if not os.path.exists(app_data.temp_dir + "/" + id):
        raise HTTPException(status_code=404, detail="tenant is invalide")

    files = os.listdir(app_data.temp_dir + "/" + id)
    files = [file for file in files if ".json" in file]

    tenant = load_tenant(id,classes=True)    
    classes_count = 0
    if tenant.classes != None:
        classes_count = len(tenant.classes.labels)

    tenant = load_tenant(id, sender=True)    
    senders_count = 0
    if tenant.sender != None:
        senders_count = len(tenant.sender.entities)

    tenant = load_tenant(id,receiver=True)    
    receivers_count = 0
    if tenant.receiver != None:
        receivers_count = len(tenant.receiver.entities)

    tenant = load_tenant(id, entities=True)    
    entities_count = 0
    if tenant.entities != None:
        entities_count = len(tenant.entities.entities)

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


@app.post("/api/tenant")
async def post_tenant(tenant: TenantApi, current_user: User = Depends(get_current_active_user)):
    '''define a new tenant'''
    if not tenant.id in current_user.tenants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )   
    if not app_data.check_options():
        raise HTTPException(status_code=500, detail="installation check is invalide")
    if not tenant.id:
        raise HTTPException(status_code=400, detail="tenant is invalide")
    if re.match("[^0-9A-Z]", tenant.id):
        raise HTTPException(
            status_code=400, detail="tenant id invalide - only 0-9 or A-Z"
        )
    if os.path.exists(app_data.temp_dir + "/" + tenant.id):
        raise HTTPException(status_code=404, detail="tenant already exists")
    else:
        try:
            os.mkdir(app_data.temp_dir + "/" + tenant.id)
        except Exception as err:
            raise HTTPException(
                status_code=400, detail="tenant id is invalide Error:" + err.args[0]
            )

    tenant = Tenant.parse_obj(tenant)
    tenant.start = datetime.now(LOCAL_TIMEZONE).isoformat()
    tenant.save()
    return {"data": {"tenant": tenant.id}}

@app.post("/api/delete_tenant/{id}")
async def post_delete_tenant(id:str, tenant: TenantApi, current_user: User = Depends(get_current_active_user)):
    """delete the tenant files and directory"""
    if not id in current_user.tenants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not app_data.check_options(id):
        raise HTTPException(status_code=500, detail="installation or tenant check is invalide")
    if not tenant.id or not id or tenant.id != id:
        raise HTTPException(status_code=400, detail="tenant id is invalide")

    if not os.path.exists(app_data.temp_dir + "/" + id):
        raise HTTPException(status_code=404, detail="tenant not exists")
    else:
        try:
            #alle Dateien löschen
            files = os.listdir(app_data.temp_dir + "/" + id)
            for file in files:
                os.remove(app_data.temp_dir + "/" + id + "/" + file)
            os.rmdir(app_data.temp_dir + "/" + id)

        except Exception as err:
            raise HTTPException(
                status_code=400, detail="tenant delete Error:" + err.args[0]
            )

    return {"message": "tenant id "+id+" deleted"}

@app.post("/api/master_data/{list_name}/{tenant}")
async def post_master_data(list_name:MasterDataEnum, tenant: str, entities_list: EntityListApi, current_user: User = Depends(get_current_active_user)):
    '''Transfer of master data for "sender", "receiver" or "entities" to a tenant'''
    if not tenant in current_user.tenants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )    
    if not app_data.check_options(tenant):
        raise HTTPException(status_code=500, detail="installation or tenant check is invalide")

    try:
        if not list_name in ["entities", "sender", "receiver"]:
            raise Exception("invalide url list_name")
        my_entities_list = EntityList()
        entities_txt = app_data.temp_dir + "/" + tenant + "/" + list_name + ".txt"

        if entities_list.modus == ModusEnum.append:
            if os.path.exists(entities_txt):
                with open(entities_txt, "rt") as file:
                    my_entities_list = EntityList.parse_obj(json.load(file))

            for person in entities_list.entities:
                # gleiche ID erst löschen
                my_entities_list.entities = [
                    f_person
                    for f_person in my_entities_list.entities
                    if person.id != f_person.id
                ]
                my_entities_list.entities.append(person)
            if len(my_entities_list.entities) != 0:
                with open(entities_txt, "wt") as file:
                    file.write(json.dumps(jsonable_encoder(my_entities_list)))

        elif entities_list.modus == ModusEnum.delete:
            if os.path.exists(entities_txt):
                os.remove(entities_txt)

        elif entities_list.modus == ModusEnum.replace:
            for person in entities_list.entities:
                my_entities_list.entities.append(person)
            if len(my_entities_list.entities) != 0:
                with open(entities_txt, "wt") as file:
                    file.write(json.dumps(jsonable_encoder(my_entities_list)))

        else:
            raise Exception("invalide parameter modus")

    except Exception as err:
        raise HTTPException(
            status_code=500, detail="entities not processed error:'" + err.args[0] + "'"
        )
    return {"message": "modus: '" + entities_list.modus + "' processed"}


@app.post("/api/classes/{tenant}")
async def classesApi(tenant: str, classesApi_list: ClassesApi, current_user: User = Depends(get_current_active_user)):
    if not tenant in current_user.tenants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not app_data.check_options(tenant):
        raise HTTPException(status_code=500, detail="installation or tenant check is invalide")

    try:
        my_classesApi_list = ClassesApi()
        classesApi_txt = app_data.temp_dir + "/" + tenant + "/classes.txt"

        for my_class in classesApi_list.labels:
            my_classesApi_list.labels.append(my_class)
        with open(classesApi_txt, "wt") as file:
            file.write(json.dumps(jsonable_encoder(my_classesApi_list)))

    except Exception as err:
        raise HTTPException(
            status_code=500, detail="classesApi not processed error:'" + err.args[0] + "'"
        )
    return {"message": "classesApi processed"}


@app.get("/api/document/{tenant}/{id}")
async def get_document(tenant: str, id: str, current_user: User = Depends(get_current_active_user)):
    if not tenant in current_user.tenants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not app_data.check_options(tenant):
        raise HTTPException(status_code=500, detail="installation or tenant check is invalide")

    if os.path.exists(app_data.temp_dir + "/" + tenant + "/" + id + ".json"):
        try:
            with open(
                app_data.temp_dir + "/" + tenant + "/" + id + ".json", "rt"
            ) as file:
                document = Document.parse_obj(json.load(file))

            if document.id != id:
                raise HTTPException(status_code=400, detail="no document found")
            document.base64 = "* ... *"
            return {"document": document}
        except:
            raise HTTPException(status_code=400, detail="no document found")
    else:
        raise HTTPException(status_code=400, detail="no document found")


@app.post("/api/new_document/{tenant}")
async def new_document(
    tenant: str, doc: DocumentApi, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_active_user)
):
    """new document for processing"""
    if not tenant in current_user.tenants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )    
    if not app_data.check_options(tenant):
        raise HTTPException(status_code=500, detail="installation or tenant check is invalide")

    document = Document.parse_obj(doc)

    document.tenant_id = tenant

    document.protocol.append(
        datetime.now(LOCAL_TIMEZONE).isoformat() + "/I - init new document"
    )

    if not document.id:
        document.id = str(uuid.uuid4())

    document.filename = app_data.temp_dir + "/" + document.tenant_id + "/" + document.id

    if not document.base64:
        raise HTTPException(status_code=404, detail="base64 data not valide")

    document.task = "00 - create document"
    document.created_at = datetime.now(LOCAL_TIMEZONE).isoformat()
    document.save()

    background_tasks.add_task(background_task, document)

    return {"id": document.id, "task": document.task}

@app.post("/api/do_parse/{tenant}/{id}")
async def post_do_parse(tenant: str, id: str, current_user: User = Depends(get_current_active_user)):
    if not tenant in current_user.tenants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )    
    if not app_data.check_options(tenant):
        raise HTTPException(status_code=500, detail="installation or tenant check is invalide")

    if os.path.exists(app_data.temp_dir + "/" + tenant + "/" + id + ".json"):
        try:
            with open(
                app_data.temp_dir + "/" + tenant + "/" + id + ".json", "rt"
            ) as file:
                document = Document.parse_obj(json.load(file))

            if document.id != id:
                raise HTTPException(status_code=400, detail="no document found")

            document.do_parse()

            return {"message": "document id "+id+" parsed"}
        except Exception as e:
            msg = e
            if hasattr(e, 'message'):
                msg = e.message
            raise HTTPException(status_code=400, detail="No document found or parsing error: "+msg)
    else:
        raise HTTPException(status_code=400, detail="No document found")

@app.post("/api/delete_document/{tenant}/{id}")
async def delete_document(tenant: str, id: str, current_user: User = Depends(get_current_active_user)):
    """delete document from file store"""
    if not tenant in current_user.tenants:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )    
    if not app_data.check_options(tenant):
        raise HTTPException(status_code=500, detail="installation or tenant check is invalide")

    if os.path.exists(app_data.temp_dir + "/" + tenant + "/" + id + ".json"):
        try:
            with open(
                app_data.temp_dir + "/" + tenant + "/" + id + ".json", "rt"
            ) as file:
                document = Document.parse_obj(json.load(file))

            if document.id != id:
                raise HTTPException(status_code=400, detail="no document found")

            #Dateien löschen
            files = os.listdir(app_data.temp_dir + "/" + tenant)
            for file in files:
                if id in file:
                    os.remove(app_data.temp_dir + "/" + tenant + "/" + file)

            return {"message": "document id "+id+" deleted"}
        except:
            raise HTTPException(status_code=400, detail="no document found")
    else:
        raise HTTPException(status_code=400, detail="no document found")

class Pediction_sts(BaseModel):
    s1:list[str] = [""]
    s2:list[str] = [""]
    score:list[list[float]] = []

@app.post("/api/predict_sts")
def post_test_sts(pre:Pediction_sts, current_user: User = Depends(get_current_active_user)):
    """compares semantics of two sentences"""
    if not len(current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )    
    perdict = pydocuClassfication.predict_sts(pre.s1,pre.s2)
    pre.score = perdict["score"]

    return { "data": pre }

class Pediction_zs(BaseModel):
    sequence:str = ""
    label:list[str] = [""]
    score:list[float] = []

@app.post("/api/predict_zs")
def post_test_zs(pre:Pediction_zs, current_user: User = Depends(get_current_active_user)):
    """semantic classification of a sentence"""
    if not len(current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    perdict = pydocuClassfication.predict_zs(pre.sequence,pre.label)
    pre.score = perdict["score"]

    result = []
    for i in range(len(pre.label)):
        result.append({"label":pre.label[i], "score":pre.score[i]})

    def get_score(ele):
        return ele["score"]

    result.sort(reverse=True,key=get_score)
    result = result[:5]

    return { "data": result }

@app.get("/api/find_date")
def get_find_date( i_str:str, current_user: User = Depends(get_current_active_user)):
    """find date in param string by regexe as document date"""
    if not len(current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )    
    date, err = find_date(i_str)    
    return {"date": date, "error": err}

@app.get("/api/hash_password/{password}")
def get_hash_password( password:str):
    """print hash of an string"""
    hash = pwd_context.hash(password)
    verify = pwd_context.verify(password,hash)
    return {
        "password":password,
        "hash": pwd_context.hash(password),
        "valid": verify
        }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
