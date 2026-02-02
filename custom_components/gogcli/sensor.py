"""Sensor platform for gogcli."""
from __future__ import annotations

import logging
import base64
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN, CONF_ACCOUNT
from .coordinator import GogGmailCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: GogGmailCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [GogGmailSensor(coordinator, i) for i in range(5)]
    sensors.append(GogGmailLastUpdateSensor(coordinator))
    async_add_entities(sensors)

class GogGmailLastUpdateSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the last time Gmail was checked."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check"
    _attr_has_entity_name = True
    _attr_translation_key = "gmail_last_update"

    def __init__(self, coordinator: GogGmailCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_last_update"
        account = coordinator.entry.data[CONF_ACCOUNT]
        self.entity_id = f"sensor.{slugify(account)}_gmail_last_update"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        account = self.coordinator.entry.data[CONF_ACCOUNT]
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=f"Gmail Account ({account})",
            manufacturer="Google",
            model="Gmail via gogcli",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.last_update_success_time

class GogGmailSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Gmail sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "gmail_email"
    _attr_icon = "mdi:email"

    def __init__(self, coordinator: GogGmailCoordinator, index: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.index = index
        self._attr_unique_id = f"{coordinator.entry.entry_id}_email_{index}"
        account = coordinator.entry.data[CONF_ACCOUNT]
        self.entity_id = f"sensor.{slugify(account)}_gmail_email_{index + 1}"

    @property
    def translation_placeholders(self) -> dict[str, str]:
        """Return translation placeholders."""
        return {"index": str(self.index + 1)}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        account = self.coordinator.entry.data[CONF_ACCOUNT]
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=f"Gmail Account ({account})",
            manufacturer="Google",
            model="Gmail via gogcli",
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        email = self._get_email_data()
        if not email:
            return "Empty"
        
        sender = self._get_header(email, "From") or "Unknown"
        subject = self._get_header(email, "Subject") or "No Subject"
        
        state = f"{sender} - {subject}"
        return state[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        email = self._get_email_data()
        if not email:
            return {}

        headers = email.get("payload", {}).get("headers", [])
        labels = email.get("labelIds", [])
        
        body_text, body_html = self._extract_body(email.get("payload", {}))
        
        return {
            "date_received": self._get_header(email, "Date"),
            "from": self._get_header(email, "From"),
            "to": self._get_header(email, "To"),
            "subject": self._get_header(email, "Subject"),
            "message_id": email.get("id"),
            "thread_id": email.get("threadId"),
            "body_text": body_text or email.get("snippet", ""),
            "body_html": body_html,
            "labels": labels,
            "has_attachment": self._check_attachment(email.get("payload", {})),
            "have_replied": self._check_reply(email),
            "priority": "IMPORTANT" in labels,
            "starred": "STARRED" in labels,
            "is_unread": "UNREAD" in labels,
        }

    def _check_attachment(self, payload: dict[str, Any]) -> bool:
        """Check if the email has attachments."""
        if payload.get("filename"):
            return True
        
        parts = payload.get("parts", [])
        for part in parts:
            if self._check_attachment(part):
                return True
        
        return False

    def _check_reply(self, email: dict[str, Any]) -> bool:
        """Check if we have replied to this email."""
        thread = email.get("_thread", {})
        messages = thread.get("messages", [])
        current_id = email.get("id")
        
        found_current = False
        for msg in messages:
            if msg.get("id") == current_id:
                found_current = True
                continue
            
            if found_current:
                # Check if this subsequent message is from us (SENT label)
                if "SENT" in msg.get("labelIds", []):
                    return True
        
        return False

    def _extract_body(self, payload: dict[str, Any]) -> tuple[str | None, str | None]:
        """Extract text and html body from payload."""
        text_body = None
        html_body = None

        mime_type = payload.get("mimeType")
        body_data = payload.get("body", {}).get("data")

        if body_data:
            decoded = self._decode_data(body_data)
            if mime_type == "text/plain":
                text_body = decoded
            elif mime_type == "text/html":
                html_body = decoded

        parts = payload.get("parts", [])
        for part in parts:
            part_text, part_html = self._extract_body(part)
            if part_text and not text_body:
                text_body = part_text
            if part_html and not html_body:
                html_body = part_html
        
        return text_body, html_body

    def _decode_data(self, data: str) -> str:
        """Decode base64url encoded data."""
        try:
            return base64.urlsafe_b64decode(data + "===").decode("utf-8")
        except Exception:
            return ""

    def _get_email_data(self) -> dict[str, Any] | None:
        """Get the email data for this sensor index."""
        if not self.coordinator.data or len(self.coordinator.data) <= self.index:
            return None
        return self.coordinator.data[self.index]

    def _get_header(self, email: dict[str, Any], header_name: str) -> str | None:
        """Get a specific header value."""
        headers = email.get("payload", {}).get("headers", [])
        for header in headers:
            if header.get("name") == header_name:
                return header.get("value")
        return None