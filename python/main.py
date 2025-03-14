import os
import logging
import pathlib
from fastapi import FastAPI, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi import FastAPI, Form, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel
from contextlib import asynccontextmanager
import json
from typing import List
import hashlib
from pathlib import Path


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"
db = pathlib.Path(__file__).parent.resolve() / "db" / "mercari.sqlite3"

# Define the path to the images & sqlite3 database & JSON folder
BASE_DIR = pathlib.Path(__file__).parent.resolve()
images = BASE_DIR / "images"
db = BASE_DIR / "db" / "mercari.sqlite3"
json_file = BASE_DIR / "JSON" / "items.json" 

def get_db():
    if not db.exists():
        yield

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()


# STEP 5-1: set up the database connection
def setup_database():
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_database()
    yield


app = FastAPI(lifespan=lifespan)

logger = logging.getLogger("uvicorn")
logger.level = logging.INFO
images = pathlib.Path(__file__).parent.resolve() / "images"
images = BASE_DIR / "images"
origins = [os.environ.get("FRONT_URL", "http://localhost:3000")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


class HelloResponse(BaseModel):
    message: str
# class HelloResponse(BaseModel):
#     message: str


@app.get("/", response_model=HelloResponse)
def hello():
    return HelloResponse(**{"message": "Hello, world!"})
# @app.get("/", response_model=HelloResponse)
# def hello():
#     return HelloResponse(message = "Hello, world!")


class AddItemResponse(BaseModel):
    message: str


class Item(BaseModel):
    name: str
    category: str  # add category
    image_name: str # add image_name

class GetItemResponse(BaseModel):
    name: str
    category: str
    image_name: str

# class GetImageResponse(BaseModel):
#     message: str
    # items: List[GetItemImages]

class GetItemsResponse(BaseModel):
    items: List[Item]
# messageはgetitem関数で返してないので、いらない

# JSON ファイルの読み込み
def load_items():
    if json_file.exists():
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            resdata = []
            for i in data["items"]:
                # reset to "Nan" if there is no "image_name"
                image_name = i.get("image_name", "Nan")
                # should be an instance of Item class!!
                ele = Item(name=i["name"], category=i["category"], image_name=image_name)
                resdata.append(ele)
            return resdata  # List of GetItemimage objects
        except json.JSONDecodeError:
            return []    # empty list if JSON is invalid
    else:
        return []   # return empty list is file does not exist

# JSON ファイルへの保存
def save_items(items):
    json_file.parent.mkdir(parents=True, exist_ok=True)  # フォルダがない場合は作成
    items_dict = {"items": [{"name": item.name, "category": item.category, "image_name": item.image_name} for item in items]}  # convert Pydantic objects to dict
    with open(json_file, "w") as f:
        json.dump(items_dict, f, indent=4, ensure_ascii=False)

# def insert_item(item:Item, db: sqlite3.Connection):
#     # STEP 4-2: add an implementation to store an item
#     cursor = db.cursor()
#     cursor.execute("INSERT INTO items (name, category) VALUES (?, ?)", (item.name, item.category))
#     db.commit()

# create an endpoint (Step4-4)
# @app.get("/items", response_model = GetImageResponse)
# def get_items():
#     items = load_items()
#     return GetImageResponse(items=items)
# getimageresponseだと画像の方のクラス（この場合はアイテムのリストを返したい）

@app.get("/items", response_model = GetItemsResponse)
def get_items():
    items = load_items()
    return GetItemsResponse(items=items)

# add_item is a handler to add a new item for POST /items .
@app.post("/items", response_model=AddItemResponse)
async def add_item(
    name: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
    category: str = Form(...),   # add category
    image: UploadFile = File(...),  # recieve an image
    # db: sqlite3.Connection = Depends(get_db),
):
    if not name:
        raise HTTPException(status_code=400, detail="name is required")


    # return AddItemResponse(**{"message": f"item received: {name}"})
    if not category:
        raise HTTPException(status_code=400, detail="category is required")

    image_content = await image.read()

    # SHA-256でハッシュ化したファイル名を生成
    hashed_name = hashlib.sha256(image_content).hexdigest() + ".jpg"

    # 画像の保存先ディレクトリ (images フォルダに保存)
    image_path = images / hashed_name
    image_path.parent.mkdir(parents=True, exist_ok=True)  # imagesディレクトリが存在しない場合、作成

    with open(image_path, "wb") as f:
        f.write(image_content)  # 画像ファイルを保存   

    # 画像名を商品データに追加
    new_item = Item(name=name, category=category, image_name=hashed_name)

    insert_item(new_item)


    # # load current data
    # data = load_items()
    # data.append(new_item)

    # # save to JSON file
    # save_items(data)

    # return the list of all items
    # return GetImageResponse(
    #     message="Items: ",
    #     items=[GetItemImages(name=item.name, category=item.category, image_name=item.image_name) for item in data]                  
    # )
    # return GetImageResponse(
    #     message="Success",
    #     items=[GetItemImages(name=item.name, category=item.category, image_name=item.image_name) for item in data]
    # )
    # insert_item(Item(name=name, category=category), db)
    return AddItemResponse(**{"message": f"item received: {name} in {category}"})


# get_image is a handler to return an image for GET /images/{filename} .
@app.get("/image/{image_name}")
async def get_image(image_name):
    # Create image path
    image = images / image_name

    if not image_name.endswith(".jpg"):
        raise HTTPException(status_code=400, detail="Image path does not end with .jpg")

    if not image.exists():
        logger.debug(f"Image not found: {image}")
        image = images / "default.jpg"

    return FileResponse(path=image)


# class Item(BaseModel):
#     name: str


def insert_item(item: Item):
    # STEP 4-2: add an implementation to store an item
    # pass
    data = load_items()
    data.append(item)

    # save to JSON file
    save_items(data)

    # itemに関するファンクションなので、画像についてはここで触れない
    # image_path = images / item.image_name

    # if not image_path.exists():
    #     raise HTTPException(status_code=404, detail="Image not found")

    # return FileResponse(image_path)

@app.get("/items/{item_id}", response_model=GetItemResponse)
def get_item_by_id(item_id: int):

    items = load_items()
    # 商品IDが範囲外の場合はエラーを返す
    if item_id < 1 or item_id > len(items):
        raise HTTPException(status_code=404, detail="Item not found")
    item = items[item_id - 1]
    return GetItemResponse(name=item.name, category=item.category, image_name=item.image_name)  # item_idは1から始まるので、0インデックスに調整

    # if not image_name.endswith(".jpg"):
    #     raise HTTPException(status_code=400, detail="Image path does not end with .jpg")

    # if not image.exists():
    #     logger.debug(f"Image not found: {image}")
    #     image_path = images / "default.jpg"

    # return FileResponse(image)


# def insert_item(item: Item):
#     # STEP 4-2: add an implementaion to store an item
#     pass