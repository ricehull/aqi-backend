import mysql.connector
from datetime import datetime, timedelta
from jose import jwt
import os

# 数据库配置
db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'aqi_service'
}

def insert_users():
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 插入个人用户
        cursor.execute("""
            INSERT INTO users (username, password, email, user_type)
            VALUES (%s, %s, %s, %s)
        """, ('individual_user', 'password123', 'individual@example.com', 'individual'))
        
        # 获取个人用户ID
        individual_user_id = cursor.lastrowid
        
        # 插入企业用户
        cursor.execute("""
            INSERT INTO users (username, password, email, user_type)
            VALUES (%s, %s, %s, %s)
        """, ('enterprise_user', 'password123', 'enterprise@example.com', 'enterprise'))
        
        # 获取企业用户ID
        enterprise_user_id = cursor.lastrowid
        
        # 生成token
        secret_key = 'your-secret-key-here'  # 与settings.py中的SECRET_KEY保持一致
        
        # 为个人用户生成token
        individual_token = jwt.encode({
            'user_id': individual_user_id,
            'exp': datetime.utcnow() + timedelta(days=1)
        }, secret_key, algorithm='HS256')
        
        # 为企业用户生成token
        enterprise_token = jwt.encode({
            'user_id': enterprise_user_id,
            'exp': datetime.utcnow() + timedelta(days=1)
        }, secret_key, algorithm='HS256')
        
        # 插入token
        cursor.execute("""
            INSERT INTO user_tokens (user_id, token, expires_at)
            VALUES (%s, %s, %s)
        """, (individual_user_id, individual_token, datetime.utcnow() + timedelta(days=1)))
        
        cursor.execute("""
            INSERT INTO user_tokens (user_id, token, expires_at)
            VALUES (%s, %s, %s)
        """, (enterprise_user_id, enterprise_token, datetime.utcnow() + timedelta(days=1)))
        
        # 提交更改
        conn.commit()
        
        print("Users inserted successfully!")
        print("\nIndividual User:")
        print(f"Username: individual_user")
        print(f"Password: password123")
        print(f"Token: {individual_token}")
        print("\nEnterprise User:")
        print(f"Username: enterprise_user")
        print(f"Password: password123")
        print(f"Token: {enterprise_token}")
        
    except Exception as e:
        print(f"Error inserting users: {str(e)}")
        if conn.is_connected():
            conn.rollback()
    
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    insert_users() 