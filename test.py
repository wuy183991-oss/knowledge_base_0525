import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 40)
print("环境配置验证")
print("=" * 40)
print(f"MINIO_ENDPOINT: {os.getenv('MINIO_ENDPOINT')}")
print(f"MILVUS_URL: {os.getenv('MILVUS_URL')}")
print(f"MONGO_URL: {os.getenv('MONGO_URL')}")
print(f"LLM_DEFAULT_MODEL: {os.getenv('LLM_DEFAULT_MODEL')}")
print("✅ 环境配置加载成功！")