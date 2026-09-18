from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI()

class Item(BaseModel):
    name: str
    price: float
    is_offer: bool = None

@app.post("/items")
def create_item(item: Item):
    print("create_item后端接口被访问")
    return item

@app.get("/root_read")
def read_root():
    print("root_read 被访问了")
    print("root_read 被访问了")
    print("root_read 被访问了")
    return {"Hello": "World"}

@app.get("/items/{item_id}")
def read_item(item_id:int,a:str):
    print("read_item后端有参数接口被访问")
    return {"item_id": item_id}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)