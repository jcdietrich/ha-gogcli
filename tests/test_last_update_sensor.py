import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from custom_components.gogcli.sensor import GogGmailLastUpdateSensor
from custom_components.gogcli.const import CONF_ACCOUNT

def test_last_update_sensor():
    coordinator = MagicMock()
    coordinator.entry.entry_id = "test_entry"
    coordinator.entry.data = {CONF_ACCOUNT: "test@gmail.com"}
    now = datetime(2026, 2, 2, 12, 0, 0, tzinfo=timezone.utc)
    coordinator.last_update_success_time = now
    
    sensor = GogGmailLastUpdateSensor(coordinator)
    
    assert sensor.native_value == now
    assert sensor.translation_key == "gmail_last_update"
    assert sensor.has_entity_name is True
    assert sensor.unique_id == "test_entry_last_update"
    assert sensor.device_info["name"] == "Gmail Account (test@gmail.com)"