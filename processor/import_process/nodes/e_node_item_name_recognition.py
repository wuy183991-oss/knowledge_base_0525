import json
from pathlib import Path
import time

from langchain_openai import ChatOpenAI
from pymilvus import DataType

from config.llm_config import llm_config
from config.milvus_config import milvus_config
from utils.milvus_utils import escape_milvus_string, get_milvus_client
from utils.embedding_utils import generate_embeddings
from processor.import_process.exceptions import StateFieldError
from processor.import_process.base import BaseNode
from processor.import_process.state import ImportGraphState
from typing import Dict, List
from langchain_core.messages import SystemMessage, HumanMessage

class NodeItemNameRecognition(BaseNode):
    """
    主体识别节点：主体识别与标签提取
    """

    name = "node_item_name_recognition"

    def process(self, state: ImportGraphState):
        #1 参数处理
        file_title,chunks = self._step_1_get_inputs(state)

        #2 上下文拼接
        context = self._step_2_build_context(file_title,chunks)
        # print(context)
        #3 模型识别（识别）
        item_name = self._step_3_call_llm(file_title,context)
        print(f"item_name: {item_name}")
        #4 回填数据（item_name -> chunks）
        self._step_4_update_chunks(state,chunks,item_name)

        path = f"{Path(state.get('md_path')).parent}/{state.get('file_title')}_new_chunks.json"
        with open(path,"w",encoding="utf-8") as f:
            json.dump(
                chunks,
                f,
                ensure_ascii=False,
                indent=2
            )
        #5 主体名称向量化
        dense_vector,sparse_vector = self._step_5_generate_vectors(item_name)

        #6 存入milvus向量库
        self._step_6_save_to_milvus(state,file_title,item_name,dense_vector,sparse_vector)
        return state

    def _step_1_get_inputs(self,state):
        print("步骤1 参数处理")
        file_title = state["file_title"]
        

        if not file_title:
            raise StateFieldError(field_name = "file_title",message = "文件标题不能为空",expected_type = str)

        chunks = state["chunks"]
        if not chunks:
            raise StateFieldError(field_name = "chunks",message = "chunks不能为空",expected_type = List)

        return file_title,chunks

    def _step_2_build_context(self,file_title,chunks:List[Dict])->str:
        print("步骤2 上下文拼接")
        #限制上下文的片数
        k = self.config.item_name_chunk_k
        #上下文切片的长度   
        chunk_size = self.config.item_name_chunk_size

        parts:List[Dict] = []
        total_chars = 0

        for index,chunk in enumerate(chunks[:k],start=1):
            chunk_title = chunk.get("title","").strip()
            chunk_content = chunk.get("content","").strip()

            #格式化
            piece = f"【切片{index}】\n标题{chunk_title}\n内容{chunk_content}\n\n"
            parts.append(piece)

            #计算长度
            total_chars += len(piece)

            #长度检测
            if total_chars > chunk_size:
                break

        #截断处理
        context = "\n\n".join(parts).strip()
        final_context = context[:chunk_size]

        return final_context

    def _step_3_call_llm(self,file_title,context)->str:
        print("步骤3 模型识别")
        if not context:
            return file_title
        #llm客户端
        llm_ai = ChatOpenAI(
            model=llm_config.default_model,
            base_url=llm_config.api_base,
            api_key=llm_config.api_key,
            temperature=llm_config.default_temperature,
            extra_body={"enable_thinking":False}
        )

        #提示词
        prompt = f""""
        请从以下信息中识别出商品名称与型号：
        文件名：{file_title}

        正文切片（用于辅助识别）：
        {context}

        要求：
        1. 返回内容为字符串形式，最好是带品牌、型号和名称的完整商品名称。比如：苏伯尓5000W大功率电磁炉；
        2. 返回结果应该只包含商品名称，不要添加任何解释或其他内容；
        3. 如果无法识别商品名称,请返回空字符串。
        """

        message = [
            SystemMessage(content="你是一个专业的商品名称识别模型，请根据提供的信息，识别商品名称。名称不要超过20个字"),
            HumanMessage(content=prompt)
        ]

        #调用大模型
        response = llm_ai.invoke(message)

        #解析返回结果，数据清洗
        item_name = getattr(response,"content","").strip() #主体名称
        item_name = (item_name.replace(" ", "")
                         .replace("\n", "")
                         .replace("\t", "")
                         .replace("\r", ""))

        #兜底
        if not item_name:
            item_name = file_title


        return item_name

    def _step_4_update_chunks(self,state,chunks,item_name):
        print("步骤4 回填数据")
        state['item_name'] = item_name
        for chunk in chunks:
            chunk["item_name"] = item_name

        return state
    def _step_5_generate_vectors(self,item_name):
        print("步骤5 主体名称向量化")
        embedding = generate_embeddings([item_name]) #稠密和稀疏向量
        dense = embedding['dense'][0]
        sparse = embedding['sparse'][0]
        return dense,sparse
    def _step_6_save_to_milvus(self,state,file_title,item_name,dense_vector,sparse_vector):
        print("步骤6 存入milvus向量库")
        milvus_url = milvus_config.milvus_url #链接地址
        collection_name = milvus_config.items_collection #表名

        #校验
        if not milvus_url or not collection_name: #参数检测
            raise Exception("参数错误")

        client = get_milvus_client()

        #字段（数据结构）
        schema = client.create_schema(auto_id=True,enable_dynamic_field=True)
        schema.add_field(
            field_name="PK",
            datatype = DataType.INT64,
            is_primary= True,
            auto_id = True
        )
        schema.add_field(
            field_name="file_title",
            datatype = DataType.VARCHAR,
            max_length = 100
        )
        schema.add_field(
            field_name="item_name",
            datatype = DataType.VARCHAR,
            max_length = 100

        )
        schema.add_field(
            field_name="dense_vector",
            datatype = DataType.FLOAT_VECTOR,
            dim = 1024 #维度
        )
        schema.add_field(
            field_name="sparse_vector",
            datatype = DataType.SPARSE_FLOAT_VECTOR,
        )
        #索引
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="dense_vector",
            index_name="dense_vector_index",
            index_type="IVF_FLAT", #分组＋精确搜索
            metric_type="COSINE",  #余旋匹配
            params={"nist":128}
        )
        index_params.add_index(
            field_name="sparse_vector",
            index_name="sparse_vector_index",
            index_type="SPARSE_INVERTED_INDEX", #索引模型
            metric_type="IP",  
            params={
                #稀疏检索算法，找到最高值
                "inverted_index_algo":"DAAT_MAXSCORE",

                #L2归一化，让内积(IP)等价于余xuan相似度
                "normalize":True,

                #统计结果是否压缩
                "quantization":'none'
            }
        )      
    
        if not client.has_collection(collection_name):
            client.create_collection(                    # ✅ 再创建
                collection_name=collection_name,
                schema=schema,
                index_params=index_params,
                timeout=30
            )
        else:
            print("集合已经存在")
        time.sleep(10)
        #幂等性清理同名表数据(collection)
        collection_name = milvus_config.items_collection  #表名
        safe_item_name = escape_milvus_string(item_name)
        #构建过滤表达式，item_name等于目标值
        filter_expr = f"item_name == '{safe_item_name}'"
        #删除符合条件的数据
        client.delete(collection_name=collection_name,filter=filter_expr)



        #插入
        data = {
            "file_title":file_title,
            "item_name":item_name,
            "dense_vector":dense_vector,
            "sparse_vector":sparse_vector

        }
        client.insert(collection_name,[data])


        state['item_name'] = item_name


if __name__ == "__main__":
    node = NodeItemNameRecognition()
    path = "D:/output/hak180产品安全手册/hak180产品安全手册_new_chunks.json"
    with open(path, "r",encoding="utf-8") as f:
        chunks_json_date = f.read()
    init_state = {
        "file_title":"hak180产品安全手册",
        "chunks": json.loads(chunks_json_date),

    }
    process = node.process(init_state)