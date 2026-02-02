import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.gogcli import async_setup_entry, async_unload_entry, DOMAIN

@pytest.mark.asyncio
async def test_unload_entry():
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.async_add_executor_job = AsyncMock()
    
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"gog_path": "gog", "config_dir": "/tmp"}
    
    # Setup
    with patch("custom_components.gogcli.GogGmailCoordinator") as MockCoordinator, \
         patch("custom_components.gogcli.get_binary_path", return_value="/mock/gog"), \
         patch("custom_components.gogcli.check_binary", return_value="1.0.0"):
        
        coordinator = MockCoordinator.return_value
        coordinator.async_config_entry_first_refresh = AsyncMock()
        await async_setup_entry(hass, entry)
    
    assert entry.entry_id in hass.data[DOMAIN]
    
    # Unload
    result = await async_unload_entry(hass, entry)
    
    assert result is True
    assert entry.entry_id not in hass.data[DOMAIN]
    hass.config_entries.async_unload_platforms.assert_called_once()
