import pytest
from unittest.mock import MagicMock
from homeassistant.const import STATE_UNKNOWN
from custom_components.gogcli.sensor import GogGmailSensor
from custom_components.gogcli.const import CONF_ACCOUNT
import base64

def encode_body(text):
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")

@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test_entry"
    coordinator.entry.data = {CONF_ACCOUNT: "test@gmail.com"}
    
    # Sample email data
    email_1 = {
        "id": "123",
        "threadId": "thread-123",
        "labelIds": ["INBOX", "IMPORTANT", "STARRED"],
        "snippet": "Hello world snippet",
        "payload": {
            "headers": [
                {"name": "From", "value": "Sender <sender@example.com>"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Mon, 02 Feb 2026 12:00:00 +0000"},
                {"name": "To", "value": "Me <me@example.com>"},
            ],
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": encode_body("Hello world text")}
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": encode_body("<b>Hello world html</b>")}
                }
            ]
        },
        "_thread": {
            "messages": [
                {"id": "123", "labelIds": ["INBOX"]},
                {"id": "124", "labelIds": ["SENT"]}
            ]
        }
    }
    
    coordinator.data = [email_1]
    return coordinator

def test_sensor_state_and_attributes(mock_coordinator):
    sensor = GogGmailSensor(mock_coordinator, 0)
    
    # Test state
    assert sensor.native_value == "Sender <sender@example.com> - Test Subject"
    
    # Test attributes
    attrs = sensor.extra_state_attributes
    assert attrs["from"] == "Sender <sender@example.com>"
    assert attrs["subject"] == "Test Subject"
    assert attrs["message_id"] == "123"
    assert attrs["thread_id"] == "thread-123"
    assert attrs["date_received"] == "Mon, 02 Feb 2026 12:00:00 +0000"
    assert attrs["body_text"] == "Hello world text"
    assert attrs["body_html"] == "<b>Hello world html</b>"
    assert attrs["priority"] is True
    assert attrs["starred"] is True
    assert "INBOX" in attrs["labels"]
    assert attrs["have_replied"] is True
    assert attrs["has_attachment"] is False
    # Mock data didn't have UNREAD label, so it should be False
    assert attrs["is_unread"] is False

def test_sensor_with_attachment(mock_coordinator):
    # Add attachment to mock data
    email_with_attachment = mock_coordinator.data[0].copy()
    email_with_attachment["payload"]["parts"].append({
        "mimeType": "application/pdf",
        "filename": "document.pdf",
        "body": {"attachmentId": "att1"}
    })
    mock_coordinator.data[0] = email_with_attachment
    
    sensor = GogGmailSensor(mock_coordinator, 0)
    attrs = sensor.extra_state_attributes
    assert attrs["has_attachment"] is True

def test_sensor_have_replied_false(mock_coordinator):
    # Update mock to remove reply
    mock_coordinator.data[0]["_thread"]["messages"] = [
        {"id": "123", "labelIds": ["INBOX"]}
    ]
    sensor = GogGmailSensor(mock_coordinator, 0)
    assert sensor.extra_state_attributes["have_replied"] is False

def test_sensor_empty(mock_coordinator):
    # Test sensor with index 1 (no data)
    sensor = GogGmailSensor(mock_coordinator, 1)
    
    assert sensor.native_value == "Empty"
    assert sensor.extra_state_attributes == {}
