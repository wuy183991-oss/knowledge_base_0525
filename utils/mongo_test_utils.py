
from dotenv import load_dotenv
import os

from pymongo import MongoClient

load_dotenv()

class HistoryMongoTool:
    def __init__(self):
        self._mongo_url = os.getenv("MONGO_URL")
        self._db_name = os.getenv("MONGO_DB_NAME")

        #连接
        self._client = MongoClient(self._mongo_url)

        #索引  相当于数据库
        self._db = self._client[self._db_name]

        #集合 相当于表
        self.chat_message = self._db["chat_message"]
        self.chat_message.create_index([("session_id",1),("ts",-1)])  #1 升序 -1 降序  ts:timestamp

_history_mongo_tool = HistoryMongoTool()

def get_history_mongo_tool():
    global _history_mongo_tool
    if _history_mongo_tool is None:
        _history_mongo_tool = HistoryMongoTool()

    return _history_mongo_tool