import unittest
import pandas as pd
from autogluon.tabular import TabularPredictor
import logging
import pymysql
from dotenv import load_dotenv
import os
import base64
from io import BytesIO
from PIL import Image

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

class TestTrainingLogic(unittest.TestCase):
    def setUp(self):
        """测试前的准备工作"""
        self.label = 'AQI'
        self.problem_type = 'regression'
        self.output_dir = 'autogluon_aqi_predictor'
        
        # 数据库连接配置
        self.db_config = {
            'host': os.getenv('DB_HOST', '127.0.0.1'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'aqi_service'),
            'port': int(os.getenv('DB_PORT', 3306))
        }
        
    def test_full_prediction_flow(self):
        """测试完整的AQI预测和保存流程"""
        try:
            # 连接数据库
            connection = pymysql.connect(**self.db_config)
            
            # 从数据库获取一条GSOD数据
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM gsod_data 
                    LIMIT 1
                """)
                columns = [col[0] for col in cursor.description]
                data = cursor.fetchall()
                
                if not data:
                    self.fail("No GSOD data available for testing")
                
                # 转换为DataFrame
                df = pd.DataFrame(data, columns=columns)
                
                # 验证所有列都存在（除了id）
                expected_columns = ['DATE', 'NAME', 'SITE', 'STATION', 
                                  'TEMP', 'DEWP', 'STP', 'VISIB', 'WDSP', 
                                  'MXSPD', 'MAX', 'MIN', 'PRCP', 'MONTH']
                for col in expected_columns:
                    self.assertIn(col, df.columns, f"{col}应该在DataFrame中")
                
                # 应用特征选择逻辑 - 只排除id列
                feature_cols = [col for col in df.columns if col != 'id']
                X = df[feature_cols]
                
                # 打印特征信息用于调试
                logger.info(f"原始列: {df.columns.tolist()}")
                logger.info(f"选择的特征列: {feature_cols}")
                logger.info(f"数据形状: {X.shape}")
                
                # 验证特征选择是否正确
                self.assertEqual(len(feature_cols), len(df.columns) - 1, "应该只排除了id列")
                
                # 验证是否包含所有必要列
                for col in expected_columns:
                    self.assertIn(col, feature_cols, f"{col}应该在特征列中")
                
                # 验证数据是否有效
                self.assertFalse(X.isnull().all().any(), "不应该存在全为空值的列")
                
                # 打印数据样本用于调试
                logger.info(f"数据样本:\n{X.head()}")
                
                # 加载模型并进行预测
                try:
                    predictor = TabularPredictor.load(self.output_dir)
                    predictions = predictor.predict(X)
                    
                    # 验证预测结果
                    self.assertIsNotNone(predictions, "预测结果不应为空")
                    self.assertEqual(len(predictions), len(X), "预测结果数量应与输入数据数量相同")
                    
                    # 打印预测结果
                    logger.info(f"预测结果: {predictions}")
                    
                    # 验证预测值是否在合理范围内
                    for pred in predictions:
                        self.assertGreaterEqual(pred, 0, "AQI预测值不应小于0")
                        self.assertLessEqual(pred, 500, "AQI预测值不应大于500")
                        
                    # 获取AQI等级
                    aqi_level = self.get_aqi_level(predictions.iloc[0])
                    logger.info(f"AQI等级: {aqi_level}")
                    
                    # 生成健康提示图片
                    hint_image = self.generate_hint_image(aqi_level)
                    self.assertIsNotNone(hint_image, "健康提示图片不应为空")
                    
                    # 将预测结果保存到数据库
                    row = df.iloc[0]
                    cursor.execute("""
                        INSERT INTO aqi_result 
                        (SITE, STATION, DATE, NAME, TEMP, DEWP, STP, VISIB, WDSP, 
                         MXSPD, MAX, MIN, PRCP, MONTH, AQI, AQILEVEL, HINTIMAGE)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row['SITE'], row['STATION'], row['DATE'], row['NAME'],
                        row['TEMP'], row['DEWP'], row['STP'], row['VISIB'],
                        row['WDSP'], row['MXSPD'], row['MAX'], row['MIN'],
                        row['PRCP'], row['MONTH'], predictions.iloc[0], aqi_level, hint_image
                    ))
                    
                    # 验证数据是否成功插入
                    cursor.execute("""
                        SELECT COUNT(*) FROM aqi_result 
                        WHERE SITE = %s AND DATE = %s
                    """, (row['SITE'], row['DATE']))
                    count = cursor.fetchone()[0]
                    self.assertEqual(count, 1, "预测结果应该成功插入到数据库")
                    
                    connection.commit()
                    logger.info("预测结果成功保存到数据库")
                        
                except Exception as e:
                    logger.error(f"预测过程中发生错误: {str(e)}")
                    self.fail(f"预测失败: {str(e)}")
                
        except Exception as e:
            logger.error(f"测试过程中发生错误: {str(e)}")
            self.fail(f"测试失败: {str(e)}")
        finally:
            if 'connection' in locals():
                connection.close()
                
    def get_aqi_level(self, aqi_value):
        """根据EPA标准确定AQI等级"""
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
            
    def generate_hint_image(self, aqi_level):
        """生成健康提示图片（测试用简化版本）"""
        # 创建一个简单的测试图片
        image = Image.new('RGB', (1024, 1024), color='white')
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
            
    def tearDown(self):
        """测试后的清理工作"""
        pass

if __name__ == '__main__':
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)
    # 运行测试
    unittest.main() 