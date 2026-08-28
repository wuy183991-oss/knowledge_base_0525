import json
import logging 

from langgraph.constants import END
from langgraph.graph import StateGraph


from processor.import_process.base import setup_logging
from processor.import_process.nodes.b_node_pdf_to_md import NodePDFToMD
from processor.import_process.nodes.c_node_md_img import NodeMDImg
from processor.import_process.nodes.d_node_document_split import NodeDocumentSplit
from processor.import_process.nodes.e_node_item_name_recognition import NodeItemNameRecognition
from processor.import_process.nodes.f_node_bge_embedding import NodeBGEEmbedding
from processor.import_process.nodes.g_node_import_milvus import NodeImportMilvus
from processor.import_process.nodes.a_node_entry import NodeEntry
from processor.import_process.state import ImportGraphState


class KBImportWorkflow:

    def __init__(self,config=None):
        self._compiled_graph = None 

    @property
    def graph(self):
        """
              返回图实例
        """
        logging.info("获取图实例")
        if self._compiled_graph is None:
            self._compiled_graph = self.build_graph() #创建图

        return self._compiled_graph

    @staticmethod
    def route_after_entry(state:ImportGraphState):
        if state.get("is_pdf_read_enabled"):
            return "b_node_pdf_to_md"
        elif state.get("is_md_read_enabled"):
            return "c_node_md_img"
        else:
            logging.info("route_after_entry路由器，未指定导入文件类型")
            return END

    def build_graph(self):
        """
            创建主图
        """

        graph = StateGraph(ImportGraphState)

        #1、注册节点
        graph.add_node("a_node_entry",NodeEntry())
        graph.add_node("b_node_pdf_to_md",NodePDFToMD())
        graph.add_node("c_node_md_img",NodeMDImg())
        graph.add_node("d_node_document_split",NodeDocumentSplit())
        graph.add_node("e_node_item_name_recognition",NodeItemNameRecognition())
        graph.add_node("f_node_bge_embedding",NodeBGEEmbedding())
        graph.add_node("g_node_import_milvus",NodeImportMilvus())

        graph.set_entry_point("a_node_entry")
        #2、定义节点边
        graph.add_conditional_edges(
            "a_node_entry",
            self.route_after_entry,
            {
                "c_node_md_img": "c_node_md_img",
                "b_node_pdf_to_md":"b_node_pdf_to_md",
                END: END
            }
        )

        graph.add_edge("b_node_pdf_to_md", "c_node_md_img")
        graph.add_edge("c_node_md_img", "d_node_document_split")
        graph.add_edge("d_node_document_split", "e_node_item_name_recognition")
        graph.add_edge("e_node_item_name_recognition", "f_node_bge_embedding")
        graph.add_edge("f_node_bge_embedding", "g_node_import_milvus")


        #3、编译图

        return graph.compile()

    def run(self,state:ImportGraphState,stream:bool=False):
        if stream:
            return self.graph.stream(state,stream_mode="values")
        else:
            return self.graph.invoke(state)

if __name__ == "__main__":
    #启用日志
    setup_logging()

    workflow = KBImportWorkflow()
    # graph = workflow.graph
    init_state = {"import_file_path":r"D:/掌柜智库课件0525/2.资料/04-设备手册汇总/doc/H3C LA2608室内无线网关 用户手册-6W100-整本手册.pdf"}
    # for event in workflow.run(init_state,stream=True):
    #     print(event)


    #非流式输出
    final_state = workflow.run(init_state,stream=False)
    print(json.dumps(final_state,ensure_ascii=False,indent=4))
    