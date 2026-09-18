"""
查询流程的接口定义
"""

from pathlib import Path
import sys
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse

from fastapi import BackgroundTasks, FastAPI, Request

project_root = Path(__file__).absolute().parent.parent.parent
sys.path.insert(0, str(project_root))

from processor.query_process.main_graph import KBQueryWorkflow
from utils.sse_utils import create_sse_queue, sse_generator
from utils.task_utils import TASK_STATUS_PROCESSING, get_task_result, update_task_status

class QueryRequest(BaseModel):
    query:str
    session_id:str
    is_stream:bool

app = FastAPI()

@app.get("/chat.html")
async def chat():
    current_dir_parent_path = Path(__file__).absolute().parent.parent
    chat_html_path = current_dir_parent_path / "page" / "chat.html"
    return FileResponse(chat_html_path)

@app.post("/query")
async def query(backgroundTasks:BackgroundTasks,query:QueryRequest):
    user_query = query.query
    session_id = query.session_id
    is_stream = query.is_stream

    if is_stream:
        create_sse_queue(session_id)

    update_task_status(session_id,TASK_STATUS_PROCESSING,is_stream) #记录进度

    if is_stream:
        backgroundTasks.add_task(run_query_graph,session_id,user_query,is_stream) #run_query_graph调用工作流
        return {"message":"任务已经开始，请耐心等待","session_id":session_id}
    else:
        run_query_graph(session_id,user_query,is_stream)
        answer = get_task_result(session_id,"answer","")
        return {
            "message":"处理完成",
            "session_id":session_id,
            "answer":answer
        }

def run_query_graph(session_id:str,user_query:str,is_stream:bool):
    print("调用搜索工作流 ")

    init_state = {
        "original_query":user_query,
        "session_id":session_id,
        "is_stream":is_stream
    }

    workflow = KBQueryWorkflow()
    for chunk in workflow.run(init_state,stream=is_stream):
        pass


@app.get("/stream/{session_id}")
async def stream(session_id:str,request:Request):
    print("追踪生成结果。。。")
    return StreamingResponse(
        sse_generator(session_id,request),
        media_type="text/event-stream",
        headers={
            "Cache-Control":"no-cache",
            "Connection":"keep-alive",
            "X-Accel-Buffering":"no"
        }
    )
    
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
