from rest_framework import serializers
from django.contrib.auth import get_user_model
from jose import jwt
from datetime import datetime, timedelta
from django.conf import settings
import logging
from django.db import connection

logger = logging.getLogger(__name__)
User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'user_type')
        read_only_fields = ('id',)

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'user_type')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            user_type=validated_data['user_type']
        )
        return user

class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            logger.info(f"尝试验证用户: {data['username']}")
            
            # 完全使用原生SQL查询
            with connection.cursor() as cursor:
                # 检查用户是否存在
                cursor.execute(
                    "SELECT id, username, user_type, password FROM users WHERE username = %s", 
                    [data['username']]
                )
                user_data = cursor.fetchone()
                
                if not user_data:
                    logger.warning(f"用户不存在: {data['username']}")
                    raise serializers.ValidationError('用户不存在')
                
                user_id, username, user_type, stored_password = user_data
                
                # 直接比较密码（这是简化的处理，生产环境应该用哈希比较）
                if data['password'] == stored_password:
                    logger.info(f"用户 {data['username']} 通过密码验证成功")
                    return {
                        'user': {
                            'id': user_id,
                            'username': username,
                            'userType': user_type
                        },
                        'token': self._generate_jwt_token(user_id)
                    }
                
                logger.warning(f"用户 {data['username']} 密码验证失败")
                raise serializers.ValidationError('密码错误')
        except Exception as e:
            logger.error(f"验证过程中发生错误: {str(e)}")
            raise serializers.ValidationError(f'验证出错: {str(e)}')

    def _generate_jwt_token(self, user_id):
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(days=1),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256') 