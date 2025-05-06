import pandas as pd
import mysql.connector
from datetime import datetime
import os

# 数据库配置
db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'aqi_service'
}

def import_gsod_data():
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 读取resources目录下的所有CSV文件
        resources_dir = 'resources'
        for filename in os.listdir(resources_dir):
            if filename.endswith('.csv'):
                print(f"Processing file: {filename}")
                file_path = os.path.join(resources_dir, filename)
                
                # 读取CSV文件
                df = pd.read_csv(file_path)
                
                # 准备插入语句
                insert_query = """
                    INSERT INTO gsod_data 
                    (SITE, STATION, DATE, NAME, TEMP, DEWP, STP, VISIB, WDSP, 
                     MXSPD, MAX, MIN, PRCP, MONTH)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                # 遍历DataFrame并插入数据
                for _, row in df.iterrows():
                    # 直接使用日期字符串，因为MySQL会自动转换YYYY-MM-DD格式
                    date = datetime.strptime(str(row['DATE']), '%Y-%m-%d').date()
                    
                    data = (
                        row['SITE'],
                        row['STATION'],
                        date,
                        row['NAME'],
                        float(row['TEMP']),
                        float(row['DEWP']),
                        float(row['STP']),
                        float(row['VISIB']),
                        float(row['WDSP']),
                        float(row['MXSPD']),
                        float(row['MAX']),
                        float(row['MIN']),
                        float(row['PRCP']),
                        int(date.month)
                    )
                    
                    cursor.execute(insert_query, data)
                
                # 提交每个文件的更改
                conn.commit()
                print(f"Successfully imported data from {filename}")
        
        print("All data imported successfully!")
        
    except Exception as e:
        print(f"Error importing data: {str(e)}")
        if conn.is_connected():
            conn.rollback()
    
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    import_gsod_data() 