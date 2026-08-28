import os
import sys
# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

from config.mineru_config import mineru_config

load_dotenv()

url = mineru_config.base_url
token = mineru_config.api_token

print(url)
print(token)