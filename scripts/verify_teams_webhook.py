#!/usr/bin/env python3
"""
scripts/verify_teams_webhook.py

Manual integration test to verify Teams webhook configuration.
This script sends a real test message to the configured Teams channel.

Usage:
    python scripts/verify_teams_webhook.py

Requirements:
    - TEAMS_WEBHOOK_URL must be set in .env file
    - pymsteams package must be installed
"""
from decouple import config
import pymsteams
import sys

TEAMS_WEBHOOK_URL = config('TEAMS_WEBHOOK_URL', default='')

if not TEAMS_WEBHOOK_URL:
    print("ERROR: TEAMS_WEBHOOK_URL not configured in .env")
    sys.exit(1)

print(f"Testing webhook: {TEAMS_WEBHOOK_URL[:50]}...")

try:
    # Create simple test message
    test_message = pymsteams.connectorcard(TEAMS_WEBHOOK_URL)
    test_message.title("Test Message from Python")
    test_message.text("If you can see this message, your webhook is working correctly!")
    test_message.color("00FF00")  # Green
    
    # Send
    response = test_message.send()
    
    print(f"[OK] Response: {response}")
    print(f"[OK] Message sent! Check your Teams channel.")
    
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
