from django.db import connection
import pandas as pd
from autogluon.tabular import TabularPredictor
from datetime import datetime
import base64
from io import BytesIO
from PIL import Image
import requests
import logging
import replicate
import os

logger = logging.getLogger(__name__)

# AQI等级对应的提示词
AQI_PROMPTS = {
    1: "A beautiful cityscape with clear blue sky, people enjoying outdoor activities, green parks and trees, modern buildings, bright sunlight, high quality, detailed, reflecting urban life and environmental harmony",
    2: "A city view with slightly hazy sky, people going about their daily activities, some wearing light masks, urban landscape with moderate air quality, buildings visible but with slight haze, high quality, detailed",
    3: "An urban scene with orange-tinted sky, sensitive groups wearing masks, reduced outdoor activities, city landmarks visible but with noticeable haze, people being cautious, high quality, detailed",
    4: "A city under red-tinted sky, most people wearing masks, limited outdoor activities, prominent city buildings with heavy haze, emergency alerts visible, high quality, detailed",
    5: "A cityscape with purple-tinted sky, empty streets, emergency vehicles visible, severe air pollution, city landmarks barely visible through thick haze, high quality, detailed",
    6: "A city in emergency conditions with maroon sky, deserted streets, emergency services active, extremely poor visibility, city almost invisible through dense pollution, high quality, detailed"
}

# AQI等级对应的健康建议
AQI_ADVICE = {
    1: "Air quality is excellent. Perfect day for outdoor activities. Enjoy the fresh air and sunshine. Stay active and healthy.",
    2: "Air quality is acceptable. Most people can enjoy outdoor activities. Sensitive individuals should consider limiting prolonged outdoor exertion.",
    3: "Sensitive groups should reduce outdoor activities. Consider wearing masks. General public should monitor their health when outdoors.",
    4: "Everyone should reduce outdoor activities. Wear masks when going outside. Sensitive groups should stay indoors as much as possible.",
    5: "Health alert! Everyone should avoid outdoor activities. Stay indoors with windows closed. Use air purifiers if available.",
    6: "Emergency conditions! Stay indoors with windows closed. Use air purifiers. Only go outside if absolutely necessary with proper protection."
}

def get_aqi_level(aqi_value):
    """根据EPA标准确定AQI等级
    
    Args:
        aqi_value: AQI值
        
    Returns:
        int: AQI等级
            1: 优 (0-50)
            2: 良 (51-100)
            3: 轻度污染 (101-150)
            4: 中度污染 (151-200)
            5: 重度污染 (201-300)
            6: 严重污染 (301-500)
    """
    if aqi_value <= 50:
        return 1  # 优
    elif aqi_value <= 100:
        return 2  # 良
    elif aqi_value <= 150:
        return 3  # 轻度污染
    elif aqi_value <= 200:
        return 4  # 中度污染
    elif aqi_value <= 300:
        return 5  # 重度污染
    else:
        return 6  # 严重污染

