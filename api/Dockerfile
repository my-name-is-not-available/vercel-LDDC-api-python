# 使用官方Python镜像作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制requirements.txt文件到工作目录
COPY requirements.txt .

# 安装依赖包
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有Python文件和LDDC目录
# 当复制多个文件时，目标必须是目录并以/结尾
COPY *.py /app/
COPY LDDC/ /app/LDDC/

# 添加调试命令，列出/app目录内容以验证文件是否存在
RUN ls -la /app

# 设置环境变量，指定Python路径
ENV PYTHONPATH=/app

# 暴露端口8000
EXPOSE 8000

# 使用api_server.py作为主入口启动服务
CMD ["python", "api_server.py"]