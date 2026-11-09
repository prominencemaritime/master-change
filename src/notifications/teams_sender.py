#src/notifications/teams_sender.py
"""
Microsoft Teams notification handler (stub for future implementation).

This is a placeholder for future Teams integration.
"""
import logging

logger = logging.getLogger(__name__)


class TeamsSender:
    """
    Handles Microsoft Teams webhook notifications.
    
    Currently a stub - to be implemented in future.
    """
    
    def __init__(self, webhook_url: str):
        """
        Initialize Teams sender.
        
        Args:
            webhook_url: Microsoft Teams webhook URL
        """
        self.webhook_url = webhook_url
        logger.info("TeamsSender initialized (stub - not yet implemented)")
    
    def send(self, title: str, message: str, data: dict) -> None:
        """
        Send message to Teams channel (not yet implemented).
        
        Args:
            title: Message title
            message: Message body
            data: Additional data to include
        """
        logger.warning("Teams notifications not yet implemented - skipping")
        pass
