import time

from fastapi import BackgroundTasks, FastAPI

app = FastAPI()
def write_log1(email:str,content:str):
    while True:
        print(f"正在给{email}发送信息，str...")
        time.sleep(1)

@app.get("/send-task/{email}")
async def send_task(email:str,backgroundTasks:BackgroundTasks):
    backgroundTasks.add_task(write_log1,email,"hello")
    # print("开始执行任务")
    # time.sleep(5)
    # print("任务结束")
    return {"message":"任务执行完成"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)