
from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()

@dataclass #自动get set方法
class MineruConfig:
    base_url:str
    api_token:str

mineru_config = MineruConfig(
    base_url = os.getenv("MINERU_BASE_URL",""),
    api_token = os.getenv("MINERU_API_TOKEN","")
)