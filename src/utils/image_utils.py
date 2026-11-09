#src/utils/image_utils.py
"""
Image handling utilities.

Functions for loading and processing logo files for email attachments.
"""
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def load_logo(logo_path: Path) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """
    Load logo file for email attachment.

    Args:
        logo_path: Path object pointing to the logo file

    Returns:
        Tuple of (file_data, mime_type, filename) or (None, None, None) if not found
    """
    if not logo_path.exists():
        logger.warning(f"Logo not found at: {logo_path}")
        return None, None, None

    try:
        with open(logo_path, 'rb') as f:
            logo_data = f.read()

        # Determine MIME type from extension
        ext = logo_path.suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }
        mime_type = mime_types.get(ext, 'image/png')

        logger.debug(f"Loaded logo from {logo_path} ({len(logo_data)} bytes, {mime_type})")
        return logo_data, mime_type, logo_path.name

    except Exception as e:
        logger.error(f"Failed to load logo from {logo_path}: {e}")
        return None, None, None
