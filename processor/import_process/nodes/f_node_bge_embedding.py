import json
from pathlib import Path
from typing import Dict, List

from utils.embedding_utils import generate_embeddings
from processor.import_process.exceptions import StateFieldError
from processor.import_process.base import BaseNode
from processor.import_process.state import ImportGraphState

class NodeBGEEmbedding(BaseNode):
    """
    混合向量化节点：使用 BGE-M3 模型将文本转换为向量
    """

    name = "node_bge_embedding"

    def process(self, state: ImportGraphState):

        #1 参数校验
        chunks = self._step_1_validate_paths(state)
        #2 数据向量化
        output_data = self._step_2_generate_embeddings(chunks)
        # for item in output_data:
        #     item_name = item.get("item_name")
        #     content = item.get("content")
        #     print(f"{item_name}")
        #     sparse_vector = item.get("sparse_vector")
        #     print(sparse_vector)

        path = f"{Path(state.get('md_path')).parent}/{state.get('file_title')}_new_chunks.json"
        with open(path,"w",encoding="utf-8") as f:
            json.dump(
                output_data,
                f,
                ensure_ascii=False,
                indent=4
            )
        #3 更新并返回结果
        state["chunks"] = output_data

        return state

    def _step_1_validate_paths(self,state:ImportGraphState)->List[Dict]:
        print("步骤1 参数校验")
        #校验结果
        chunks = state.get("chunks")
        if not chunks:
            raise ValueError("参数错误：chunks为空")

        if not isinstance(chunks,list): #chunks必须为列表
            raise StateFieldError(field_name="chunks",message="chunks数据类型不正确",expected_type=list)
        return chunks


    def _step_2_generate_embeddings(self,chunks:List[Dict[str,str]])->List[Dict[str,str]]:
        """
            将item_name 和content转化为向量数据（稀疏和稠密）
        """

        print("步骤2 数据向量化")
        #生成向量
        output_data = []

        batch_size = 5 #批量处理
        for i in range(0,len(chunks),batch_size):
            five_ready_xlh_text = []
            five_texts = chunks[i:i+batch_size] #第一次从0块取到第四块，一共取五块
            for doc in five_texts:
                item_name = doc.get("item_name")
                content = doc.get("content")
                five_ready_xlh_text.append(f"{item_name}\n{content}" if item_name else content)

            embeddings = generate_embeddings(five_ready_xlh_text) #向量化结果
            for j,doc in enumerate(five_texts):
                item = doc.copy()
                dense  =embeddings["dense"][j]
                item["dense_vector"] = dense
                sparse = embeddings["sparse"][j]
                item["sparse_vector"] = sparse
                output_data.append(item)
        return output_data


if __name__ == "__main__":
    node = NodeBGEEmbedding()
    path = "D:/output/hak180产品安全手册/hak180产品安全手册_new_new_chunks.json"
    with open(path, "r",encoding="utf-8") as f:
        chunks_content = f.read()

    json_state = json.loads(chunks_content)
    init_state = {
        "chunks":json_state
    }
    response = node(init_state)
    dumps = json.dumps(response,ensure_ascii=False,indent=4)
    print(dumps)