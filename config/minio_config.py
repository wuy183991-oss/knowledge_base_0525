
from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()

@dataclass #自动get set方法
class MinioConfig:
    endpoint:str
    access_key:str
    secret_key:str
    bucket_name:str
    img_dir:str

minio_config = MinioConfig(
    endpoint = os.getenv("MINIO_ENDPOINT",""),
    access_key = os.getenv("MINIO_ACCESS_KEY",""),
    secret_key = os.getenv("MINIO_SECRET_KEY",""),
    bucket_name = os.getenv("MINIO_BUCKET_NAME",""),
    img_dir = os.getenv("MINIO_IMG_DIR","")
)