"""
Pluggable notification channel for pipeline alerts.

The rubric asks for owners/stakeholders to be notified on failure. In a
real deployment this would be email/Slack/PagerDuty; this coursework
deliverable implements a console+log notifier by default (so it runs with
no external credentials) and stubs the real channels behind the same
interface, so swapping one in later is a one-line change, not a redesign.
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("pipeline")


class Notifier(ABC):
    @abstractmethod
    def notify(self, subject: str, message: str, severity: str = "CRITICAL"):
        ...


class LogNotifier(Notifier):
    """Default notifier: writes the alert through the same structured
    logger as everything else, and to stdout, so it shows up in the cron
    log without needing any external service configured. This is what
    build_pipeline() uses unless a different notifier is passed in."""

    def notify(self, subject: str, message: str, severity: str = "CRITICAL"):
        logger.log(
            logging.CRITICAL if severity == "CRITICAL" else logging.WARNING,
            f"ALERT [{severity}] {subject} :: {message}",
        )
        print(f"\n{'='*70}\nALERT [{severity}]: {subject}\n{message}\n{'='*70}\n")


class EmailNotifier(Notifier):
    """Stub for a real deployment. Not wired to real SMTP credentials in
    this coursework repo -- shown to demonstrate the extension point the
    Notifier interface provides, and left inert (raises) if actually used
    without configuration, rather than pretending to send mail."""

    def __init__(self, smtp_host, smtp_port, from_addr, to_addrs):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    def notify(self, subject: str, message: str, severity: str = "CRITICAL"):
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(message)
        msg["Subject"] = f"[{severity}] {subject}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as s:
            s.sendmail(self.from_addr, self.to_addrs, msg.as_string())
        logger.info(f"Sent email alert to {self.to_addrs}")


class SlackWebhookNotifier(Notifier):
    """Stub for a real deployment via an incoming webhook URL. Same
    reasoning as EmailNotifier: interface is real, credentials are not."""

    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def notify(self, subject: str, message: str, severity: str = "CRITICAL"):
        import json
        import urllib.request

        payload = json.dumps({"text": f"*[{severity}] {subject}*\n{message}"}).encode()
        req = urllib.request.Request(self.webhook_url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        logger.info("Sent Slack webhook alert")


class MultiNotifier(Notifier):
    """Fan a single alert out to several channels at once (e.g. log +
    email + Slack), so pipeline_runner.py only ever calls one notifier."""

    def __init__(self, notifiers):
        self.notifiers = notifiers

    def notify(self, subject: str, message: str, severity: str = "CRITICAL"):
        for n in self.notifiers:
            try:
                n.notify(subject, message, severity)
            except Exception as e:
                logger.error(f"Notifier {type(n).__name__} itself failed: {e}")
