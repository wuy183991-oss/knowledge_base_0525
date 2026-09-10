
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from processor.query_process.state import QueryGraphState
from processor.query_process.nodes.b_node_search_embedding import NodeSearchEmbedding
from processor.query_process.nodes.c_node_search_embedding_hyde import NodeSearchEmbeddingHyde
from processor.query_process.nodes.d_node_web_search_mcp import NodeWebSearchMcp
from processor.query_process.nodes.e_node_rrf import NodeRrf
from processor.query_process.nodes.f_node_rerank import NodeRerank
from processor.query_process.nodes.g_node_answer_output import NodeAnswerOutput
from processor.query_process.nodes.a_node_item_name_confirm import NodeItemNameConfirm


load_dotenv()

class KBQueryWorkflow:
    def __init__(self):
        print("初始化工作流")
        #1 工作流状态
        self.workflow = StateGraph(QueryGraphState)

        #2 实例化所有节点
        self._init_nodes()

        #3 注册所有节点（添加节点）
        self._register_nodes()

        #4 设置路由规则（设置边）
        self._setup_routes()

        #5 编译工作流(懒加载，首次执行时编译)
        self._compiled_app = None

    #实例化结点
    def _init_nodes(self):
        print("实例化所有节点")
        self.node_item_name_confirm = NodeItemNameConfirm()
        self.node_search_embedding = NodeSearchEmbedding()
        self.node_search_embedding_hyde = NodeSearchEmbeddingHyde()
        self.node_web_search_mcp = NodeWebSearchMcp()
        self.node_rrf = NodeRrf()
        self.node_rerank = NodeRerank()
        self.node_answer_output = NodeAnswerOutput()

    #注册
    def _register_nodes(self):
        print("注册所有节点")
        self.workflow.add_node("node_item_name_confirm",self.node_item_name_confirm)
        self.workflow.add_node("node_search_embedding",self.node_search_embedding)
        self.workflow.add_node("node_search_embedding_hyde",self.node_search_embedding_hyde)
        self.workflow.add_node("node_web_search_mcp",self.node_web_search_mcp)
        self.workflow.add_node("node_rrf",self.node_rrf)
        self.workflow.add_node("node_rerank",self.node_rerank)
        self.workflow.add_node("node_answer_output",self.node_answer_output)

    #路由
    def _setup_routes(self):
        print("设置路由规则")
        #入口
        self.workflow.add_edge(START,"node_item_name_confirm")

        #条件路由
        self.workflow.add_conditional_edges(
            "node_item_name_confirm",
            self._route_after_item_name_confirs,
            {
                "node_search_embedding": "node_search_embedding",
                "node_search_embedding_hyde": "node_search_embedding_hyde",
                "node_web_search_mcp": "node_web_search_mcp",
                "node_item_name_confirm": "node_item_name_confirm" #问题确认后，不进入任何检索分支，直接返回结果
            }
        )

        #注册边
        self.workflow.add_edge("node_search_embedding", "node_rrf")
        self.workflow.add_edge("node_search_embedding_hyde", "node_rrf")
        self.workflow.add_edge("node_web_search_mcp", "node_rrf")

        self.workflow.add_edge("node_rrf", "node_rerank")
        self.workflow.add_edge("node_rerank", "node_answer_output")
        self.workflow.add_edge("node_answer_output",END)

    #条件路由
    def _route_after_item_name_confirs(self,state:QueryGraphState)->str:
        print("条件路由")
        if state.get("answer"):
            return "node_answer_output"

        return "node_search_embedding"
        

    #编译图
    def compile(self):
        print("编译图")
        if not self._compiled_app:
            self._compiled_app = self.workflow.compile()
        return self._compiled_app

    #调用
    def run(self, initial_state: QueryGraphState, stream: bool = False) -> QueryGraphState:
        print("调用图")
        """
        统一执行入口，支持切换invoke/stream
        """
        if not self._compiled_app:
            self.compile()
        if stream:
            return self._compiled_app.stream(initial_state)
        else:
            return self._compiled_app.invoke(initial_state)

if __name__ == "__main__":
    workflow = KBQueryWorkflow()
    response = workflow.run({"original_query":"B530这玩意儿咋鼓捣上？","session_id":"123"},stream=True)
    #print(response)
    for res in response:
        print(res)

    #画图
    # print(workflow.compile().get_graph().draw_ascii())
