import time
import requests
import concurrent.futures
import random
import json
from datetime import datetime
import statistics
from tqdm import tqdm  # 用于显示进度条

# 配置参数
target_url = "http://127.0.0.1:8000/danmaku/add_danmaku"  # 目标API地址
concurrent_workers = 100  # 并发工作线程数
total_requests = 10000  # 总请求数
timeout = 5  # 单个请求超时时间(秒)

# 生成随机弹幕内容
def generate_danmaku_content():
    """生成随机的弹幕内容"""
    contents = [
        "这直播太精彩了！", "主播666", "哈哈哈", "老铁们点个关注", "666666",
        "什么情况？", "笑死我了", "主播好厉害", "我来了我来了", "这个操作绝了",
        "太秀了", "无敌了", "好看好看", "关注了关注了", "主播加油"
    ]
    return random.choice(contents)

# 发送单个请求
def send_request(session):
    """发送单个弹幕请求并返回结果"""
    start_time = time.time()
    try:
        payload = {
            "type": "danmaku",
            "content": generate_danmaku_content(),
            "danmu_type": "danmaku"
        }
        response = session.post(
            target_url,
            json=payload,
            timeout=timeout
        )
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # 转换为毫秒
        
        if response.status_code == 200:
            return True, response_time, None
        else:
            return False, response_time, f"HTTP {response.status_code}"
    except Exception as e:
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # 转换为毫秒
        return False, response_time, str(e)

# 主压测函数
def run_load_test():
    """运行压测并输出结果"""
    print(f"\n=== 弹幕代理服务压测开始 ===")
    print(f"目标URL: {target_url}")
    print(f"并发线程数: {concurrent_workers}")
    print(f"总请求数: {total_requests}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 创建会话以重用连接
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    # 初始化统计数据
    success_count = 0
    failure_count = 0
    response_times = []
    errors = []
    
    # 开始计时
    overall_start_time = time.time()
    
    # 使用线程池执行并发请求
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
        # 创建所有请求任务
        futures = [executor.submit(send_request, session) for _ in range(total_requests)]
        
        # 使用tqdm显示进度
        for future in tqdm(concurrent.futures.as_completed(futures), total=total_requests, desc="压测进度"):
            success, response_time, error_msg = future.result()
            response_times.append(response_time)
            
            if success:
                success_count += 1
            else:
                failure_count += 1
                errors.append(error_msg)
    
    # 结束计时
    overall_end_time = time.time()
    total_duration = overall_end_time - overall_start_time
    
    # 计算QPS
    qps = total_requests / total_duration if total_duration > 0 else 0
    
    # 计算响应时间统计
    if response_times:
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # 计算中位数和百分位数
        response_times_sorted = sorted(response_times)
        p50 = response_times_sorted[int(len(response_times_sorted) * 0.5)]
        p90 = response_times_sorted[int(len(response_times_sorted) * 0.9)]
        p95 = response_times_sorted[int(len(response_times_sorted) * 0.95)]
        p99 = response_times_sorted[int(len(response_times_sorted) * 0.99)]
    else:
        avg_response_time = min_response_time = max_response_time = p50 = p90 = p95 = p99 = 0
    
    # 输出结果
    print("\n" + "=" * 50)
    print(f"=== 压测结果 ===")
    print(f"总耗时: {total_duration:.2f} 秒")
    print(f"成功请求数: {success_count}")
    print(f"失败请求数: {failure_count}")
    print(f"成功率: {(success_count/total_requests*100):.2f}%")
    print(f"QPS (每秒请求数): {qps:.2f}")
    print("\n响应时间统计 (毫秒):")
    print(f"平均响应时间: {avg_response_time:.2f}")
    print(f"最小响应时间: {min_response_time:.2f}")
    print(f"最大响应时间: {max_response_time:.2f}")
    print(f"中位数响应时间 (P50): {p50:.2f}")
    print(f"90%请求响应时间 (P90): {p90:.2f}")
    print(f"95%请求响应时间 (P95): {p95:.2f}")
    print(f"99%请求响应时间 (P99): {p99:.2f}")
    
    # 输出错误摘要
    if errors:
        print("\n错误摘要:")
        # 统计每种错误出现的次数
        error_counts = {}
        for error in errors:
            error_counts[error] = error_counts.get(error, 0) + 1
        
        # 输出前5种最常见的错误
        sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
        for error, count in sorted_errors[:5]:
            print(f"  '{error}': {count}次")
    
    print("=" * 50)
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    # 运行压测前先检查服务是否可用
    try:
        test_response = requests.get("http://127.0.0.1:8000/docs", timeout=2)
        if test_response.status_code == 200:
            print("服务检测成功，开始压测...")
            run_load_test()
        else:
            print(f"服务检测失败，HTTP状态码: {test_response.status_code}")
            print("请确保弹幕代理服务已启动并监听在8000端口")
    except Exception as e:
        print(f"服务检测失败: {str(e)}")
        print("请确保弹幕代理服务已启动并监听在8000端口")
