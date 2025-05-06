from django.core.management.base import BaseCommand
from aqi_app.tasks import predict_aqi
import schedule
import time
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Run AQI prediction task periodically'

    def handle(self, *args, **options):
        logger.info("Starting AQI prediction scheduler")
        
        # 立即执行一次预测任务
        self.stdout.write("执行立即预测...")
        predict_aqi()
        self.stdout.write("立即预测完成")
        
        # 每天凌晨1点运行预测任务
        schedule.every().day.at("01:00").do(predict_aqi)
        
        # 开发测试用：每10分钟执行一次
        schedule.every(10).minutes.do(predict_aqi)
        
        self.stdout.write("已设置定时任务: 每天凌晨1点和每10分钟执行一次")
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"Error in scheduler: {str(e)}")
                self.stderr.write(f"定时任务出错: {str(e)}")
                time.sleep(300)  # 发生错误时等待5分钟再继续 