def predict_aqi():
    """从GSOD数据预测AQI"""
    try:
        # 从数据库获取所有未处理的GSOD数据
        with connection.cursor() as cursor:
            # 首先检查未处理数据总量
            cursor.execute("""
                SELECT COUNT(*) FROM gsod_data 
                WHERE (HANDLED = 0 OR HANDLED IS NULL)
            """)
            total_unhandled = cursor.fetchone()[0]
            logger.info(f"总共有 {total_unhandled} 条未处理的数据")
            
            if total_unhandled == 0:
                logger.warning("没有未处理的GSOD数据可用于预测")
                return
            
            # 获取所有未处理的数据，每次处理最多1000条
            cursor.execute("""
                SELECT * FROM gsod_data 
                WHERE (HANDLED = 0 OR HANDLED IS NULL)
                LIMIT 1000
            """)
            columns = [col[0] for col in cursor.description]
            data = cursor.fetchall()
            
            if not data:
                logger.warning("No unhandled GSOD data available for prediction")
                return
            
            logger.info(f"本次将处理 {len(data)} 条数据")
            
            # 转换为DataFrame
            df = pd.DataFrame(data, columns=columns)
            
            # 输出数据日期分布情况
            date_counts = df['DATE'].value_counts().to_dict()
            logger.info(f"数据日期分布: {date_counts}")
            
            # 加载AutoGluon模型
            predictor = TabularPredictor.load('autogluon_aqi_predictor')
            
            # 准备预测数据 - 只排除id列和HANDLED列
            feature_cols = [col for col in df.columns if col != 'id' and col != 'HANDLED']
            X = df[feature_cols]
            
            # 进行预测
            predictions = predictor.predict(X)
            
            # 将预测结果存入数据库
            processed_count = 0
            for idx, row in df.iterrows():
                try:
                    aqi = predictions.iloc[idx]
                    aqi_level = get_aqi_level(aqi)
                    
                    # 生成健康提示图片
                    hint_image = generate_hint_image(aqi_level)
                    
                    # 插入预测结果到aqi_result表
                    cursor.execute("""
                        INSERT INTO aqi_result 
                        (SITE, STATION, DATE, NAME, TEMP, DEWP, STP, VISIB, WDSP, 
                         MXSPD, MAX, MIN, PRCP, MONTH, AQI, AQILEVEL, HINTIMAGE)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row['SITE'], row['STATION'], row['DATE'], row['NAME'],
                        row['TEMP'], row['DEWP'], row['STP'], row['VISIB'],
                        row['WDSP'], row['MXSPD'], row['MAX'], row['MIN'],
                        row['PRCP'], row['MONTH'], aqi, aqi_level, hint_image
                    ))
                    
                    # 将处理过的数据标记为已处理
                    cursor.execute("""
                        UPDATE gsod_data
                        SET HANDLED = 1
                        WHERE id = %s
                    """, (row['id'],))
                    
                    processed_count += 1
                    logger.info(f"成功插入预测结果: SITE={row['SITE']}, DATE={row['DATE']}, AQI={aqi}, AQILEVEL={aqi_level}")
                    
                    # 每50条数据提交一次事务，避免事务过大
                    if processed_count % 50 == 0:
                        connection.commit()
                        logger.info(f"已提交 {processed_count} 条数据")
                        
                except Exception as e:
                    logger.error(f"处理数据时出错 (ID={row['id']}): {str(e)}")
                    # 单条数据处理失败不影响整体流程，继续处理下一条
            
            # 最后提交剩余事务
            connection.commit()
            logger.info(f"AQI预测和结果存储完成，共处理 {processed_count} 条数据")
            
    except Exception as e:
        logger.error(f"AQI预测或结果存储过程中发生错误: {str(e)}")
        try:
            connection.rollback()
        except:
            pass  # 即使rollback失败也继续执行

def generate_hint_image(aqi_level, city_name="Beijing", city_features="modern skyscrapers, traditional hutongs, Forbidden City, Great Wall"):
    """使用Replicate的Stable Diffusion API生成健康提示图片
    
    Args:
        aqi_level: AQI等级
        city_name: 城市名称
        city_features: 城市特征描述
    """
    try:
        # 设置Replicate API key TODO
        #r8_FbDI0q1SKimFK1KnYkxnMtt
        os.environ["REPLICATE_API_TOKEN"] = "your api key"
        
        # 构建提示词，包含城市特征、AQI信息和健康建议
        prompt = f"A {city_name} cityscape with {city_features}, {AQI_PROMPTS[aqi_level]}, {AQI_ADVICE[aqi_level]}, include AQI level indicator and health tips in the image, showing the unique characteristics of {city_name}"
        
        # 调用Stable Diffusion模型
        output = replicate.run(
            # 实际运行使用自己的API key TODO 
            "stability-ai/stable-diffusion:your-api-key",
            input={
                "prompt": prompt,
                "width": 1024,
                "height": 1024,
                "num_outputs": 1,
                "num_inference_steps": 75,
                "guidance_scale": 8.5
            }
        )
        
        # 下载生成的图片
        image_url = output[0]
        response = requests.get(image_url)
        
        # 转换为base64
        return base64.b64encode(response.content).decode('utf-8')
        
    except Exception as e:
        logger.error(f"Error generating hint image: {str(e)}")
        # 发生错误时返回一个默认图片
        image = Image.new('RGB', (1024, 1024), color='white')
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8') 