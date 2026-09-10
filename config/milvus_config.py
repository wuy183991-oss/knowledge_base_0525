
from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()

@dataclass #自动get set方法
class MilvusConfig:
    milvus_url:str
    chunks_collection:str
    items_collection:str

milvus_config = MilvusConfig(
    milvus_url = os.getenv("MILVUS_URL"),
    chunks_collection = os.getenv("CHUNKS_COLLECTION"),
    items_collection = os.getenv("ITEM_NAME_COLLECTION")
)