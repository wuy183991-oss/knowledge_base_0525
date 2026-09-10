import json
import logging

from pymilvus import DataType

from config.milvus_config import milvus_config
from utils.milvus_utils import escape_milvus_string, get_milvus_client
from processor.import_process.exceptions import MilvusError, StateFieldError
from processor.import_process.base import BaseNode, setup_logging
from processor.import_process.state import ImportGraphState


class NodeImportMilvus(BaseNode):
    """
    导入向量库节点：数据持久化
    """

    name = "node_import_milvus"

    def process(self, state: ImportGraphState):

        #1 数据校验
        chunks_json_data,vector_dimension = self._step_1_check_inputs(state)

        #2 客户端和集合的准备
        milvus_client = self._step_2_prepare_collection(vector_dimension)


        #3 清理可能的冗余数据(幂等性)
        self._step_3_clean_old_data(milvus_client,chunks_json_data)

        #4 数据入库，返回数据库主键
        update_chunks = self._step_4_insert_data(milvus_client,chunks_json_data)
        for chunk in update_chunks:
            print(f"chunk_id:{chunk['chunk_id']}")
        #5 更新状态
        state['chunks'] = update_chunks
        return state
    #步骤1 数据校验
    def _step_1_check_inputs(self,state):
        print("步骤1 数据校验")
        chunks=state['chunks']
        if not chunks:
            raise StateFieldError(field_name="chunks", message="chunks不能为空",expected_type=list)

        if not isinstance(chunks,list):
            raise StateFieldError(field_name="chunks", message="chunks类型错误",expected_type=list)

        #校验2 切片包含dense_vector 字段
        first_chunk = chunks[0]
        if 'dense_vector' not in first_chunk:
            raise StateFieldError(field_name="chunks", message="chunks字段缺少dense_vector字段")

        #校验3 切片包含sparse_vector 字段
        if 'sparse_vector' not in first_chunk:
            raise StateFieldError(field_name="chunks", message="chunks字段缺少sparse_vector字段")

        #提取向量维度
        vector_dimension = len(first_chunk['dense_vector'])
        return chunks,vector_dimension

    #步骤2 客户端和集合准备
    def _step_2_prepare_collection(self,vector_dimension):
        print("步骤2 客户端和集合准备")
        """
            milvus客户端+集合准备
        """
        #1、获取milvus客户端对象
        milvus_client =  get_milvus_client()
        if not milvus_client:
            self.logger.error("获取milvus客户端对象失败")
            raise MilvusError("获取milvus客户端对象失败")

        #2 集合不存在就创建
        collections_name = milvus_config.chunks_collection
        if not milvus_client.has_collection(collections_name):
            self.create_chunks_collection(collections_name,milvus_client,vector_dimension)

        milvus_client.load_collection(collections_name)
        return milvus_client

    def create_chunks_collection(self,collections_name,milvus_client,vector_dimension):
        print("步骤2 创建集合")
        """
            创建集合
        """
        #1 创建schema
        schema = milvus_client.create_schema(auto_id=True,enable_dynamic_field=True)

        #2 创建列
        schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)  # 切片内容
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=100)  # 切片标题
        schema.add_field(field_name="parent_title", datatype=DataType.VARCHAR, max_length=100)  # 父标题
        schema.add_field(field_name="part", datatype=DataType.INT8)  # 分片编号
        schema.add_field(field_name="file_title", datatype=DataType.VARCHAR, max_length=100)  # 源文件标题
        schema.add_field(field_name="item_name", datatype=DataType.VARCHAR, max_length=100)  # 商品名称（幂等性依据）
        schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)  # 稀疏向量
        schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=vector_dimension)  # 稠密向量


        #3 创建索引
        index_params = milvus_client.prepare_index_params()
        #稠密向量索引：AUTOINDEX自动选最优索引类型+余弦相似度（语义检索常用）
        index_params.add_index(
            field_name = "dense_vector",
            index_name = "dense_vector_index",
            index_type = "AUTOINDEX",
            metric_type = "COSINE"
        )

        # 稀疏向量索引：专用SPARSE_INVERTED_INDEX+内积（IP），适配稀疏向量检索
        index_params.add_index(
            field_name="sparse_vector",
            index_name="sparse_inverted_index",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="IP",
            params={"inverted_index_algo": "DAAT_MAXSCORE", "normalize": True, "quantization": "none"}
        )

        #创建集合
        milvus_client.create_collection(
            collection_name = collections_name, 
            schema = schema, 
            index_params = index_params
            )

    #步骤3 清理可能的冗余数据
    def _step_3_clean_old_data(self,client,chunks_json_data):
        print("步骤3 清理可能的冗余数据")
        """ 
            1、根据文件名删除数据
            2、根据主键删除数据
        """
        #获取查询条件
        file_title = chunks_json_data[0]['file_title']

        #执行幂等清理
        self.clear_chunks_by_file_title(client,file_title)

    def clear_chunks_by_file_title(self,client,file_title):
        print("步骤3 清理旧数据")
        try:
            file_title = escape_milvus_string(file_title)
            client.delete(
                collection_name = milvus_config.chunks_collection,
                filter = f"file_title=='{file_title}'"  #相当于mysql的where
            )
        except Exception as e:
            self.logger.error(f"Milvus数据删除失败：{str(e)}")
            raise MilvusError(f"Milvus数据删除失败：{str(e)}")
    #步骤4 数据入库，返回数据库主键
    def _step_4_insert_data(self,milvus_client,chunks_json_data):
        print("步骤4 数据入库")
        """
            批量插入milvus
        """
        #数据处理
        data_to_insert=[]
        for item in chunks_json_data:
            item_copy = item.copy()
            if "part" not in item_copy:
                item_copy['part'] = 0

            data_to_insert.append(item_copy)

        #批量插入
        insert_result = milvus_client.insert(collection_name = milvus_config.chunks_collection, data = data_to_insert)
        insert_count = insert_result.get("insert_count",0) #插入数据的条数
        print(f"插入数据条数：{insert_count}")
        # print(f"insert_result 的 keys: {insert_result.keys()}")
        #回写主题
        insert_ids = insert_result.get("ids",[])
        if insert_ids:
            for index,item in enumerate(chunks_json_data):
                item['chunk_id'] = str(insert_ids[index])

        #返回带有主键的chunks
        return chunks_json_data

if __name__ == '__main__':
    setup_logging()
    json_path = r"D:/output/hak180产品安全手册/hak180产品安全手册_new_new_new_chunks.json"
    with open(json_path, "r", encoding="utf-8") as f:
        state_json = f.read()

    state = json.loads(state_json)

    init_state = {
        "chunks": state
    }

    node = NodeImportMilvus()
    result = node(init_state)

    logging.getLogger().info(json.dumps(result, ensure_ascii=False,indent=4))