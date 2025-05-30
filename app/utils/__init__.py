# 时区工具
from datetime import datetime, timezone, timedelta

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ)

def get_beijing_timezone():
    """获取北京时区对象"""
    return BEIJING_TZ 