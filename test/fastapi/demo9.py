
import asyncio

from fastapi import FastAPI
from starlette.responses import StreamingResponse

app = FastAPI()

#普通流式方法，用了yield 没用return
async def generate_stream():
    words = ["你","好","，","吗"]
    for word in words:
        await asyncio.sleep(0.5)
        yield word

#流式输出接口
@app.get("/stream")
async def stream_response():
    print("流式输出的web接口")
    return StreamingResponse(generate_stream(),media_type = "text/event-stream")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)