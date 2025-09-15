# main.py - WSGI 应用程序入口点
from app import app as application

# 确保 Gunicorn 可以找到应用
app = application

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5001, debug=False)