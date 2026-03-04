"""
邮件通知模块 - 通过QQ邮箱SMTP发送买入信号通知
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from typing import List, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class EmailNotifier:
    """邮件通知类 - QQ邮箱SMTP"""
    
    def __init__(self, config: dict):
        """
        初始化邮件通知器
        
        Args:
            config: 邮件配置
                - smtp_server: SMTP服务器地址
                - smtp_port: SMTP端口
                - use_ssl: 是否使用SSL
                - sender: 发件人邮箱
                - password: 邮箱授权码
                - receivers: 收件人列表
        """
        self.smtp_server = config.get('smtp_server', 'smtp.qq.com')
        self.smtp_port = config.get('smtp_port', 465)
        self.use_ssl = config.get('use_ssl', True)
        self.sender = config.get('sender', '')
        self.password = config.get('password', '')
        self.receivers = config.get('receivers', [])
        
        self._last_send_time: Optional[datetime] = None
        self._cooldown = config.get('cooldown', 3600)  # 默认1小时冷却
        
        # 连接超时设置
        self._timeout = config.get('timeout', 30)
        # 发送失败重试次数
        self._retry_times = config.get('retry_times', 2)
    
    @contextmanager
    def _smtp_connection(self):
        """
        SMTP连接的上下文管理器，确保连接被正确关闭
        
        Yields:
            smtplib.SMTP or smtplib.SMTP_SSL 连接对象
        """
        server = None
        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(
                    self.smtp_server, 
                    self.smtp_port, 
                    timeout=self._timeout
                )
            else:
                server = smtplib.SMTP(
                    self.smtp_server, 
                    self.smtp_port, 
                    timeout=self._timeout
                )
                server.starttls()
            
            server.login(self.sender, self.password)
            yield server
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    try:
                        server.close()
                    except Exception:
                        pass
    
    def send_signal_notification(self, signal) -> bool:
        """
        发送买入信号通知邮件
        
        Args:
            signal: Signal对象
        
        Returns:
            是否发送成功
        """
        if not self._check_config():
            return False
        
        # 检查冷却时间
        if self._last_send_time:
            elapsed = (datetime.now() - self._last_send_time).total_seconds()
            if elapsed < self._cooldown:
                logger.info(f"邮件发送冷却中，还需等待{self._cooldown - elapsed:.0f}秒")
                return False
        
        # 获取强度等级描述
        strength_level = getattr(signal, 'strength_detail', None)
        level_desc = strength_level.level if strength_level else f"{signal.strength}级"
        total_score = strength_level.total_score if strength_level else signal.strength * 33
        
        subject = f"黄金买入信号提醒 - {level_desc}({total_score}分)"
        
        html_content = self._build_signal_html(signal)
        
        success = self._send_email(subject, html_content, is_html=True)
        
        if success:
            self._last_send_time = datetime.now()
            logger.info("买入信号通知邮件发送成功")
        
        return success
    
    def send_test_email(self) -> bool:
        """发送测试邮件"""
        if not self._check_config():
            return False
        
        subject = "黄金监控系统 - 测试邮件"
        content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>✅ 邮件配置测试成功</h2>
            <p>黄金价格监控系统邮件通知功能正常运行。</p>
            <p>发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </body>
        </html>
        """
        return self._send_email(subject, content, is_html=True)
    
    def _check_config(self) -> bool:
        """检查邮件配置是否完整"""
        if not self.sender or not self.password:
            logger.error("邮件配置不完整: 缺少发件人或授权码")
            return False
        if not self.receivers:
            logger.error("邮件配置不完整: 缺少收件人")
            return False
        return True
    
    def _build_signal_html(self, signal) -> str:
        """构建买入信号HTML邮件内容"""
        reasons_html = "".join([f"<li>{r}</li>" for r in signal.reasons])
        
        # 指标详情
        indicators = signal.indicators
        ma_val = f"{indicators.get('ma', 0):.2f}" if indicators.get('ma') else "N/A"
        rsi_val = f"{indicators.get('rsi', 0):.1f}" if indicators.get('rsi') else "N/A"
        dif_val = f"{indicators.get('macd_dif', 0):.4f}" if indicators.get('macd_dif') else "N/A"
        dea_val = f"{indicators.get('macd_dea', 0):.4f}" if indicators.get('macd_dea') else "N/A"
        
        # 获取详细强度信息
        strength_detail = getattr(signal, 'strength_detail', None)
        if strength_detail:
            total_score = strength_detail.total_score
            level = strength_detail.level
            ma_score = strength_detail.ma_score
            rsi_score = strength_detail.rsi_score
            macd_score = strength_detail.macd_score
            trend_score = strength_detail.trend_score
            position_score = strength_detail.position_score
            
            # 获取详细分析
            details = strength_detail.details
            ma_details = details.get('ma', {})
            rsi_details = details.get('rsi', {})
            macd_details = details.get('macd', {})
            trend_details = details.get('trend', {})
            position_details = details.get('position', {})
        else:
            total_score = signal.strength * 33
            level = ['极弱', '弱', '中等', '强', '极强'][min(signal.strength, 4)]
            ma_score = rsi_score = macd_score = trend_score = position_score = 0
            ma_details = rsi_details = macd_details = trend_details = position_details = {}
        
        # 根据强度等级选择颜色
        level_colors = {
            '极强': '#4CAF50',
            '强': '#8BC34A', 
            '中等': '#FFC107',
            '弱': '#FF9800',
            '极弱': '#f44336'
        }
        level_color = level_colors.get(level, '#FFC107')
        
        # 构建强度评分条
        def score_bar(score, label):
            width = max(5, score)
            color = '#4CAF50' if score >= 60 else '#FFC107' if score >= 40 else '#f44336'
            return f'''
            <div style="margin: 8px 0;">
                <div style="display: flex; justify-content: space-between; font-size: 12px; color: #666;">
                    <span>{label}</span>
                    <span>{score}/100</span>
                </div>
                <div style="background: #e0e0e0; border-radius: 4px; height: 8px; overflow: hidden;">
                    <div style="background: {color}; width: {width}%; height: 100%;"></div>
                </div>
            </div>
            '''
        
        strength_bars = f'''
        {score_bar(ma_score, 'MA均线')}
        {score_bar(rsi_score, 'RSI指标')}
        {score_bar(macd_score, 'MACD指标')}
        {score_bar(trend_score, '趋势确认')}
        {score_bar(position_score, '价格位置')}
        '''
        
        # 构建详细分析内容
        analysis_items = []
        if ma_details.get('golden_cross'):
            analysis_items.append(f"MA: {ma_details.get('golden_cross')}")
        if ma_details.get('alignment'):
            analysis_items.append(f"均线排列: {ma_details.get('alignment')}")
        if rsi_details.get('oversold_level'):
            analysis_items.append(f"RSI状态: {rsi_details.get('oversold_level')}")
        if rsi_details.get('momentum'):
            analysis_items.append(f"RSI动能: {rsi_details.get('momentum')}")
        if rsi_details.get('divergence'):
            analysis_items.append(f"RSI背离: {rsi_details.get('divergence')}")
        if macd_details.get('cross_type'):
            analysis_items.append(f"MACD: {macd_details.get('cross_type')}")
        if macd_details.get('histogram_trend'):
            analysis_items.append(f"柱状图: {macd_details.get('histogram_trend')}")
        if trend_details.get('trend'):
            analysis_items.append(f"趋势: {trend_details.get('trend')}")
        if position_details.get('position'):
            analysis_items.append(f"位置: {position_details.get('position')}")
        if position_details.get('breakthrough'):
            analysis_items.append(f"突破: {position_details.get('breakthrough')}")
        
        analysis_html = "".join([f"<li>{item}</li>" for item in analysis_items])
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #FFD700, #FFA500); color: white; padding: 20px; border-radius: 10px 10px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ padding: 20px; }}
                .price-box {{ background: #fff8e1; border-left: 4px solid #FFD700; padding: 15px; margin: 15px 0; }}
                .price {{ font-size: 32px; color: #FF6B00; font-weight: bold; }}
                .signal-strength {{ display: inline-block; padding: 8px 20px; background: {level_color}; color: white; border-radius: 20px; font-weight: bold; }}
                .score-box {{ background: #f0f0f0; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                .total-score {{ font-size: 36px; font-weight: bold; color: {level_color}; text-align: center; }}
                .reasons {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .reasons ul {{ margin: 0; padding-left: 20px; }}
                .reasons li {{ margin: 8px 0; color: #333; }}
                .indicators {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 15px 0; }}
                .indicator {{ background: #f0f0f0; padding: 10px; border-radius: 5px; text-align: center; }}
                .indicator-label {{ font-size: 12px; color: #666; }}
                .indicator-value {{ font-size: 18px; font-weight: bold; color: #333; }}
                .analysis {{ background: #e8f5e9; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .analysis ul {{ margin: 0; padding-left: 20px; font-size: 13px; }}
                .analysis li {{ margin: 5px 0; color: #2e7d32; }}
                .footer {{ text-align: center; padding: 15px; color: #999; font-size: 12px; border-top: 1px solid #eee; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>黄金买入信号</h1>
                </div>
                <div class="content">
                    <div class="price-box">
                        <div>当前价格</div>
                        <div class="price">{signal.price:.2f}</div>
                        <div>元/克 (Au9999)</div>
                    </div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <span class="signal-strength">{level} ({signal.strength}/5)</span>
                    </div>
                    
                    <div class="score-box">
                        <div style="text-align: center; font-size: 14px; color: #666; margin-bottom: 5px;">综合强度评分</div>
                        <div class="total-score">{total_score}/100</div>
                        <div style="margin-top: 15px;">
                            {strength_bars}
                        </div>
                    </div>
                    
                    <div class="reasons">
                        <strong>触发原因:</strong>
                        <ul>{reasons_html}</ul>
                    </div>
                    
                    <div class="analysis">
                        <strong>详细分析:</strong>
                        <ul>{analysis_html}</ul>
                    </div>
                    
                    <div class="indicators">
                        <div class="indicator">
                            <div class="indicator-label">MA20均线</div>
                            <div class="indicator-value">{ma_val}</div>
                        </div>
                        <div class="indicator">
                            <div class="indicator-label">RSI指标</div>
                            <div class="indicator-value">{rsi_val}</div>
                        </div>
                        <div class="indicator">
                            <div class="indicator-label">MACD DIF</div>
                            <div class="indicator-value">{dif_val}</div>
                        </div>
                        <div class="indicator">
                            <div class="indicator-label">MACD DEA</div>
                            <div class="indicator-value">{dea_val}</div>
                        </div>
                    </div>
                    
                    <p style="color: #ff9800; font-size: 14px;">
                        * 此信号仅供参考，投资有风险，决策需谨慎。
                    </p>
                </div>
                <div class="footer">
                    <p>信号生成时间: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>黄金价格监控系统</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def _send_email(self, subject: str, content: str, is_html: bool = False) -> bool:
        """
        发送邮件
        
        Args:
            subject: 邮件主题
            content: 邮件内容
            is_html: 是否为HTML格式
        
        Returns:
            是否发送成功
        """
        last_error = None
        
        for attempt in range(self._retry_times):
            try:
                msg = MIMEMultipart()
                msg['From'] = self.sender
                msg['To'] = ', '.join(self.receivers)
                msg['Subject'] = Header(subject, 'utf-8')
                
                content_type = 'html' if is_html else 'plain'
                msg.attach(MIMEText(content, content_type, 'utf-8'))
                
                # 使用上下文管理器确保连接被正确关闭
                with self._smtp_connection() as server:
                    server.sendmail(self.sender, self.receivers, msg.as_string())
                
                logger.info(f"邮件发送成功: {subject}")
                return True
                
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"邮箱认证失败，请检查授权码: {e}")
                return False  # 认证错误不重试
            except smtplib.SMTPException as e:
                logger.error(f"SMTP错误 (尝试 {attempt + 1}/{self._retry_times}): {e}")
                last_error = e
            except (TimeoutError, ConnectionError) as e:
                logger.error(f"连接错误 (尝试 {attempt + 1}/{self._retry_times}): {e}")
                last_error = e
            except Exception as e:
                logger.error(f"邮件发送失败 (尝试 {attempt + 1}/{self._retry_times}): {e}")
                last_error = e
        
        if last_error:
            logger.error(f"邮件发送最终失败: {last_error}")
        return False
    
    def cleanup(self):
        """清理资源（预留接口，当前无需清理）"""
        pass


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    from dataclasses import dataclass
    from datetime import datetime
    
    @dataclass
    class MockSignal:
        timestamp: datetime
        signal_type: str
        strength: int
        price: float
        reasons: list
        indicators: dict
    
    config = {
        'smtp_server': 'smtp.qq.com',
        'smtp_port': 465,
        'use_ssl': True,
        'sender': 'your_qq@qq.com',
        'password': 'your_auth_code',
        'receivers': ['target@qq.com']
    }
    
    notifier = EmailNotifier(config)
    
    # 模拟信号
    mock_signal = MockSignal(
        timestamp=datetime.now(),
        signal_type='BUY',
        strength=2,
        price=2045.50,
        reasons=['[MA] 价格上穿MA20', '[RSI] RSI处于超卖区域'],
        indicators={'ma': 2040.00, 'rsi': 28.5, 'macd_dif': 1.5, 'macd_dea': 1.2}
    )
    
    print("邮件配置检查:", notifier._check_config())
    # notifier.send_signal_notification(mock_signal)  # 实际发送需配置正确邮箱
