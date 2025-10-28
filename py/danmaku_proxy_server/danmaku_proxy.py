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
                'empty_sleep_time': config_data['queue']['empty_sleep_time'],
                # 主服务配置
                'main_server_consume_url': config_data.get('main_server', {}).get('consume_url', 'http://localhost:3456/api/danmaku/consume'),
                'main_server_timeout': config_data.get('main_server', {}).get('timeout', 5),
                'main_server_max_retry_count': config_data.get('main_server', {}).get('max_retry_count', 3),
                'main_server_retry_interval': config_data.get('main_server', {}).get('retry_interval', 1)
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
                'empty_sleep_time': 0.01,
                # 主服务默认配置
                'main_server_consume_url': 'http://localhost:3456/api/danmaku/consume',
                'main_server_timeout': 5,
                'main_server_max_retry_count': 3,
                'main_server_retry_interval': 1
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


# 3. 简化的双bucket交替工作机制
class DualBucketSystem:
    def __init__(self, bucket_capacity=config['node_capacity'], bucket_lifetime=config['patch_lifetime']):
        self.bucket_capacity = bucket_capacity
        self.bucket_lifetime = bucket_lifetime
        self.lock = threading.Lock()
        
        # 两个bucket：A和B
        self.bucket_a = {
            'danmakus': deque(maxlen=bucket_capacity),
            'start_time': time.time(),
            'is_active': True,  # A桶当前是否活跃
            'is_consuming': False  # A桶是否正在消费
        }
        
        self.bucket_b = {
            'danmakus': deque(maxlen=bucket_capacity),
            'start_time': None,  # B桶在A桶发送后才开始计时
            'is_active': False,  # B桶当前是否活跃
            'is_consuming': False  # B桶是否正在消费
        }
        
        self.current_bucket = self.bucket_a  # 当前活跃的bucket
    
    def add_danmaku(self, danmaku: Dict[str, Any]):
        """添加弹幕到当前活跃的bucket"""
        with self.lock:
            if self.current_bucket['is_consuming']:
                logger.warning(f"⚠️ Bucket正在消费中，弹幕被丢弃: {danmaku['content'][:30]}...")
                return
            
            # 添加到当前活跃的bucket
            self.current_bucket['danmakus'].append(danmaku)
            logger.debug(f"📥 弹幕已添加到{'A' if self.current_bucket == self.bucket_a else 'B'}桶: {danmaku['content'][:30]}...")
    
    def get_consumable_bucket(self):
        """获取可消费的bucket"""
        with self.lock:
            current_time = time.time()
            
            # 检查A桶是否到期且未在消费
            if (self.bucket_a['is_active'] and 
                not self.bucket_a['is_consuming'] and
                self.bucket_a['danmakus'] and
                current_time - self.bucket_a['start_time'] > self.bucket_lifetime):
                return self.bucket_a
            
            # 检查B桶是否到期且未在消费（B桶已开始计时）
            if (self.bucket_b['is_active'] and 
                not self.bucket_b['is_consuming'] and
                self.bucket_b['danmakus'] and
                self.bucket_b['start_time'] is not None and
                current_time - self.bucket_b['start_time'] > self.bucket_lifetime):
                return self.bucket_b
            
            return None
    
    def mark_bucket_consuming(self, bucket):
        """标记bucket正在消费"""
        with self.lock:
            bucket['is_consuming'] = True
    
    def switch_bucket(self):
        """切换bucket：当前bucket消费完成后，切换到另一个bucket"""
        with self.lock:
            if self.current_bucket == self.bucket_a:
                # A桶消费完成，切换到B桶
                logger.info("🔄 A桶消费完成，切换到B桶")
                self.bucket_a['is_active'] = False
                self.bucket_a['is_consuming'] = False
                self.bucket_a['danmakus'].clear()
                
                # B桶开始计时
                self.bucket_b['is_active'] = True
                self.bucket_b['start_time'] = time.time()
                self.current_bucket = self.bucket_b
                
            else:
                # B桶消费完成，切换回A桶
                logger.info("🔄 B桶消费完成，切换到A桶")
                self.bucket_b['is_active'] = False
                self.bucket_b['is_consuming'] = False
                self.bucket_b['danmakus'].clear()
                self.bucket_b['start_time'] = None
                
                # A桶重新开始计时
                self.bucket_a['is_active'] = True
                self.bucket_a['start_time'] = time.time()
                self.current_bucket = self.bucket_a
    
    def get_merged_danmaku(self, bucket):
        """合并bucket中的所有弹幕"""
        with self.lock:
            if not bucket['danmakus']:
                return None
            
            # 提取所有弹幕内容并合并
            contents = [dm['content'] for dm in bucket['danmakus']]
            merged_content = '\n'.join(contents)
            
            # 使用第一个弹幕的类型作为合并后的类型
            first_danmaku = next(iter(bucket['danmakus']), {})
            merged_danmaku = {
                'type': 'message',
                'content': merged_content,
                'danmu_type': first_danmaku.get('danmu_type', 'danmaku'),
                'count': len(bucket['danmakus'])
            }
            
            return merged_danmaku


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


