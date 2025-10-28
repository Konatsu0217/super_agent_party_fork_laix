from http.server import HTTPServer, BaseHTTPRequestHandler
import json


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 只处理指定的API路径
        if self.path == '/api/consumption-status':
            # 设置响应头
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            # 构造并发送响应体 - 默认返回允许消费
            response = {
                "can_consume": True,
                "message": "Service is ready for consumption"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        elif self.path == '/':
            # 简单的健康检查页面
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Consumption Status Mock Service is running')
        else:
            # 处理其他路径
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # 可选：禁用日志输出，保持控制台干净
        return


def run_server(port=2345):
    """在指定端口启动HTTP服务器"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print(f'Starting mock service on port {port}...')
    print(f'API endpoint: http://localhost:{port}/api/consumption-status')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server(port=2345)