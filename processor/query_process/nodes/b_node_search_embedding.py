import json

from config.milvus_config import milvus_config
from utils.milvus_utils import create_hybrid_search_requests, get_milvus_client, hybrid_search
from utils.embedding_utils import generate_embeddings
from processor.query_process.base import NodeBase
from processor.query_process.state import QueryGraphState
from tool.logger import logger


class NodeSearchEmbedding(NodeBase):
     """
    节点功能：基于已确认主体名+改写后的用户问题，执行Milvus向量数据库混合检索
    """

     # 覆盖基类的 name 属性，标识节点名称
     name: str = "node_search_embedding"

     def process(self, state: QueryGraphState) -> QueryGraphState:
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """

        # TODO

        #1 参数处理
        logger.info(f"【{self.name}】节点逻辑")
        item_names = state.get("item_names") #元数据过滤条件
        query = state.get("rewritten_query") #语义搜索条件

        query_embeddings = generate_embeddings([query]) #参数向量化
        dense_vector = query_embeddings["dense"][0]
        sparse_vector = query_embeddings["sparse"][0]

        #2 milvus客户端
        milvus_client = get_milvus_client()
        chunks_collection = milvus_config.chunks_collection #表(集合)

        #3 请求对象
        request = create_hybrid_search_requests(
            dense_vector=dense_vector,
            sparse_vector=sparse_vector,
            expr=f"item_name in {item_names}"
        )

        #4 发送请求
        response = hybrid_search(
            client=milvus_client,
            collection_name=chunks_collection,
            reqs=request,
            ranker_weights=(0.8,0.2),
            output_fields=["chunk_id","content","item_name"],
        )
        print(response[0])
        # return state
        return {"embedding_chunks": response[0] if response else []}

if __name__ == '__main__':
    node_search_embedding = NodeSearchEmbedding()
    init_state = {
        "item_names": ["兄弟HAK180烫金机"],
        "rewritten_query":"兄弟帮我查一下HAK180烫金机是什么"
    }
    process = node_search_embedding.process(init_state)
    print(json.dumps(process,ensure_ascii=False,indent=4))