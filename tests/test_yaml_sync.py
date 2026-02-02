import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.gogcli import async_setup_entry, DOMAIN
from custom_components.gogcli.const import CONF_CONFIG_DIR

@pytest.mark.asyncio
async def test_yaml_sync_on_setup():
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.async_add_executor_job = AsyncMock()
    
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"gog_path": "gog", CONF_CONFIG_DIR: "/mock/config/dir"}
    entry.options = {}
    entry.async_on_unload = MagicMock()
    
    with patch("custom_components.gogcli.GogGmailCoordinator") as MockCoordinator, \
         patch("custom_components.gogcli.sync_config") as mock_sync_config, \
         patch("custom_components.gogcli.get_binary_path", return_value="/mock/gog"), \
         patch("custom_components.gogcli.check_binary", return_value="1.0.0"), \
         patch("custom_components.gogcli.setup_services"): # Avoid re-registering services
        
        coordinator = MockCoordinator.return_value
        coordinator.async_config_entry_first_refresh = AsyncMock()
        
        await async_setup_entry(hass, entry)
        
        # Verify sync_config was called via executor
        hass.async_add_executor_job.assert_called_with(mock_sync_config, hass, "/mock/config/dir")