# 7. 创建双bucket系统实例
bucket_system = DualBucketSystem()

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

# 全局事件循环管理器
class EventLoopManager:
    def __init__(self):
        self.loop = None
        self._lock = threading.Lock()
    
    def get_loop(self):
        """获取或创建事件循环"""
        with self._lock:
            if self.loop is None or self.loop.is_closed():
                try:
                    self.loop = asyncio.get_event_loop()
                except RuntimeError:
                    self.loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self.loop)
            return self.loop
    
    def run_coroutine(self, coro):
        """在线程中运行协程"""
        loop = self.get_loop()
        if loop.is_running():
            # 如果循环已经在运行，创建任务
            return asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            # 如果循环没有运行，直接运行
            return loop.run_until_complete(coro)

event_loop_manager = EventLoopManager()


# 修改process_danmaku_batch函数，将弹幕添加到bucket系统
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
                bucket_system.add_danmaku(danmaku)
        except Exception as e:
            logger.error(f"处理弹幕批次时出错: {str(e)}")
        
        # 让出控制权，避免长时间占用事件循环
        await asyncio.sleep(0)  # 让出控制权


# 8. 定义消费函数（异步版本）
async def consume_async():
    """异步消费过期的弹幕数据，会先检查远程服务是否允许消费，然后发送到主服务接口"""
    while True:
        await asyncio.sleep(1)  # 异步等待1秒
        # 检查远程服务是否允许消费
        if not can_consume():
            logger.info("Remote service indicates consumption is not allowed at this time")
            continue
        
        # 双bucket交替工作机制
        consumable_bucket = bucket_system.get_consumable_bucket()
        if consumable_bucket:
            # 标记bucket为正在消费状态
            bucket_system.mark_bucket_consuming(consumable_bucket)
            
            # 获取合并后的弹幕数据
            merged_danmaku = bucket_system.get_merged_danmaku(consumable_bucket)
            if merged_danmaku:
                bucket_name = "A" if consumable_bucket == bucket_system.bucket_a else "B"
                logger.info(f"🔄 双bucket交替工作 - 消费{bucket_name}桶弹幕: {merged_danmaku['content'][:50]}...")
                
                # 构建消费消息
                consume_message = {
                    'type': 'message',
                    'content': merged_danmaku['content'],
                    'danmu_type': merged_danmaku['danmu_type'],
                    'timestamp': datetime.datetime.now().isoformat()
                }
                
                # 发送到主服务
                try:
                    await send_to_main_server(consume_message)
                    logger.info(f"✅ 成功发送到主服务: {consume_message}")
                    
                    # 切换bucket（在switch_bucket中处理）
                    bucket_system.switch_bucket()
                        
                except Exception as e:
                    logger.error(f"发送到主服务失败: {e}", exc_info=True)
                    # 消费失败也要切换bucket
                    bucket_system.switch_bucket()
        else:
            logger.debug("暂无可消费节点，继续等待...")


# 保持同步版本用于线程
def consume():
    """同步消费函数，包装异步版本"""
    try:
        # 获取或创建事件循环
        loop = None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # 如果循环已经在运行，创建任务
            asyncio.create_task(consume_async())
        else:
            # 如果循环没有运行，直接运行
            loop.run_until_complete(consume_async())
    except Exception as e:
        logger.error(f"消费函数运行失败: {e}", exc_info=True)


# 添加检查远程服务是否允许消费的函数
def can_consume():
    """
    检查远程服务是否允许消费弹幕，请求主服务的/api/consumption-status接口
    返回: bool - True表示允许消费，False表示不允许消费
    """
    retry_count = 0
    while retry_count <= config['max_retry_count']:
        try:
            # 发送GET请求到主服务的消费状态接口
            response = requests.get(
                config['consume_check_url'],
                timeout=config['consume_check_timeout'],
                headers={'Content-Type': 'application/json'}
            )

            # 检查响应状态码
            if response.status_code == 200:
                # 解析JSON响应
                data = response.json()
                # 主服务返回的JSON包含'can_consume'布尔字段，基于isLLMWorking状态
                can_consume_result = data.get('can_consume', False)
                logger.info(f"主服务消费状态检查成功: can_consume={can_consume_result}")
                return can_consume_result
            else:
                logger.warning(f"主服务返回非200状态码: {response.status_code}")
                retry_count += 1
                time.sleep(config['retry_interval'])
        except requests.exceptions.RequestException as e:
            # 处理请求异常
            logger.error(f"连接主服务失败: {str(e)}")
            retry_count += 1
            time.sleep(config['retry_interval'])
        except json.JSONDecodeError as e:
            logger.error(f"解析主服务响应JSON失败: {str(e)}")
            retry_count += 1
            time.sleep(config['retry_interval'])

    # 重试次数耗尽，默认返回False表示不允许消费
    logger.error(f"检查消费状态失败，重试{config['max_retry_count']}次后放弃")
    return False


