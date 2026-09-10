import json
from pathlib import Path
import re
from typing import Dict, List

from processor.import_process.import_config import get_config
from processor.import_process.exceptions import StateFieldError
from processor.import_process.base import BaseNode
from processor.import_process.state import ImportGraphState
from langchain_text_splitters import RecursiveCharacterTextSplitter

class NodeDocumentSplit(BaseNode):
    """
    文档切分节点：智能文档切片
    """

    name = "node_document_split"

    def process(self, state: ImportGraphState):

        #1 参数处理
        content,file_title = self._step_1_get_inputs(state)

        #2 标题切（初切）
        sections,title_count,lines_count = self._step_2_split_by_title(content,file_title)
        # for sections in sections:
        #     print(f"s{sections['title']}")
        #     print(f"s{sections['content']}")
        #     print("===========================================================================================")
        # print(f"标题数量:{title_count}")
        # print(f"行数:{lines_count}")

        #3 无标题兜底(默认标题)
        sections = self._step_3_handle_no_title(content,sections,title_count,file_title)

        #4 块的精细化处理(长切短合)
        sections = self._step_4_refine_chunks(sections)
        
        #5 打印日志
        self._step_5_print_stats(lines_count,sections)

        #6 备份 
        self._step_6_backup(state,sections)

        state["chunks"] = sections
        return state

    #步骤1 参数处理
    def _step_1_get_inputs(self,state):
        print("步骤1 参数处理")
        content = state.get("md_content")
        if not content:
            raise StateFieldError(field_name="file_title",message="文件标题不能为空",expected_type=str)
        
        file_title = state.get("file_title")
        if not file_title:
            raise StateFieldError(field_name="file_title",message="文件标题不能为空",expected_type=str)

        #换行符处理
        content = content.replace("\r\n","\n").replace("\r","\n")
        return content,file_title
    #步骤2 标题切
    def _step_2_split_by_title(self,content,file_title):
        print("步骤2 标题切")

        #参数声明
        sections:List[Dict[str,str]] = []
        title_count = 0
        lines = content.split("\n")
        in_code_block = False  #判断是否在代码块里面
        current_lines = []
        current_title = ""

        #切换逻辑（标题切）
        title_pattern = r'\s*#{1,6}\s+.+' #匹配标题

        #独立封装刷新块的逻辑函数
        def _flush_section():
            if not current_lines:
                return

            sections.append(
                {
                    "title":current_title,
                    "content":"\n".join(current_lines),
                    "parent_title":"",
                    "file_title":file_title
                }
            )

        for line in lines:
            striped_line = line.strip()

            #判断是否在代码块中
            if striped_line.startswith("```") or striped_line.startswith("~~~"):
                in_code_block = not in_code_block
                current_lines.append(line)
                continue

            if(not in_code_block) and (re.match(title_pattern,line)):
                #标题处理 将之前存好的块中内容封装成sections块
                _flush_section()
                current_title = striped_line #换标题
                current_lines = [current_title]
                title_count += 1

                
            else:
                current_lines.append(line) #普通行或代码块
            current_lines.append(line)

        _flush_section()
        return sections,title_count,len(lines)

    #步骤3 无标题兜底
    def _step_3_handle_no_title(self,content,sections,title_count,file_title):
        print("步骤3 无标题兜底")
        if title_count == 0:
            return [{"title":"无标题","content":content,"file_title":file_title}]

        return sections

    #步骤4 块精细化处理(长切短合)
    def _step_4_refine_chunks(self,sections):
        print("步骤4 块精细化处理(长切短合)")

        #长切列表
        refined_split = []
        for sec in sections:
            refined_split.extend(self.split_long_section(sec))  #长切操作

        #短合列表
        final_sections = self.merge_short_sections(refined_split) #短合操作


        return sections


    #步骤四 方法1 长切
    def split_long_section(self,section:Dict[str,str]):
        content = section.get("content","")
        content_len = len(content)
        #长度合标 直接返回
        if content_len <= get_config().max_content_length:
            return [section]

        title = section.get("title") #没有换行的title
        prefix = f"{title}\n\n" if title else ""
 
        available_len = get_config().max_content_length - len(prefix) #切分标准

        #去重标题
        body = content
        if title and content.lstrip().startswith(title):
            body = body[len(title) + len(title):].lstrip()

        #切分
        splitter = RecursiveCharacterTextSplitter(
            chunk_size = available_len,
            chunk_overlap = 0,
            separators=["\n\n","\n","。","!","?",":",".","！","？",";"," "]
        )

        #切分结果
        sub_sections = []

        for index,chunk in enumerate(splitter.split_text(body),start=1):
            text = chunk.strip()
            if not text:
                continue
            full_text = (prefix + text).strip()

            sub_sections.append(
                {
                    "title":f"{title}-{index}" if title else f"chunk - {index}",
                    "content":full_text,
                    "parent_title":title,
                    "part":index,
                    "file_title":section.get("file_title")
                }
            )
        return sub_sections

    def merge_short_sections(self,sections):
        print("短合")
        """
        【辅助函数】过短章节合并（减少碎片化，提升检索效果）
        核心规则：仅合并「同父标题」且「当前块长度不足阈值」的相邻Chunk，避免跨章节合并
        :param sections: 待合并的Chunk列表（通常是_split_long_section切分后的结果）
        :return: 合并后的Chunk列表，长度适中，保留元信息
        """
        # 边界处理：空列表直接返回，避免后续索引报错
        if not sections:
            self.logger.debug("待合并Chunk列表为空，直接返回")
            return []

        merged_sections = []  # 最终合并结果
        current_chunk = None  # 迭代累加器：保存当前待合并的Chunk

        for sec in sections:
            # 初始化：第一个Chunk直接作为当前待合并块
            if current_chunk is None:
                current_chunk = sec
                continue

            # 合并条件：1.当前块长度不足阈值 2.与下一块同父标题（同属一个原章节）
            is_current_short = len(current_chunk["content"]) < self.config.min_content_length
            is_same_parent = current_chunk.get("parent_title") == sec.get("parent_title")

            if is_current_short and is_same_parent:
                # 合并前清理：去掉下一块开头重复的父标题，避免内容冗余
                parent_title = sec.get("parent_title", "")
                next_content = sec["content"]
                if parent_title and next_content.startswith(parent_title):
                    next_content = next_content[len(parent_title):].lstrip()
                # 合并内容：空行分隔，保证格式整洁
                current_chunk["content"] += "\n\n" + next_content
                # 更新子Chunk序号：保留最新序号，便于溯源
                if "part" in sec:
                    current_chunk["part"] = sec["part"]
                self.logger.debug(f"合并短Chunk：{current_chunk.get('parent_title')} → 累计长度{len(current_chunk['content'])}")
            else:
                # 不满足合并条件：将当前块加入结果，切换为新的待合并块
                merged_sections.append(current_chunk)
                current_chunk = sec

        # 循环结束后，将最后一个待合并块加入结果
        if current_chunk is not None:
            merged_sections.append(current_chunk)

        self.logger.debug(f"短Chunk合并完成：原{len(sections)}个 → 合并后{len(merged_sections)}个")
        return merged_sections
    #打印结果
    def _step_5_print_stats(self,lines_count,sections):
        print("步骤5 打印结果")
        """
        【步骤5】输出文档切分统计信息（日志记录，便于监控/调试）
        :param lines_count: MD原始文本总行数
        :param sections: 最终处理后的Chunk列表
        """
        chunk_num = len(sections)
        # 输出核心统计信息：原始行数/最终Chunk数/首个Chunk预览
        self.logger.info("-" * 50 + " 文档切分统计信息 " + "-" * 50)
        self.logger.info(f"MD原始文本总行数：{lines_count}")
        self.logger.info(f"最终生成Chunk数量：{chunk_num}")
        #小于阈值 + 合前一个章节同父标题


    #备份
    def _step_6_backup(self,state,sections):
        print("步骤6 备份")
        #将sections切分结果输出的文档路径
        path = Path(state.get("md_path")).parent / f"{state.get('file_title')}_chunks.json"
        with open(path,"w",encoding="utf-8") as f:
            json.dump(
                sections,
                f,
                ensure_ascii=False,
                indent=4
            )

if __name__ == "__main__":
    node = NodeDocumentSplit()
    with open("D:/output/hak180产品安全手册/hak180产品安全手册_new.md","r",encoding="utf-8") as f:
        md_content = f.read()

    init_state = {
        "md_path":"D:/output/hak180产品安全手册/hak180产品安全手册_new.md",
        "md_content":md_content,
        "file_title":"hak180产品安全手册_new"
    }

    process = node.process(init_state)
    print(f"切分节点执行流程:{process}")
    