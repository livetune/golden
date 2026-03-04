"""
黄金价格监控系统 - 主入口
实时获取黄金价格，通过技术指标分析生成买入信号，并通过邮件通知
"""
import os
import sys
import yaml
import logging
import gc
import atexit
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from src.scheduler import Scheduler


def setup_logging(config: dict):
    """配置日志系统"""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    log_file = log_config.get('file', 'logs/app.log')
    max_bytes = log_config.get('max_bytes', 10 * 1024 * 1024)  # 10MB
    backup_count = log_config.get('backup_count', 5)
    
    # 确保日志目录存在
    log_path = ROOT_DIR / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除已有处理器，避免重复
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)
    
    # 文件处理器
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置文件，支持环境变量覆盖敏感信息"""
    config_path = ROOT_DIR / 'config' / 'config.yaml'
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    else:
        # 无配置文件时使用默认配置（适用于 Docker/云平台部署）
        config = {
            'api': {'source': '上金所Au9999', 'interval': 40, 'timeout': 10, 'retry_times': 3, 'max_history': 500},
            'algorithm': {'threshold': 5, 'cooldown': 600},
            'memory': {'gc_interval': 60, 'max_task_errors': 10},
            'email': {'smtp_server': 'smtp.qq.com', 'smtp_port': 465, 'use_ssl': True, 'timeout': 30, 'retry_times': 2},
            'logging': {'level': 'INFO', 'file': 'logs/app.log', 'max_bytes': 10485760, 'backup_count': 5},
        }
    
    # 环境变量覆盖邮件配置（优先级高于配置文件）
    email_cfg = config.setdefault('email', {})
    if os.environ.get('EMAIL_SENDER'):
        email_cfg['sender'] = os.environ['EMAIL_SENDER']
    if os.environ.get('EMAIL_PASSWORD'):
        email_cfg['password'] = os.environ['EMAIL_PASSWORD']
    if os.environ.get('EMAIL_RECEIVERS'):
        email_cfg['receivers'] = [r.strip() for r in os.environ['EMAIL_RECEIVERS'].split(',')]
    
    return config


def validate_config(config: dict, logger) -> bool:
    """验证配置完整性"""
    errors = []
    
    # 验证邮件配置
    email_config = config.get('email', {})
    if not email_config.get('sender') or email_config.get('sender') == 'your_qq@qq.com':
        errors.append("请配置发件人邮箱 (email.sender)")
    if not email_config.get('password') or email_config.get('password') == 'your_auth_code':
        errors.append("请配置邮箱授权码 (email.password)")
    if not email_config.get('receivers'):
        errors.append("请配置收件人邮箱列表 (email.receivers)")
    
    if errors:
        logger.warning("配置验证警告:")
        for err in errors:
            logger.warning(f"  - {err}")
        logger.warning("邮件通知功能可能无法正常工作，但程序仍会运行")
    
    return True


def setup_memory_optimization():
    """配置内存优化策略"""
    # 启用垃圾回收
    gc.enable()
    
    # 设置垃圾回收阈值，更积极地回收内存
    # 默认是 (700, 10, 10)，降低阈值使回收更频繁
    gc.set_threshold(500, 10, 5)


def cleanup_on_exit():
    """程序退出时的清理函数"""
    logger = logging.getLogger(__name__)
    logger.info("执行退出清理...")
    gc.collect()


def main():
    """主函数"""
    # 配置内存优化
    setup_memory_optimization()
    
    # 注册退出清理
    atexit.register(cleanup_on_exit)
    
    # 加载配置
    config = load_config()
    
    # 配置日志
    logger = setup_logging(config)
    
    # 验证配置
    validate_config(config, logger)
    
    # 显示启动信息
    api_config = config.get('api', {})
    algo_config = config.get('algorithm', {})
    
    logger.info(f"系统启动 | Au9999 | 间隔:{api_config.get('interval', 60)}s | 波动阈值:{algo_config.get('threshold', 5)}元/克")
    
    # 创建并启动调度器，使用上下文管理器确保资源清理
    scheduler = None
    try:
        scheduler = Scheduler(config)
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("用户中断，系统退出")
    except MemoryError:
        logger.error("内存不足，系统退出")
        if scheduler:
            scheduler.stop()
        gc.collect()
        sys.exit(1)
    except Exception as e:
        logger.error(f"系统异常退出: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # 确保调度器被正确停止和清理
        if scheduler:
            try:
                scheduler.stop()
            except Exception:
                pass
        # 最终垃圾回收
        gc.collect()


if __name__ == "__main__":
    main()
