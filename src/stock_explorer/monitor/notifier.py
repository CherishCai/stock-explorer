"""告警通知模块 - 多渠道告警"""

import base64
import hashlib
import hmac
import json
import time
import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import requests
from rich.console import Console
from rich.table import Table

from stock_explorer.logging.logger import get_logger
from stock_explorer.signal.base import Signal

logger = get_logger(__name__)


class AlertChannelBase(ABC):
    """告警通道基类"""

    @abstractmethod
    def send(self, message: str, signal: Signal) -> bool:
        """发送告警消息"""
        pass

    @abstractmethod
    def format_message(self, signal: Signal) -> str:
        """格式化告警消息"""
        pass


class ConsoleNotifier(AlertChannelBase):
    """控制台告警"""

    def format_message(self, signal: Signal) -> str:
        table = Table(show_header=True)
        table.add_column("时间", style="cyan")
        table.add_column("方向", style="green" if signal.direction.value == "buy" else "red")
        table.add_column("股票", style="yellow")
        table.add_column("信号")
        table.add_column("强度")

        table.add_row(
            signal.timestamp.strftime("%H:%M:%S"),
            signal.direction.value.upper(),
            f"{signal.symbol} {signal.name}",
            signal.signal_type.value,
            signal.strength.value,
        )

        console = Console()
        console.print(table)
        return ""

    def send(self, message: str, signal: Signal) -> bool:
        # format_message 已经在 NotifierManager.notify() 中调用过了，这里不需要重复打印
        return True


