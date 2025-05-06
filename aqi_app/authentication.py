from rest_framework import authentication
from rest_framework import exceptions
from datetime import datetime
from jose import jwt, JWTError, ExpiredSignatureError
from django.conf import settings
from django.db import connection
import logging

logger = logging.getLogger(__name__)

class TokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None

        try:
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload['user_id']
            
            # 使用原生SQL查询
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, user_type, email FROM users WHERE id = %s", 
                    [user_id]
                )
                user_data = cursor.fetchone()
                
                if not user_data:
                    raise exceptions.AuthenticationFailed('User not found')
                
                # 创建一个类似于User模型的对象
                user = SimpleUser(
                    id=user_data[0],
                    username=user_data[1],
                    user_type=user_data[2],
                    email=user_data[3]
                )
                
                return (user, None)
        except (JWTError, ExpiredSignatureError):
            logger.warning("无效的token")
            raise exceptions.AuthenticationFailed('Invalid token')
        except Exception as e:
            logger.error(f"认证过程中发生错误: {str(e)}")
            raise exceptions.AuthenticationFailed(f'认证错误: {str(e)}')

# 简单的用户对象，模拟Django User模型
class SimpleUser:
    def __init__(self, id, username, user_type, email):
        self.id = id
        self.username = username
        self.user_type = user_type
        self.email = email
        self.is_authenticated = True
        
    def __str__(self):
        return self.username 