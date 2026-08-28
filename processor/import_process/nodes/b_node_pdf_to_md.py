import json
import logging
from pathlib import Path
from platform import node

from processor.import_process.exceptions import FileProcessingError, StateFieldError
from processor.import_process.base import BaseNode, setup_logging
from processor.import_process.state import ImportGraphState


class NodePDFToMD(BaseNode):
    """
    PDF 转 Markdown 节点：PDF结构化解析
    """

    name = "node_pdf_to_md"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name} 节点开始执行")

        #1、检查和获取相关参数
        pdf_path_obj,output_dir_obj = self._step_1_validate_paths(state)


        #2、获取上传连接并上传到mineru服务器
        zip_url = self._step_2_upload_and_poll(pdf_path_obj)

        #3、下载zip压缩文件并解压 并改名
        md_path = self._step_3_download_and_extract(zip_url,output_dir_obj,pdf_path_obj.stem)

        #4、读取文件 md_content
        with open(md_path,"r",encoding="utf-8") as md_file:
            md_content = md_file.read()
        #5、设置state结果
        state["md_content"] = md_content
        state["md_path"] = md_path
        return state

    def _step_1_validate_paths(self, state: ImportGraphState):

        #1、校验路径
        pdf_path_obj = state.get("pdf_path")
        if not pdf_path_obj:
            raise StateFieldError(field_name="pdf_path",expected_type=str)
        file_dir = state.get("file_dir")  
        if not file_dir:
            raise StateFieldError(field_name="file_dir",expected_type=str)

        #2 path封装路径
        pdf_path_obj = Path(pdf_path_obj)
        output_dir_obj = Path(file_dir)

        #3 文档是否存在
        if not pdf_path_obj.exists():
            raise FileProcessingError(message=f"输入的文件不存在:{pdf_path_obj}")
        if not output_dir_obj.exists():
            raise FileProcessingError(message=f"输出的文件不存在:{output_dir_obj}")

        return pdf_path_obj,output_dir_obj

    def _step_2_upload_and_poll(self,pdf_path_obj:Path):
        logging.info("_step_2_upload_and_poll 上传文件到mineru服务器...")

        return "下载的url"

    def _step_3_download_and_extract(self,zip_url:str,output_dir_obj:Path,pdf_stem:str):
        logging.info("_step_3_download_and_extract 下载zip文件并解压改名...")

        return "md_path"


if __name__ == "__main__":

    setup_logging()

    init_state = {
        "pdf_path":"D:/掌柜智库课件0525/2.资料/04-设备手册汇总/doc/hak180产品安全手册.pdf",
        "file_dir": "D:/output"
    }
    node = NodePDFToMD()
    result =  node.process(init_state)

    #打印结果
    dumps = json.dump(result,ensure_ascii=False,indent=4)

    print(dumps)