class FileNotifier(AlertChannelBase):
    """文件日志告警"""

    def __init__(self, log_path: str = "logs/signals.log"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def format_message(self, signal: Signal) -> str:
        return (
            f"[{signal.timestamp.isoformat()}] "
            f"{signal.direction.value.upper()} - {signal.symbol} {signal.name} | "
            f"{signal.signal_type.value} | {signal.strength.value} | {signal.message}"
        )

    def send(self, message: str, signal: Signal) -> bool:
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(self.format_message(signal) + "\n")
            return True
        except Exception as e:
            logger.error(f"File write failed: {e}")
            return False


class EmailNotifier(AlertChannelBase):
    """邮件告警"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_addr: str,
        to_addrs: list[str],
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    def format_message(self, signal: Signal) -> str:
        return f"""
        <html>
        <body>
            <h2>股票信号告警</h2>
            <table>
                <tr><td><b>股票:</b></td><td>{signal.symbol} {signal.name}</td></tr>
                <tr><td><b>信号:</b></td><td>{signal.signal_type.value}</td></tr>
                <tr><td><b>方向:</b></td><td>{signal.direction.value.upper()}</td></tr>
                <tr><td><b>强度:</b></td><td>{signal.strength.value}</td></tr>
                <tr><td><b>价格:</b></td><td>{signal.price}</td></tr>
                <tr><td><b>时间:</b></td><td>{signal.timestamp}</td></tr>
                <tr><td><b>消息:</b></td><td>{signal.message}</td></tr>
            </table>
        </body>
        </html>
        """

    def send(self, message: str, signal: Signal) -> bool:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[股票信号] {signal.direction.value.upper()} - {signal.symbol}"
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)

            html = self.format_message(signal)
            msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())

            logger.info(f"Email sent successfully for {signal.symbol}")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False


class DingTalkNotifier(AlertChannelBase):
    """钉钉告警"""

    def __init__(self, webhook_url: str, secret: str = ""):
        self.webhook_url = webhook_url
        self.secret = secret

    def format_message(self, signal: Signal) -> str:
        emoji = "🔔" if signal.direction.value == "buy" else "🔕"

        text = f"""### {emoji} {signal.direction.value.upper()}信号

> 股票: **{signal.symbol} {signal.name}**
> 信号: {signal.signal_type.value}
> 强度: {signal.strength.value}
> 价格: {signal.price}
> 时间: {signal.timestamp}
> 消息: {signal.message}
"""
        payload = {"msgtype": "markdown", "markdown": {"title": "股票信号告警", "text": text}}
        return json.dumps(payload)

    def send(self, message: str, signal: Signal) -> bool:
        try:
            url = self.webhook_url

            if self.secret:
                timestamp = str(round(time.time() * 1000))
                secret_enc = self.secret.encode("utf-8")
                string_to_sign = f"{timestamp}\n{self.secret}"
                string_to_sign_enc = string_to_sign.encode("utf-8")
                hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
                url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

            payload = self.format_message(signal)
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, data=payload.encode("utf-8"), headers=headers)
            result = response.json()

            if result.get("errcode") == 0:
                logger.info(f"DingTalk message sent for {signal.symbol}")
                return True
            else:
                logger.error(f"DingTalk send failed: {result}")
                return False
        except Exception as e:
            logger.error(f"DingTalk send failed: {e}")
            return False


class NotifierManager:
    """告警管理器"""

    def __init__(self):
        self.channels: dict[str, AlertChannelBase] = {}
        self.alert_history: dict[str, datetime] = {}
        self.rate_limit_seconds: int = 60
        self.console = Console()

    def register(self, name: str, channel: AlertChannelBase):
        """注册告警通道"""
        self.channels[name] = channel
        logger.info(f"Registered alert channel: {name}")

    def notify(self, signal: Signal, channels: list[str] | None = None):
        """发送告警"""
        if not self._check_rate_limit(signal):
            logger.debug(f"Rate limit triggered for {signal.symbol}")
            return

        if channels is None:
            channels = list(self.channels.keys())

        for channel_name in channels:
            if channel_name in self.channels:
                channel = self.channels[channel_name]
                message = channel.format_message(signal)
                success = channel.send(message, signal)

                if success:
                    logger.info(f"Alert sent via {channel_name} for {signal.symbol}")
                else:
                    logger.warning(f"Alert failed via {channel_name} for {signal.symbol}")

    def _check_rate_limit(self, signal: Signal) -> bool:
        """检查频率限制"""
        key = f"{signal.symbol}:{signal.signal_type.value}"
        now = datetime.now()

        if key in self.alert_history:
            last_alert = self.alert_history[key]
            if (now - last_alert).seconds < self.rate_limit_seconds:
                return False

        self.alert_history[key] = now
        return True

    def set_rate_limit(self, seconds: int):
        """设置频率限制"""
        self.rate_limit_seconds = seconds


def create_notifier_manager(config: dict) -> NotifierManager:
    """根据配置创建告警管理器"""
    manager = NotifierManager()

    logger.info(f"Alert config: {config}")

    if config.get("console", True):
        manager.register("console", ConsoleNotifier())

    if config.get("file", False):
        log_path = config.get("file_path", "logs/signals.log")
        logger.info(f"Creating FileNotifier with log_path: {log_path}")
        manager.register("file", FileNotifier(log_path))

    email_config = config.get("email", {})
    if email_config.get("enabled", False):
        manager.register(
            "email",
            EmailNotifier(
                smtp_host=email_config.get("smtp_host", ""),
                smtp_port=email_config.get("smtp_port", 465),
                smtp_user=email_config.get("smtp_user", ""),
                smtp_password=email_config.get("smtp_password", ""),
                from_addr=email_config.get("from_addr", ""),
                to_addrs=email_config.get("to_addrs", []),
            ),
        )

    dingtalk_config = config.get("dingtalk", {})
    if dingtalk_config.get("enabled", False):
        manager.register(
            "dingtalk",
            DingTalkNotifier(
                webhook_url=dingtalk_config.get("webhook_url", ""),
                secret=dingtalk_config.get("secret", ""),
            ),
        )

    rate_limit = config.get("rate_limit_seconds", 60)
    manager.set_rate_limit(rate_limit)

    return manager
