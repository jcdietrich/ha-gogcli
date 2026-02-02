import pytest
from unittest.mock import MagicMock
from custom_components.gogcli.sensor import GogGmailSensor, GogGmailLastUpdateSensor
from custom_components.gogcli.const import DOMAIN, CONF_ACCOUNT

def test_sensor_device_info_multi_account():
    # Setup account 1
    coordinator1 = MagicMock()
    coordinator1.entry.entry_id = "entry_1"
    coordinator1.entry.data = {CONF_ACCOUNT: "user1@gmail.com"}
    coordinator1.data = []
    
    # Setup account 2
    coordinator2 = MagicMock()
    coordinator2.entry.entry_id = "entry_2"
    coordinator2.entry.data = {CONF_ACCOUNT: "user2@gmail.com"}
    coordinator2.data = []
    
    # Check sensor 1
    sensor1 = GogGmailSensor(coordinator1, 0)
    device_info1 = sensor1.device_info
    assert device_info1["identifiers"] == {(DOMAIN, "entry_1")}
    assert device_info1["name"] == "Gmail Account (user1@gmail.com)"
    
    # Check sensor 2
    sensor2 = GogGmailSensor(coordinator2, 0)
    device_info2 = sensor2.device_info
    assert device_info2["identifiers"] == {(DOMAIN, "entry_2")}
    assert device_info2["name"] == "Gmail Account (user2@gmail.com)"
    
    # Check LastUpdate sensor 1
    update_sensor1 = GogGmailLastUpdateSensor(coordinator1)
    assert update_sensor1.device_info["identifiers"] == {(DOMAIN, "entry_1")}

def test_sensor_unique_ids_different():
    coordinator1 = MagicMock()
    coordinator1.entry.entry_id = "entry_1"
    coordinator1.entry.data = {CONF_ACCOUNT: "user1@gmail.com"}
    
    coordinator2 = MagicMock()
    coordinator2.entry.entry_id = "entry_2"
    coordinator2.entry.data = {CONF_ACCOUNT: "user2@gmail.com"}
    
    sensor1 = GogGmailSensor(coordinator1, 0)
    sensor2 = GogGmailSensor(coordinator2, 0)
    
    assert sensor1.unique_id != sensor2.unique_id
    assert "entry_1" in sensor1.unique_id
    assert "entry_2" in sensor2.unique_id