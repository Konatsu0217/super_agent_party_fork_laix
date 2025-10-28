import os
import asyncio
import logging
import threading
import time
import datetime
from collections import deque
from typing import List, Dict, Any, Optional
import json
import websockets

from fastapi import FastAPI, Body, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests
import uvicorn

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 加载JSON配置
class ConfigLoader:
    _instance = None
    _config = None
    
    @classmethod
    def get_config(cls, config_path='config.json'):
        if cls._config is None:
            cls._load_config(config_path)
        return cls._config
    
    @classmethod
    def _load_config(cls, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 扁平化配置，便于访问
            cls._config = {
                'port': config_data['server']['port'],
                'node_capacity': config_data['ring']['node_capacity'],
                'patch_lifetime': config_data['ring']['patch_lifetime'],
                'ring_size': config_data['ring']['ring_size'],
                'consume_check_url': config_data['consumption']['check_url'],
                'consume_check_timeout': config_data['consumption']['check_timeout'],
                'max_retry_count': config_data['consumption']['max_retry_count'],
                'retry_interval': config_data['consumption']['retry_interval'],
                'workers': config_data['server']['workers'],
                'limit_concurrency': config_data['server']['limit_concurrency'],
                'backlog': config_data['server']['backlog'],
                'reload': config_data['server']['reload'],
                'batch_size': config_data['queue']['batch_size'],
                'empty_sleep_time': config_data['queue']['empty_sleep_time']
            }
            logger.info(f"配置加载成功: {cls._config}")
        except Exception as e:
            logger.error(f"配置文件加载失败: {str(e)}")
            # 使用默认配置作为后备
            cls._config = {
                'port': 8000,
                'node_capacity': 100,
                'patch_lifetime': 8,
                'ring_size': 10,
                'consume_check_url': "http://localhost:2345/api/consumption-status",
                'consume_check_timeout': 5,
                'max_retry_count': 99,
                'retry_interval': 1,
                'workers': 'auto',
                'limit_concurrency': 1000,
                'backlog': 2048,
                'reload': True,
                'batch_size': 100,
                'empty_sleep_time': 0.01
            }
            logger.warning(f"使用默认配置: {cls._config}")


# 获取配置
config = ConfigLoader.get_config()


# 2. 定义环形链表节点
class RingNode:
    def __init__(self):
        # 使用固定长度的双端队列存储弹幕，自动丢弃老弹幕
        self.danmakus = deque(maxlen=config['node_capacity'])
        self.create_time = time.time()  # 创建时间
        self.next: Optional[RingNode] = None  # 指向下一个节点


# 3. 实现时间片轮转的环形链表
class TimeSliceRing:
    def __init__(self, size=config['ring_size'], node_capacity=config['node_capacity']):
        self.size = size
        self.node_capacity = node_capacity
        self.head = None  # 头节点
        self.current = None  # 当前节点
        self._init_ring()  # 初始化环形链表
        self.lock = threading.Lock()  # 添加线程锁保证线程安全
    
    def _init_ring(self):
        """初始化环形链表"""
        # 创建首节点
        self.head = RingNode()
        current = self.head
        
        # 创建剩余节点并连接成环形
        for _ in range(self.size - 1):
            new_node = RingNode()
            current.next = new_node
            current = new_node
        
        # 形成环形连接
        current.next = self.head
        
        # 设置当前节点为头节点
        self.current = self.head

    def add_danmaku(self, danmaku: Dict[str, Any]):
        with self.lock:  # 使用线程锁保护共享资源
            # 检查当前节点是否已满或已过期
            current_time = time.time()

            # 如果当前节点已过期，移动到下一个节点
            if current_time - self.current.create_time > config['patch_lifetime']:
                self.current = self.current.next
                # 重置当前节点
                self.current.danmakus = deque(maxlen=config['node_capacity'])  # 重新创建固定长度的双端队列
                self.current.create_time = current_time

            # 将弹幕添加到当前节点的队列中
            # 由于使用了deque(maxlen=config['node_capacity'])，当队列满时会自动丢弃队头元素
            self.current.danmakus.append(danmaku)
    
    def get_merged_danmaku(self, node: RingNode) -> Optional[Dict[str, Any]]:
        """合并节点中的所有弹幕"""
        with self.lock:
            if not node.danmakus:
                return None
            
            # 提取所有弹幕内容并合并
            contents = [dm['content'] for dm in node.danmakus]
            merged_content = '\n'.join(contents)
            
            # 构建合并后的弹幕数据
            # 使用第一个弹幕的类型作为合并后的类型
            first_danmaku = next(iter(node.danmakus), {})
            merged_danmaku = {
                'type': 'message',
                'content': merged_content,
                'danmu_type': first_danmaku.get('danmu_type', 'danmaku'),
                'count': len(node.danmakus)  # 添加弹幕数量信息
            }
            
            return merged_danmaku
    
    # 其他方法也需要添加线程锁保护
    def _clean_expired_nodes(self):
        with self.lock:
            # 清理所有过期的节点
            current_time = time.time()
            current = self.head
    
            for _ in range(self.size):
                if current_time - current.create_time > config['patch_lifetime']:
                    current.danmakus = deque(maxlen=config['node_capacity'])  # 重新创建固定长度的双端队列
                    current.create_time = current_time
                current = current.next


# 4. 创建FastAPI应用实例
app = FastAPI(
    title="Danmaku Proxy Service",
    description="极简弹幕代理服务",
    version="1.0.0"
)

# 5. 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 6. 定义请求模型
class DanmakuRequest(BaseModel):
    type: str = Field(..., description="消息类型")
    content: str = Field(..., description="弹幕内容")
    danmu_type: str = Field(..., description="弹幕类型")


# 7. 创建环形链表实例
ring = TimeSliceRing()

# 创建一个线程安全的异步队列
class AsyncDanmakuQueue:
    def __init__(self):
        self.queue = deque()
        self.lock = asyncio.Lock()
    
    async def put(self, item):
        async with self.lock:
            self.queue.append(item)
    
    async def get_batch(self, max_items=config['batch_size']):
        batch = []
        async with self.lock:
            while self.queue and len(batch) < max_items:
                batch.append(self.queue.popleft())
        return batch

# 创建全局队列实例
danmaku_queue = AsyncDanmakuQueue()

# WebSocket连接管理器
class WebSocketManager:
    def __init__(self):
        self.connections = set()
        self.lock = asyncio.Lock()
    
    async def connect(self, websocket):
        async with self.lock:
            self.connections.add(websocket)
    
    async def disconnect(self, websocket):
        async with self.lock:
            self.connections.discard(websocket)
    
    async def broadcast(self, message):
        """向所有连接的WebSocket客户端广播消息"""
        if not self.connections:
            return
        
        disconnected = set()
        async with self.lock:
            for websocket in self.connections:
                try:
                    await websocket.send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(websocket)
                except Exception as e:
                    logger.error(f"WebSocket广播消息时出错: {e}")
                    disconnected.add(websocket)
            
            # 移除断开的连接
            for websocket in disconnected:
                self.connections.discard(websocket)

# 创建WebSocket管理器实例
ws_manager = WebSocketManager()


# 修改process_danmaku_batch函数，保持将弹幕添加到TimeSliceRing但不合并
async def process_danmaku_batch():
    """后台任务：批量处理弹幕数据"""
    while True:
        # 获取一批弹幕（最多100条）
        batch = await danmaku_queue.get_batch(max_items=config['batch_size'])
        
        if not batch:
            # 如果队列为空，短暂休眠后继续
            await asyncio.sleep(config['empty_sleep_time'])  # 10ms
            continue
        
        try:
            # 批量处理弹幕
            for danmaku in batch:
                ring.add_danmaku(danmaku)
        except Exception as e:
            logger.error(f"处理弹幕批次时出错: {str(e)}")
        
        # 让出控制权，避免长时间占用事件循环
        await asyncio.sleep(0)  # 让出控制权


# 8. 定义消费函数
def consume():
    """消费过期的弹幕数据，会先检查远程服务是否允许消费，然后广播到前端"""
    while True:
        time.sleep(1)  # 每秒检查一次
        current_time = time.time()

        # 检查远程服务是否允许消费
        if not can_consume():
            logger.info("Remote service indicates consumption is not allowed at this time")
            continue

        # 遍历环形链表，检查并消费过期节点
        current = ring.head
        for _ in range(ring.size):
            if current_time - current.create_time > config['patch_lifetime'] and current.danmakus:
                # 消费逻辑 - 获取合并后的弹幕数据（在消费前才进行合并）
                merged_danmaku = ring.get_merged_danmaku(current)
                if merged_danmaku:
                    print(f"Consuming merged danmaku at {datetime.datetime.now()}: {merged_danmaku}")
                    
                    # 广播到所有WebSocket客户端
                    broadcast_message = {
                        'type': 'message',
                        'content': merged_danmaku,
                        'danmu_type': 'danmaku',
                        'timestamp': datetime.datetime.now().isoformat()
                    }
                    
                    # 将消息添加到广播队列，由异步任务处理
                    try:
                        # 创建新的异步任务来广播消息
                        asyncio.create_task(ws_manager.broadcast(broadcast_message))
                    except Exception as e:
                        logger.error(f"创建WebSocket广播任务失败: {e}")
                    
                    # 清空已消费的弹幕
                    current.danmakus.clear()
            current = current.next


# 添加检查远程服务是否允许消费的函数
def can_consume():
    """
    检查远程服务是否允许消费弹幕
    返回: bool - True表示允许消费，False表示不允许消费
    """
    retry_count = 0
    while retry_count <= config['max_retry_count']:
        try:
            # 发送GET请求到远程服务
            response = requests.get(
                config['consume_check_url'],
                timeout=config['consume_check_timeout']
            )

            # 检查响应状态码
            if response.status_code == 200:
                # 解析JSON响应
                data = response.json()
                # 假设远程服务返回的JSON包含一个'can_consume'布尔字段
                return data.get('can_consume', False)
            else:
                logger.warning(f"Remote service returned non-200 status code: {response.status_code}")
                retry_count += 1
                time.sleep(config['retry_interval'])
        except requests.exceptions.RequestException as e:
            # 处理请求异常
            logger.error(f"Error connecting to remote service: {str(e)}")
            retry_count += 1
            time.sleep(config['retry_interval'])

    # 重试次数耗尽，默认返回False表示不允许消费
    logger.error(f"Failed to check consumption status after {config['max_retry_count']} retries")
    return False


# 9. 启动消费者线程和后台任务
@app.on_event("startup")
async def startup_event():
    # 启动批量处理任务
    asyncio.create_task(process_danmaku_batch())
    # 启动消费者线程
    consumer_thread = threading.Thread(target=consume, daemon=True)
    consumer_thread.start()


# 10. 定义路由和处理函数
@app.post("/danmaku/add_danmaku", summary="接收弹幕")
async def receive_danmaku(data: DanmakuRequest = Body(...)):
    # 快速失败检查 - 减少不必要的处理
    if data.type != "danmaku":
        raise HTTPException(status_code=400, detail="只处理type为'danmaku'的消息")

    # 构建弹幕数据 - 避免复杂计算
    danmaku_data = {
        'content': data.content,
        'danmu_type': data.danmu_type,
        'timestamp': time.time()
    }

    # 异步添加到队列，非阻塞操作
    await danmaku_queue.put(danmaku_data)

    # 立即返回响应，不等待实际处理完成
    return {
        "success": True,
        "message": "弹幕已接收"
    }


# WebSocket端点
@app.websocket("/ws/danmaku")
async def websocket_endpoint(websocket):
    """WebSocket连接端点，用于接收弹幕消息"""
    await ws_manager.connect(websocket)
    try:
        while True:
            # 保持连接活跃，接收客户端消息（可选）
            data = await websocket.receive_text()
            # 可以处理客户端发送的消息，这里只是保持连接
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await ws_manager.disconnect(websocket)


# 11. 启动服务的入口
if __name__ == "__main__":

    # ============== 这里是可消费模拟服务，上线去除 ======================
    import mock_service_simple as mock_service
    
    # 创建并启动一个线程来运行模拟服务
    mock_thread = threading.Thread(
        target=mock_service.run_server,
        args=(2345,),
        daemon=True
    )
    mock_thread.start()
    # ============== 这里是可消费模拟服务，上线去除 ======================

    # 计算工作进程数
    if config['workers'] == 'auto':
        workers = min(8, os.cpu_count() * 2 + 1)  # 根据CPU核心数设置工作进程数
    else:
        workers = int(config['workers'])
    
    # 启动uvicorn服务
    uvicorn.run(
        "danmaku_proxy:app",
        host="127.0.0.1",
        port=config['port'],
        reload=config['reload'],
        workers=workers,
        limit_concurrency=config['limit_concurrency'],
        backlog=config['backlog']
    )