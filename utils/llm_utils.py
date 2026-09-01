

from config.llm_config import llm_config
from langchain_openai import ChatOpenAI


_llm_client_cache = {}

def get_llm_client(model:str|None=None,json_model:bool=False):
    m = model or llm_config.default_model

    key = (m,json_model)

    if key in _llm_client_cache:
        return _llm_client_cache[key]

    model_kwargs = {}
    if json_model:
        model_kwargs["response_format"] = {"type":"json_object"}


    #返回模型
    client =  ChatOpenAI(
        model=m,
        temperature=llm_config.default_temperature,
        base_url=llm_config.api_base,
        api_key=llm_config.api_key
    )

    _llm_client_cache[key] = client

    return client

if __name__ == '__main__':
    client = get_llm_client()
    invoke = client.invoke("你是谁？")
    print(invoke.content)