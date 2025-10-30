# -- coding: utf-8 --
"""
深度研究系统模块
负责管理深度研究的各个阶段
"""
import json
import logging
from typing import Dict, Any, Optional, Tuple
from config.constants import DRS_STAGE_1, DRS_STAGE_2, DRS_STAGE_3, DRS_STAGE_NAMES, DRS_STAGE_MESSAGES


class DeepResearchSystem:
    """深度研究系统"""
    
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        
    def get_initial_stage(self, message_count: int) -> int:
        """
        根据消息数量确定初始研究阶段
        
        Args:
            message_count: 消息数量
            
        Returns:
            研究阶段 (1, 2, 或 3)
        """
        if message_count > 2:
            return DRS_STAGE_2  # 查询搜索阶段
        return DRS_STAGE_1      # 明确用户需求阶段
        
    def get_stage_name(self, stage: int) -> str:
        """
        获取阶段名称
        
        Args:
            stage: 阶段编号
            
        Returns:
            阶段名称
        """
        return DRS_STAGE_NAMES.get(stage, DRS_STAGE_NAMES[DRS_STAGE_3])
        
    def get_stage_message(self, stage: int) -> str:
        """
        获取阶段描述消息
        
        Args:
            stage: 阶段编号
            
        Returns:
            阶段描述
        """
        return DRS_STAGE_MESSAGES.get(stage, DRS_STAGE_MESSAGES[DRS_STAGE_3])
        
    def create_stage_prompt(self, stage: int, user_prompt: str, full_content: str) -> str:
        """
        创建阶段提示
        
        Args:
            stage: 当前阶段
            user_prompt: 用户原始提示
            full_content: 当前累积的内容
            
        Returns:
            阶段提示文本
        """
        stage_name = self.get_stage_name(stage)
        
        if stage == DRS_STAGE_1:
            return self._create_stage_1_prompt(user_prompt, full_content, stage_name)
        elif stage == DRS_STAGE_2:
            return self._create_stage_2_prompt(user_prompt, full_content, stage_name)
        else:
            return self._create_stage_3_prompt(user_prompt, full_content, stage_name)
            
    def _create_stage_1_prompt(self, user_prompt: str, full_content: str, stage_name: str) -> str:
        """创建第一阶段提示"""
        return f"""
# 当前状态：

## 初始任务：
{user_prompt}

## 当前结果：
{full_content}

## 当前阶段：
{stage_name}

# 深度研究一共有三个阶段：1: 明确用户需求阶段 2: 查询搜索阶段 3: 生成结果阶段

## 当前阶段，请输出json字符串：

### 如果需要用户明确需求，请输出json字符串：
{{
    "status": "need_more_info",
    "unfinished_task": ""
}}

### 如果不需要进一步明确需求，进入并进入查询搜索阶段，请输出json字符串：
{{
    "status": "search",
    "unfinished_task": ""
}}
"""
        
    def _create_stage_2_prompt(self, user_prompt: str, full_content: str, stage_name: str) -> str:
        """创建第二阶段提示"""
        return f"""
# 当前状态：

## 初始任务：
{user_prompt}

## 当前结果：
{full_content}

## 当前阶段：
{stage_name}

# 深度研究一共有三个阶段：1: 明确用户需求阶段 2: 查询搜索阶段 3: 生成结果阶段

## 当前阶段，请输出json字符串：

### 如果需要继续查询，请输出json字符串：
{{
    "status": "need_more_search",
    "unfinished_task": "这里填入继续查询的信息"
}}

### 如果不需要进一步明确需求，进入并进入查询搜索阶段，请输出json字符串：
{{
    "status": "answer",
    "unfinished_task": ""
}}
"""
        
    def _create_stage_3_prompt(self, user_prompt: str, full_content: str, stage_name: str) -> str:
        """创建第三阶段提示"""
        return f"""
# 当前状态：

## 初始任务：
{user_prompt}

## 当前结果：
{full_content}

## 当前阶段：
{stage_name}

# 深度研究一共有三个阶段：1: 明确用户需求阶段 2: 查询搜索阶段 3: 生成结果阶段

## 当前阶段，请输出json字符串：

如果初始任务已完成，请输出json字符串：
{{
    "status": "done",
    "unfinished_task": ""
}}

如果初始任务未完成，请输出json字符串：
{{
    "status": "not_done",
    "unfinished_task": "这里填入未完成的任务"
}}
"""
        
    def parse_stage_response(self, response_content: str) -> Tuple[str, Optional[str]]:
        """
        解析阶段响应
        
        Args:
            response_content: 响应内容
            
        Returns:
            (状态, 未完成任务) 元组
        """
        try:
            # 尝试提取JSON
            if "```json" in response_content:
                try:
                    import re
                    json_match = re.search(r'```json(.*?)```', response_content, re.DOTALL)
                    if json_match:
                        response_content = json_match.group(1).strip()
                    else:
                        # 尝试提取```json之后的内容
                        json_match = re.search(r'```json(.*)', response_content, re.DOTALL)
                        if json_match:
                            response_content = json_match.group(1).strip()
                except Exception as e:
                    self._logger.warning(f"提取JSON失败: {e}")
            
            # 解析JSON
            data = json.loads(response_content)
            
            status = data.get("status", "error")
            unfinished_task = data.get("unfinished_task", "")
            
            return status, unfinished_task
            
        except json.JSONDecodeError as e:
            self._logger.error(f"解析阶段响应JSON失败: {e}")
            return "error", None
            
    def get_next_stage(self, current_stage: int, status: str) -> int:
        """
        根据当前状态和响应确定下一阶段
        
        Args:
            current_stage: 当前阶段
            status: 响应状态
            
        Returns:
            下一阶段
        """
        if status == "need_more_info":
            return DRS_STAGE_2  # 需要更多信息，进入搜索阶段
        elif status == "search":
            return DRS_STAGE_2  # 进入搜索阶段
        elif status == "need_more_search":
            return DRS_STAGE_2  # 继续搜索
        elif status == "answer":
            return DRS_STAGE_3  # 进入回答阶段
        elif status == "done":
            return DRS_STAGE_3  # 完成，保持在回答阶段
        elif status == "not_done":
            return DRS_STAGE_3  # 未完成，继续回答阶段
        else:
            return current_stage  # 保持当前阶段
            
    def create_stage_transition_chunk(self, status: str, translate_func) -> Dict[str, Any]:
        """
        创建阶段转换的流式响应块
        
        Args:
            status: 状态
            translate_func: 翻译函数
            
        Returns:
            流式响应块
        """
        status_messages = {
            "need_more_info": f"❓{translate_func('task_need_more_info')}",
            "search": f"🔍{translate_func('enter_search_stage')}",
            "need_more_search": f"🔍{translate_func('need_more_search')}",
            "answer": f"⭐{translate_func('enter_answer_stage')}",
            "done": f"✅{translate_func('task_done')}",
            "not_done": f"❎{translate_func('task_not_done')}",
            "error": f"❌{translate_func('task_error')}"
        }
        
        message = status_messages.get(status, f"❌{translate_func('task_error')}")
        
        return {
            "choices": [{
                "delta": {
                    "tool_content": f'\n\n<div class="highlight-block">\n{message}</div>\n\n'
                }
            }]
        }


# 全局深度研究系统实例
deep_research_system = DeepResearchSystem()