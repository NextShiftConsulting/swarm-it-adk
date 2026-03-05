"""
Notification Plugins - Phase 6 Extensibility

Implements pluggable notification backends for alerts and events:
- Slack notifications
- PagerDuty incidents
- Email notifications
- Webhook notifications (generic)

Based on OperationsEngineer recommendation:
"Need pluggable alerting for SLO violations, circuit breaker events,
and security incidents."

Implements:
- NotificationProvider abstract base class
- SlackNotificationProvider
- PagerDutyNotificationProvider
- EmailNotificationProvider
- WebhookNotificationProvider
- NotificationRegistry for plugin discovery

Usage:
    from swarm_it_adk.notification_plugins import SlackNotificationProvider

    # Configure Slack notifications
    notifier = SlackNotificationProvider(
        webhook_url="https://hooks.slack.com/services/...",
        channel="#rsct-alerts"
    )

    # Send alert
    notifier.send_alert(
        title="SLO Violation",
        message="Availability SLO dropped to 99.85%",
        severity="warning"
    )
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
import json


class NotificationSeverity(str, Enum):
    """Notification severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationType(str, Enum):
    """Notification types."""
    ALERT = "alert"
    EVENT = "event"
    METRIC = "metric"
    INCIDENT = "incident"


@dataclass
class Notification:
    """Notification data structure."""
    title: str
    message: str
    severity: NotificationSeverity = NotificationSeverity.INFO
    notification_type: NotificationType = NotificationType.EVENT
    timestamp: datetime = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Set defaults."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "type": self.notification_type.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class NotificationProvider(ABC):
    """
    Abstract base class for notification providers.

    Subclasses implement specific notification backends.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize notification provider.

        Args:
            config: Provider-specific configuration
        """
        self.config = config or {}

    @abstractmethod
    def send_notification(self, notification: Notification) -> bool:
        """
        Send notification.

        Args:
            notification: Notification to send

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    def send_alert(
        self,
        title: str,
        message: str,
        severity: NotificationSeverity = NotificationSeverity.WARNING,
        **metadata
    ) -> bool:
        """
        Send alert notification.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity
            **metadata: Additional metadata

        Returns:
            True if sent successfully
        """
        notification = Notification(
            title=title,
            message=message,
            severity=severity,
            notification_type=NotificationType.ALERT,
            metadata=metadata
        )
        return self.send_notification(notification)

    def send_event(
        self,
        title: str,
        message: str,
        **metadata
    ) -> bool:
        """
        Send event notification.

        Args:
            title: Event title
            message: Event message
            **metadata: Additional metadata

        Returns:
            True if sent successfully
        """
        notification = Notification(
            title=title,
            message=message,
            severity=NotificationSeverity.INFO,
            notification_type=NotificationType.EVENT,
            metadata=metadata
        )
        return self.send_notification(notification)


class SlackNotificationProvider(NotificationProvider):
    """
    Slack notification provider.

    Sends notifications to Slack channels via webhooks.
    """

    def __init__(
        self,
        webhook_url: str,
        channel: Optional[str] = None,
        username: str = "RSCT Alert",
        icon_emoji: str = ":warning:"
    ):
        """
        Initialize Slack notifier.

        Args:
            webhook_url: Slack webhook URL
            channel: Target channel (optional, uses webhook default)
            username: Bot username
            icon_emoji: Bot icon emoji
        """
        super().__init__({
            "webhook_url": webhook_url,
            "channel": channel,
            "username": username,
            "icon_emoji": icon_emoji
        })

        try:
            import requests
            self.requests_available = True
        except ImportError:
            self.requests_available = False
            raise ImportError("requests not installed. Install with: pip install requests")

        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.icon_emoji = icon_emoji

    def _get_color(self, severity: NotificationSeverity) -> str:
        """Get Slack color for severity."""
        colors = {
            NotificationSeverity.INFO: "#36a64f",  # green
            NotificationSeverity.WARNING: "#ff9900",  # orange
            NotificationSeverity.ERROR: "#ff0000",  # red
            NotificationSeverity.CRITICAL: "#990000"  # dark red
        }
        return colors.get(severity, "#808080")

    def send_notification(self, notification: Notification) -> bool:
        """Send notification to Slack."""
        import requests

        # Build Slack message
        payload = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [
                {
                    "color": self._get_color(notification.severity),
                    "title": notification.title,
                    "text": notification.message,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": notification.severity.value.upper(),
                            "short": True
                        },
                        {
                            "title": "Type",
                            "value": notification.notification_type.value,
                            "short": True
                        },
                        {
                            "title": "Timestamp",
                            "value": notification.timestamp.isoformat(),
                            "short": False
                        }
                    ],
                    "footer": "RSCT Monitoring",
                    "ts": int(notification.timestamp.timestamp())
                }
            ]
        }

        if self.channel:
            payload["channel"] = self.channel

        # Add metadata as fields
        if notification.metadata:
            for key, value in notification.metadata.items():
                payload["attachments"][0]["fields"].append({
                    "title": key,
                    "value": str(value),
                    "short": True
                })

        # Send to Slack
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False


class PagerDutyNotificationProvider(NotificationProvider):
    """
    PagerDuty notification provider.

    Creates incidents in PagerDuty.
    """

    def __init__(
        self,
        integration_key: str,
        routing_key: Optional[str] = None
    ):
        """
        Initialize PagerDuty notifier.

        Args:
            integration_key: PagerDuty integration key
            routing_key: PagerDuty routing key (optional)
        """
        super().__init__({
            "integration_key": integration_key,
            "routing_key": routing_key
        })

        try:
            import requests
            self.requests_available = True
        except ImportError:
            self.requests_available = False
            raise ImportError("requests not installed. Install with: pip install requests")

        self.integration_key = integration_key
        self.routing_key = routing_key
        self.api_url = "https://events.pagerduty.com/v2/enqueue"

    def _get_pagerduty_severity(self, severity: NotificationSeverity) -> str:
        """Map to PagerDuty severity."""
        mapping = {
            NotificationSeverity.INFO: "info",
            NotificationSeverity.WARNING: "warning",
            NotificationSeverity.ERROR: "error",
            NotificationSeverity.CRITICAL: "critical"
        }
        return mapping.get(severity, "warning")

    def send_notification(self, notification: Notification) -> bool:
        """Send notification to PagerDuty."""
        import requests

        # Build PagerDuty event
        payload = {
            "routing_key": self.routing_key or self.integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": notification.title,
                "source": "rsct-monitoring",
                "severity": self._get_pagerduty_severity(notification.severity),
                "timestamp": notification.timestamp.isoformat(),
                "custom_details": {
                    "message": notification.message,
                    "type": notification.notification_type.value,
                    **notification.metadata
                }
            }
        }

        # Send to PagerDuty
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            return response.status_code == 202
        except Exception:
            return False


class EmailNotificationProvider(NotificationProvider):
    """
    Email notification provider.

    Sends email notifications via SMTP.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: str = "rsct@example.com",
        to_emails: List[str] = None,
        use_tls: bool = True
    ):
        """
        Initialize email notifier.

        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_username: SMTP username (optional)
            smtp_password: SMTP password (optional)
            from_email: Sender email address
            to_emails: List of recipient email addresses
            use_tls: Whether to use TLS
        """
        super().__init__({
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "from_email": from_email,
            "to_emails": to_emails or []
        })

        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_emails = to_emails or []
        self.use_tls = use_tls

    def send_notification(self, notification: Notification) -> bool:
        """Send notification via email."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        # Build email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{notification.severity.value.upper()}] {notification.title}"
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self.to_emails)

        # Plain text version
        text = f"""
{notification.title}

