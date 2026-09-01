import base64
from collections import deque
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Deque, Dict, List, Tuple

from minio import Minio

from config.llm_config import llm_config
from config.minio_config import minio_config
from utils.minio_utils import get_minio_client
from utils.llm_utils import get_llm_client
from processor.import_process.exceptions import FileProcessingError, StateFieldError
from processor.import_process.base import BaseNode, setup_logging
from processor.import_process.state import ImportGraphState
from minio.deleteobjects import DeleteObject


class NodeMDImg(BaseNode):
    """
    MarkDown图片处理节点：多模态图片理解
    """

    name = "node_md_img"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行")

        #1、参数处理
        md_content,md_path_obj,images_dir = self._step_1_get_content(state)
        print(f"md_content:{md_content},md_path_obj:{md_path_obj},images_dir:{images_dir}")

        #2 图片扫描
        target_images = self._step_2_scan_images(md_content,images_dir)
        print(f"target_images:{target_images}")

        #3 视觉模型摘要
        summaries = self._step3_generate_summaries(md_path_obj.stem,target_images)

        #4 上传minio 替换md
        new_md_content = self._step4_upload_and_replace(md_path_obj,target_images,summaries,md_content)

        #5 保存备份md
        new_md_file_name = self._step5_backup_new_md_file(state['md_path'],new_md_content)

        state['md_content'] = new_md_content
        state['md_path'] = new_md_file_name
        
        return state

    def _step_1_get_content(self,state):

        #1 校验参数
        md_path = state.get('md_path')
        if not md_path:
            raise StateFieldError(field_name="md_path",expected_type=str)
        md_path_obj = Path(md_path)

        if not md_path_obj.exists():
            raise FileProcessingError(message=f"输入文件不存在:{md_path}")

        md_content = state['md_content']

        #测试
        if not md_content:
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()

        #图片路径 和md文档所在目录同级的images图片路径
        images_dir = md_path_obj.parent / "images"

        return md_content,md_path_obj,images_dir


    def _step_2_scan_images(self,md_content,images_dir):

        #1 返回结果
        target_images = []

        #2 扫描图片
        for image_file in os.listdir(images_dir):
            file_ext = os.path.splitext(image_file)[1].lower()
            if file_ext not in self.config.image_extensions:
                self.logger.warning(f"图片格式不支持，跳过:{image_file}")
                continue
            img_path = images_dir / image_file #图片路径

            #找到md中图片的位置和上下文
            context = self._find_image_in_md(md_content,image_file)

            #过滤MD中未引用的图片
            if not context:
                self.logger.warning(f"图片未在MD中引用，跳过处理:{image_file}")
                continue
                    
            target_images.append((image_file,img_path,context))


        return target_images

    def _find_image_in_md(self,md_content:str,image_file:str,context_len:int=100)->Tuple[str,str]:
        """
        在md文档中查找图片的位置和上下文
        """
        # 1、定义正则表达式
        # ![描述](images/文件名.扩展名)
        # r"字符串"：不要将其中的特殊符号进行转义
        # re.escape 转义图片文件名中的特殊字符，避免正则语法错误
        # .* 贪婪匹配 .*? 非贪婪匹配
        pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_file) + r".*?\)")
        match = pattern.search(md_content)
        if not match:
            return None

        start,end = match.span()

        pre_text = md_content[max(0,start-context_len):start] #文件上文
        post_text = md_content[end:min(len(md_content),end+context_len)] #文件下文


        return pre_text,post_text

    def _step3_generate_summaries(self,doc_stem:str,target_images:List[Tuple[str,str,Tuple[str,str]]]) -> Dict[str,str]:
        """
        生成图片摘要
        """
        #1、定义结果
        summaries = {}

        request_deque = deque()

        for image_file,img_path,context in target_images:
            self._apply_api_rate_limit(request_deque,max_requests=10)
            #调用视觉模型
            summaries[image_file] = self._summarize_image(img_path,root_stem=doc_stem,image_context=context) #图片摘要


        self._apply_api_rate_limit(request_deque,max_requests=10)

        return summaries

    def _apply_api_rate_limit(
            self,
            request_times: Deque[float],
            max_requests: int,
            window_seconds: int = 60
    ) -> None:
        """
        通用滑动窗口API速率限制器（抽离为公共工具）
        核心逻辑：维护请求时间戳双端队列，窗口内请求数超上限则自动等待，防止触发第三方API限流
        :param request_times: 存储请求时间戳的双端队列，需外部初始化（全局/单例），跨调用复用
        :param max_requests: 速率限制窗口内的最大允许请求次数
        :param window_seconds: 速率限制滑动窗口时长，默认60秒（1分钟）
        :return: None，超出限制时会阻塞等待
        """
        current_time = time.time()

        # 1. 清理滑动窗口外的过期请求时间戳，保证队列仅存窗口内的请求
        while request_times and current_time - request_times[0] >= window_seconds:
            request_times.popleft()

        # 2. 窗口内请求数达上限，计算并阻塞等待剩余时间
        if len(request_times) >= max_requests:
            # 计算需要等待的时长（窗口总时长 - 最早请求已存在的时长）
            sleep_duration = window_seconds - (current_time - request_times[0])
            if sleep_duration > 0:
                logging.getLogger().info(
                    f"触发API速率限制，窗口{window_seconds}秒内最多{max_requests}次，需等待：{sleep_duration:.2f} 秒")
                time.sleep(sleep_duration)
                # 等待后更新当前时间，重新清理过期请求（避免等待期间有请求过期）
                current_time = time.time()
                while request_times and current_time - request_times[0] >= window_seconds:
                    request_times.popleft()

        # 3. 记录当前请求时间戳，加入滑动窗口队列
        request_times.append(current_time)
        logging.getLogger().info(f"API请求时间戳已记录，当前{window_seconds}秒窗口内请求数：{len(request_times)}")

    def _summarize_image(self,img_path:str,root_stem:str,image_context:Tuple[str,str]) -> str:
        """
        生成图片摘要
        """
        #0 图片的base64编码
        with open(img_path,"rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode("utf-8")

        #1 llm模型工具
        vl_ai = get_llm_client(llm_config.vl_model)

        #2 调用模型
        message=[
            {
                "role":"user",
                "content":[
                    {
                            "type": "text",
                            "text": f"""这是"{root_stem}"文件中的一张图片，图片上文部分为"{image_context[0]}"，下文部分为"{image_context[1]}"，请用中文简要总结这张图片的内容，用于 Markdown 图片标题。"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                ]
            }
        ]
        response = vl_ai.invoke(message)
        #3 处理返回结果
        return response.content.strip().replace("\n","")

    def _step4_upload_and_replace(self,doc_stem:str,target_images:List[Tuple[str,str,Tuple[str,str]]],summaries:Dict[str,str],md_content:str):
        #0 minio客户端
        minio_client = get_minio_client()
        minio_img_dir = minio_config.img_dir
        upload_dir = f"{minio_img_dir}/B530"
        print(f"将图片存入{upload_dir}目录下")

        #1 清理minio目录 避免目录冲突
        self._clean_minio_dir(minio_client,upload_dir)

        #2 批量上传图片，获得minio的urls
        urls = self.upload_images_batch(minio_client,upload_dir,target_images)

        #3 将摘要和urls路径合并
        image_info = self.merge_summaries_and_urls(summaries,urls)

        #4 替换md文件的摘要和路径
        md_content = self.replace_md_file(md_content,image_info)
    
        return md_content
    #步骤4 方法1 清理目录
    def _clean_minio_dir(self,minio_client:Minio,prefix:str):
        try:
            objects_to_delete = minio_client.list_objects(minio_config.bucket_name, prefix=prefix, recursive=True)
            # 构造删除列表
            delete_list = [DeleteObject(obj.object_name) for obj in objects_to_delete]
            if delete_list:
                errors = minio_client.remove_objects(minio_config.bucket_name, delete_list)
                for error in errors:
                    self.logger.error(f"删除失败：{error}")
        except Exception as e:
                self.logger.error(f"清理minio目录失败：{e}")

    #步骤4 方法2 批量上传图片
    def upload_images_batch(self,minio_client:Minio,upload_dir:str,target_images:List[Tuple[str,str,Tuple[str,str]]]) -> List[str]:
        """
        批量上传图片
        """
        urls = {}
        for img_file,img_path,_ in target_images:
            # 上传图片
            filename = os.path.basename(img_file)
            object_name = f"{upload_dir}/{filename}" #minio文件对象名(路径：带后缀名)
            print(f"上传图片：{object_name}")
            urls[img_file] = self.upload_to_minio(minio_client,img_path,object_name) #返回minio的url

        return urls

    #步骤4 方法3 合并参数
    def merge_summaries_and_urls(self,summaries:Dict[str,str],urls:List[str]):
        image_info = {}

        for image_file,summary in summaries.items():
            image_info[image_file] = (summary,urls[image_file])

        return image_info
    #步骤4 方法4 替换md文件
    def replace_md_file(self,md_content:str,image_info:Dict[str,str]) -> str:
        """
        替换md文件
        """
        for image_file,(summary,url) in image_info.items():
            pattern = re.compile(r"!\[.*?\]\(.*?"+re.escape(image_file)+r".*?\)")
            md_content = pattern.sub(lambda m:f"![{summary}]({url})",md_content)

        return md_content

    #步骤4 方法5 上传图片
    def upload_to_minio(self,minio_client:Minio,img_path:str,object_name:str)-> str:

        #上传minio
        ifSuccess = minio_client.fput_object(
            bucket_name=minio_config.bucket_name,
            object_name=object_name,
            file_path=img_path,
            content_type=f"image/{os.path.splitext(img_path)[1][1:]}",
            )
        print(f"上传图片成功：{ifSuccess}")
        url = f"http://{minio_config.endpoint}/{minio_config.bucket_name}/{object_name}" # http://192.168.1.245:9000/桶名/项目名/文件名/107.png
        print(f"图片url：{url}")

        return url

    #步骤5保存和备份新文档
    def _step5_backup_new_md_file(self, origin_md_path: str, md_content: str) -> str:
        """
        步骤5：将处理后的MD内容保存为新文件（原文件不变，避免数据丢失）
        新文件命名规则：原文件名 + _new.md（如test.md → test_new.md）
        :param origin_md_path: 原始MD文件完整路径
        :param md_content: 处理后的新MD内容
        :return: 新MD文件的完整路径
        """
        # 构造新文件路径：替换原后缀为 _new.md
        new_md_file_name = os.path.splitext(origin_md_path)[0] + "_new.md"

        # 写入新MD内容（覆盖写入，若文件已存在则更新）
        with open(new_md_file_name, "w", encoding="utf-8") as f:
            f.write(md_content)

        self.logger.info(f"处理后MD文件已保存，新文件路径：{new_md_file_name}")

        return new_md_file_name

if __name__ == "__main__":

    setup_logging()

    init_state = {
        "md_path":"D:/output/hak180产品安全手册/hak180产品安全手册.md",
        "md_content":None
    }
    node = NodeMDImg()
    result =  node(init_state)

    #打印结果
    dumps = json.dumps(result,ensure_ascii=False,indent=4)

    print(dumps)