import logging
from pathlib import Path

from processor.import_process.exceptions import FileProcessingError, StateFieldError
from processor.import_process.base import BaseNode
from processor.import_process.state import ImportGraphState


class NodeEntry(BaseNode):
    """
    入口节点：任务分发
    """

    name = "node_entry"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行...")

        #1 获得输入路径
        input_file_path = state.get("import_file_path")

        #2 校验路径
        if not input_file_path:
            raise StateFieldError(field_name="import_file_path", expected_type=str)

        #3,4校验文件
        import_file_path_obj = Path(input_file_path)
        if not import_file_path_obj.exists():
            raise FileProcessingError(message=f"文件不存在:{input_file_path}")

        #5 md 还是pdf
        if import_file_path_obj.suffix == ".md":
            state['is_md_read_enabled'] = True
            state['md_path'] = input_file_path
        elif import_file_path_obj.suffix == ".pdf":
            state['is_pdf_read_enabled'] = True
            state['pdf_path'] = input_file_path
        else:
            raise FileProcessingError(message=f"不支持的文件格式:{input_file_path}")

        state['file_title'] = import_file_path_obj.stem
        state['file_dir'] = r"D:/output"
        
        return state