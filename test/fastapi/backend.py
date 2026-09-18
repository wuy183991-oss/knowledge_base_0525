from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

#cors 跨域允许协议
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  #允许所有的源
    allow_credentials=True, #允许客户端传递cookie
    allow_methods=["*"], #get 和 post都行
    allow_headers=["*"], #请求头所有信息都行
)

@app.get("/api/data")
async def get_data():
    print("请求后端数据结构服务")
    return{"message": "这是后端数据","status":"success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)