# 新增：发送弹幕消息到主服务
async def send_to_main_server(message: dict):
    """
    异步发送弹幕消息到主服务的消费接口，支持重试机制
    """
    retry_count = 0
    max_retries = config['main_server_max_retry_count']
    
    while retry_count <= max_retries:
        try:
            # 主服务的消费接口URL
            main_server_url = config['main_server_consume_url']
            headers = {"Content-Type": "application/json"}
            timeout = config['main_server_timeout']
            
            # 使用异步HTTP客户端发送请求
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    main_server_url, 
                    json=message, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('success'):
                            logger.info(f"弹幕消息成功发送到主服务: {message.get('content', '')[:50]}...")
                            return True
                        else:
                            logger.error(f"主服务处理失败: {result.get('message', 'Unknown error')}")
                            return False
                    else:
                        logger.error(f"主服务返回错误状态码: {response.status}")
                        return False
                        
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                logger.warning(f"发送到主服务失败 (尝试 {retry_count}/{max_retries + 1}): {str(e)}")
                await asyncio.sleep(config['main_server_retry_interval'])
            else:
                logger.error(f"发送到主服务失败，重试次数耗尽: {str(e)}", exc_info=True)
                # 可以选择重试或记录失败的消息
                raise e
    
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
    if data.danmu_type != "danmaku":
        raise HTTPException(status_code=400, detail="只处理danmu_type为'danmaku'的消息")

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


# 启动消费任务的函数
async def start_consume_task():
    """启动异步消费任务"""
    try:
        logger.info("启动弹幕消费任务")
        await consume_async()
    except Exception as e:
        logger.error(f"消费任务启动失败: {e}", exc_info=True)


# WebSocket端点
@app.websocket("/ws/danmaku")
async def websocket_endpoint(websocket):
    """WebSocket连接端点，用于接收弹幕消息"""
    logger.info(f"收到WebSocket连接请求，客户端: {websocket.client}")
    try:
        await websocket.accept()  # 接受WebSocket连接
        logger.info("WebSocket连接已接受")
        await ws_manager.connect(websocket)
        logger.info(f"WebSocket客户端已添加到管理器，当前连接数: {len(ws_manager.connections)}")
        
        while True:
            # 保持连接活跃，接收客户端消息（可选）
            data = await websocket.receive_text()
            logger.info(f"收到WebSocket消息: {data}")
            # 可以处理客户端发送的消息，这里只是保持连接
            
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket连接已关闭")
    except Exception as e:
        logger.error(f"WebSocket连接错误: {e}", exc_info=True)
    finally:
        await ws_manager.disconnect(websocket)
        logger.info(f"WebSocket客户端已断开，剩余连接数: {len(ws_manager.connections)}")


# 11. 启动服务的入口
if __name__ == "__main__":

    # ============== 这里是可消费模拟服务，上线去除 ======================
    # import mock_service_simple as mock_service
    #
    # # 创建并启动一个线程来运行模拟服务
    # mock_thread = threading.Thread(
    #     target=mock_service.run_server,
    #     args=(2345,),
    #     daemon=True
    # )
    # mock_thread.start()
    # ============== 这里是可消费模拟服务，上线去除 ======================

    # 计算工作进程数
    if config['workers'] == 'auto':
        workers = min(8, os.cpu_count() * 2 + 1)  # 根据CPU核心数设置工作进程数
    else:
        workers = int(config['workers'])
    
    # 启动异步任务
    async def main():
        """主异步函数"""
        # 启动消费任务
        consume_task = asyncio.create_task(consume_async())
        logger.info("弹幕消费任务已启动")
        
        # 启动uvicorn服务
        uvicorn_config = uvicorn.Config(
            "danmaku_proxy:app",
            host="0.0.0.0",  # 允许所有IP连接
            port=config['port'],
            reload=config['reload'],
            workers=workers,  # 使用单进程模式便于调试
            limit_concurrency=config['limit_concurrency'],
            backlog=config['backlog'],
            log_level="info"
        )
        server = uvicorn.Server(uvicorn_config)
        await server.serve()
    
    # 运行主异步函数
    asyncio.run(main())