{notification.message}

Severity: {notification.severity.value.upper()}
Type: {notification.notification_type.value}
Timestamp: {notification.timestamp.isoformat()}

Metadata:
{json.dumps(notification.metadata, indent=2)}
"""

        # HTML version
        html = f"""
<html>
  <body>
    <h2>{notification.title}</h2>
    <p>{notification.message}</p>
    <hr>
    <p><strong>Severity:</strong> {notification.severity.value.upper()}</p>
    <p><strong>Type:</strong> {notification.notification_type.value}</p>
    <p><strong>Timestamp:</strong> {notification.timestamp.isoformat()}</p>
    <h3>Metadata</h3>
    <pre>{json.dumps(notification.metadata, indent=2)}</pre>
  </body>
</html>
"""

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        # Send email
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            return True
        except Exception:
            return False


class WebhookNotificationProvider(NotificationProvider):
    """
    Generic webhook notification provider.

    Sends JSON payloads to HTTP endpoints.
    """

    def __init__(
        self,
        webhook_url: str,
        headers: Optional[Dict[str, str]] = None,
        method: str = "POST"
    ):
        """
        Initialize webhook notifier.

        Args:
            webhook_url: Webhook URL
            headers: HTTP headers (optional)
            method: HTTP method (POST or PUT)
        """
        super().__init__({
            "webhook_url": webhook_url,
            "headers": headers or {},
            "method": method
        })

        try:
            import requests
            self.requests_available = True
        except ImportError:
            self.requests_available = False
            raise ImportError("requests not installed. Install with: pip install requests")

        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}
        self.method = method.upper()

    def send_notification(self, notification: Notification) -> bool:
        """Send notification to webhook."""
        import requests

        # Build payload
        payload = notification.to_dict()

        # Send to webhook
        try:
            if self.method == "POST":
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=10
                )
            elif self.method == "PUT":
                response = requests.put(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=10
                )
            else:
                return False

            return response.status_code in (200, 201, 202, 204)
        except Exception:
            return False


class NotificationRegistry:
    """
    Notification provider registry.

    Manages notification provider plugins.
    """

    def __init__(self):
        """Initialize notification registry."""
        self.providers: Dict[str, NotificationProvider] = {}
        self._default_provider: Optional[str] = None

    def register(self, name: str, provider: NotificationProvider):
        """Register notification provider."""
        self.providers[name] = provider

    def unregister(self, name: str):
        """Unregister notification provider."""
        self.providers.pop(name, None)

    def get_provider(self, name: Optional[str] = None) -> Optional[NotificationProvider]:
        """
        Get notification provider by name.

        Args:
            name: Provider name (uses default if None)

        Returns:
            NotificationProvider or None
        """
        if name is None:
            name = self._default_provider

        return self.providers.get(name)

    def set_default(self, name: str):
        """Set default notification provider."""
        if name in self.providers:
            self._default_provider = name

    def list_providers(self) -> List[str]:
        """List registered provider names."""
        return list(self.providers.keys())

    def broadcast_notification(self, notification: Notification) -> Dict[str, bool]:
        """
        Send notification to all registered providers.

        Args:
            notification: Notification to send

        Returns:
            Dict mapping provider name to success status
        """
        results = {}
        for name, provider in self.providers.items():
            results[name] = provider.send_notification(notification)
        return results

    def broadcast_alert(
        self,
        title: str,
        message: str,
        severity: NotificationSeverity = NotificationSeverity.WARNING,
        **metadata
    ) -> Dict[str, bool]:
        """
        Broadcast alert to all providers.

        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity
            **metadata: Additional metadata

        Returns:
            Dict mapping provider name to success status
        """
        notification = Notification(
            title=title,
            message=message,
            severity=severity,
            notification_type=NotificationType.ALERT,
            metadata=metadata
        )
        return self.broadcast_notification(notification)


# Global notification registry
_global_registry: Optional[NotificationRegistry] = None


def get_notification_registry() -> NotificationRegistry:
    """Get or create global notification registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = NotificationRegistry()
    return _global_registry


def send_alert(
    title: str,
    message: str,
    severity: NotificationSeverity = NotificationSeverity.WARNING,
    provider: Optional[str] = None,
    **metadata
) -> bool:
    """
    Send alert using default or specified provider.

    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        provider: Provider name (uses default if None)
        **metadata: Additional metadata

    Returns:
        True if sent successfully
    """
    registry = get_notification_registry()
    notifier = registry.get_provider(provider)

    if notifier is None:
        return False

    return notifier.send_alert(title, message, severity, **metadata)


def broadcast_alert(
    title: str,
    message: str,
    severity: NotificationSeverity = NotificationSeverity.WARNING,
    **metadata
) -> Dict[str, bool]:
    """
    Broadcast alert to all registered providers.

    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        **metadata: Additional metadata

    Returns:
        Dict mapping provider name to success status
    """
    registry = get_notification_registry()
    return registry.broadcast_alert(title, message, severity, **metadata)
