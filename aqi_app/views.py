from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db import connection
from .serializers import UserSerializer, UserRegistrationSerializer, UserLoginSerializer
from .models import User
import pandas as pd
from autogluon.tabular import TabularPredictor
import base64
from io import BytesIO
from PIL import Image
import requests
import os
import random
import logging

logger = logging.getLogger(__name__)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            # 直接使用SQL插入用户，而不是用ORM
            try:
                with connection.cursor() as cursor:
                    # 检查用户名和邮箱是否已存在
                    cursor.execute(
                        "SELECT id FROM users WHERE username = %s OR email = %s",
                        [request.data['username'], request.data['email']]
                    )
                    if cursor.fetchone():
                        return Response(
                            {"error": "用户名或邮箱已存在"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # 插入新用户
                    cursor.execute(
                        """
                        INSERT INTO users (username, password, email, user_type)
                        VALUES (%s, %s, %s, %s)
                        """,
                        [
                            request.data['username'],
                            request.data['password'],  # 注意：生产环境应哈希密码
                            request.data['email'],
                            request.data['user_type']
                        ]
                    )
                    
                    # 获取新插入的用户ID
                    user_id = cursor.lastrowid
                    
                    return Response({
                        'user': {
                            'id': user_id,
                            'username': request.data['username'],
                            'userType': request.data['user_type'],
                            'email': request.data['email']
                        },
                        'message': 'User created successfully'
                    }, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def login(self, request):
        try:
            serializer = UserLoginSerializer(data=request.data)
            if serializer.is_valid():
                # 添加支持的城市列表
                supported_cities = AQIViewSet()._get_supported_cities()
                # 获取默认城市的AQI数据
                default_city = supported_cities[0] if supported_cities else None
                
                response_data = serializer.validated_data
                response_data['supported_cities'] = supported_cities
                
                # 如果有默认城市，添加默认城市的AQI数据
                if default_city:
                    # 使用原生SQL查询
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT id, username, user_type, email FROM users WHERE username = %s",
                            [request.data['username']]
                        )
                        user_data = cursor.fetchone()
                        
                        if user_data:
                            from .authentication import SimpleUser
                            user = SimpleUser(
                                id=user_data[0],
                                username=user_data[1],
                                user_type=user_data[2],
                                email=user_data[3]
                            )
                            aqi_data = AQIViewSet()._get_aqi_data_response(user, default_city)
                            response_data['default_city_aqi'] = aqi_data
                    
                return Response(response_data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"登录错误: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AQIViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _get_supported_cities(self):
        """获取支持的城市列表"""
        try:
            # 先检查表是否存在
            with connection.cursor() as cursor:
                cursor.execute("""
                    SHOW TABLES LIKE 'aqi_result'
                """)
                if not cursor.fetchone():
                    # 表不存在，返回示例数据
                    return [
                        {'site': 'BEIJING', 'name': '北京'},
                        {'site': 'SHANGHAI', 'name': '上海'},
                        {'site': 'GUANGZHOU', 'name': '广州'},
                        {'site': 'SHENZHEN', 'name': '深圳'},
                        {'site': 'HANGZHOU', 'name': '杭州'},
                        {'site': 'NANJING', 'name': '南京'},
                        {'site': 'WUHAN', 'name': '武汉'},
                        {'site': 'CHENGDU', 'name': '成都'}
                    ]
                
                # 表存在，查询数据
                cursor.execute("""
                    SELECT DISTINCT SITE, NAME 
                    FROM aqi_result 
                    ORDER BY SITE
                """)
                cities = cursor.fetchall()
                if cities:
                    return [{'site': city[0], 'name': city[1]} for city in cities]
        except Exception as e:
            logger.error(f"获取城市列表出错: {e}")
        
        # 发生错误或没有数据时返回示例数据
        return [
            {'site': 'BEIJING', 'name': '北京'},
            {'site': 'SHANGHAI', 'name': '上海'},
            {'site': 'GUANGZHOU', 'name': '广州'},
            {'site': 'SHENZHEN', 'name': '深圳'},
            {'site': 'HANGZHOU', 'name': '杭州'},
            {'site': 'NANJING', 'name': '南京'},
            {'site': 'WUHAN', 'name': '武汉'},
            {'site': 'CHENGDU', 'name': '成都'}
        ]

    def _get_aqi_data(self, site=None):
        """从数据库获取AQI数据"""
        try:
            # 先检查表是否存在
            with connection.cursor() as cursor:
                cursor.execute("""
                    SHOW TABLES LIKE 'aqi_result'
                """)
                if not cursor.fetchone():
                    # 表不存在，直接使用模拟数据
                    logger.error("表不存在")
                    return self._generate_mock_aqi_data(site)
                
                # 表存在，查询数据
                if site:
                    cursor.execute("""
                        SELECT * FROM aqi_result 
                        WHERE SITE = %s 
                        ORDER BY DATE DESC 
                        LIMIT 1
                    """, [site])
                else:
                    cursor.execute("""
                        SELECT * FROM aqi_result 
                        ORDER BY DATE DESC 
                        LIMIT 1
                    """)
                columns = [col[0] for col in cursor.description]
                data = cursor.fetchone()
                
                if data:
                    return dict(zip(columns, data))
        except Exception as e:
            logger.error(f"获取AQI数据出错: {e}")
        
        # 发生错误或没有数据时使用模拟数据
        return self._generate_mock_aqi_data(site)

    def _generate_mock_aqi_data(self, site=None):
        """生成模拟AQI数据"""
        import datetime
        from django.utils import timezone
        
        if not site:
            site = 'BEIJING'
            station = 'Central Station'
            name = '北京'
        else:
            city_map = {city['site']: city['name'] for city in self._get_supported_cities()}
            name = city_map.get(site, site)
            station = f"{name} Central Station"
        
        aqi = random.randint(30, 300)
        
        if aqi <= 50:
            aqi_level = 1
        elif aqi <= 100:
            aqi_level = 2
        elif aqi <= 150:
            aqi_level = 3
        elif aqi <= 200:
            aqi_level = 4
        elif aqi <= 300:
            aqi_level = 5
        else:
            aqi_level = 6
        
        # 基础路径获取
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 图片路径
        image_path = os.path.join(base_dir, f'test_images/level{aqi_level}.jpg')
        
        hint_image = None
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                hint_image = base64.b64encode(f.read()).decode('utf-8')
        
        return {
            'id': random.randint(1, 1000),
            'SITE': site,
            'STATION': station,
            'DATE': timezone.now().date(),
            'NAME': name,
            'TEMP': random.uniform(15, 30),
            'DEWP': random.uniform(5, 15),
            'STP': random.uniform(900, 1050),
            'VISIB': random.uniform(5, 25),
            'WDSP': random.uniform(0, 15),
            'MXSPD': random.uniform(5, 30),
            'MAX': random.uniform(25, 35),
            'MIN': random.uniform(15, 25),
            'PRCP': random.uniform(0, 10),
            'MONTH': timezone.now().month,
            'AQI': aqi,
            'AQILEVEL': aqi_level,
            'HINTIMAGE': hint_image
        }

    def _get_aqi_data_response(self, user, site=None):
        """根据用户类型返回不同的AQI数据"""
        if isinstance(site, dict) and 'site' in site:
            site = site['site']
            
        aqi_data = self._get_aqi_data(site)
        
        if not aqi_data:
            return {'error': 'No AQI data available'}
            
        # 检查user.user_type
        if hasattr(user, 'user_type') and user.user_type == 'enterprise':
            return {
                'site': aqi_data['SITE'],
                'name': aqi_data['NAME'],
                'date': aqi_data['DATE'], 
                'aqi': aqi_data['AQI'],
                'aqi_level': aqi_data['AQILEVEL']
            }
        else:
            return {
                'site': aqi_data['SITE'],
                'date': aqi_data['DATE'],
                'name': aqi_data['NAME'],
                'aqi': aqi_data['AQI'],
                'aqi_level': aqi_data['AQILEVEL'],
                'hint_image': aqi_data['HINTIMAGE']
            }

    def list(self, request):
        """获取所有支持的城市和默认城市的AQI数据"""
        supported_cities = self._get_supported_cities()
        default_city = supported_cities[0] if supported_cities else None
        
        response_data = {
            'supported_cities': supported_cities
        }
        
        if default_city:
            aqi_data = self._get_aqi_data_response(request.user, default_city['site'])
            response_data['default_city_aqi'] = aqi_data
            
        return Response(response_data)

    @action(detail=False, methods=['get'])
    def by_site(self, request):
        """根据城市获取AQI数据"""
        site = request.query_params.get('site')
        if not site:
            return Response({'error': 'Site parameter is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        aqi_data = self._get_aqi_data_response(request.user, site)
        return Response(aqi_data)
        
    @action(detail=False, methods=['get'])
    def cities(self, request):
        """获取支持的城市列表"""
        supported_cities = self._get_supported_cities()
        return Response(supported_cities) 