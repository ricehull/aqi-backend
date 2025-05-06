#!/bin/bash

# 激活虚拟环境
source .venv/bin/activate

# 迁移数据库
python manage.py makemigrations
python manage.py migrate

# 创建超级用户（如果需要）
# python manage.py createsuperuser

# 启动服务器
python manage.py runserver 0.0.0.0:8000 