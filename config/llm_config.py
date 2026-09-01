
from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv(override=True)

@dataclass #自动get set方法
class LLMConfig:
    api_key:str
    api_base:str
    default_model:str
    vl_model:str
    item_model:str
    default_temperature:float

llm_config = LLMConfig(
    api_key = os.getenv("OPENAI_API_KEY",""),
    api_base = os.getenv("OPENAI_API_BASE",""),
    default_model = os.getenv("LLM_DEFAULT_MODEL",""),
    vl_model = os.getenv("VL_MODEL",""),
    item_model = os.getenv("ITEM_MODEL",""),
    default_temperature = float(os.getenv("LLM_DEFAULT_TEMPERATURE"))
)