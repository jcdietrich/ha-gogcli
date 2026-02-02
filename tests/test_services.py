import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError
from custom_components.gogcli import async_setup_entry, DOMAIN

@pytest.mark.asyncio
async def test_services_registration_and_calls():
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    hass.services.has_service.return_value = False
    hass.services.async_register = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.async_add_executor_job = AsyncMock()
    
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"gog_path": "gog", "config_dir": "/tmp"}
    entry.options = {}
    entry.async_on_unload = MagicMock()
    
    # Mock coordinator setup
    with patch("custom_components.gogcli.GogGmailCoordinator") as MockCoordinator, \
         patch("custom_components.gogcli.get_binary_path", return_value="/mock/gog"), \
         patch("custom_components.gogcli.check_binary", return_value="1.0.0"):
        
        coordinator_instance = MockCoordinator.return_value
        coordinator_instance.async_config_entry_first_refresh = AsyncMock()
        coordinator_instance.async_request_refresh = AsyncMock()
        coordinator_instance.wrapper = MagicMock()
        coordinator_instance.wrapper.get_thread = AsyncMock(return_value={"id": "thread-123", "messages": []})
        
        await async_setup_entry(hass, entry)
        
        # Verify service registration
        assert hass.services.async_register.call_count == 2 # update_gmail, get_thread
        
        # Extract handlers
        update_handler = None
        get_thread_handler = None
        for call_args in hass.services.async_register.call_args_list:
            if call_args[0][1] == "update_gmail":
                update_handler = call_args[0][2]
            if call_args[0][1] == "get_thread":
                get_thread_handler = call_args[0][2]
        
        assert update_handler is not None
        assert get_thread_handler is not None
        
        # Test update_gmail (all)
        call_update_all = ServiceCall(hass, DOMAIN, "update_gmail", {})
        await update_handler(call_update_all)
        coordinator_instance.async_request_refresh.assert_called_once()
        
        # Test update_gmail (specific)
        coordinator_instance.async_request_refresh.reset_mock()
        call_update_specific = ServiceCall(hass, DOMAIN, "update_gmail", {"config_entry_ids": ["test_entry"]})
        await update_handler(call_update_specific)
        coordinator_instance.async_request_refresh.assert_called_once()

        # Test update_gmail (wrong entry)
        coordinator_instance.async_request_refresh.reset_mock()
        call_update_wrong = ServiceCall(hass, DOMAIN, "update_gmail", {"config_entry_ids": ["wrong_entry"]})
        await update_handler(call_update_wrong)
        coordinator_instance.async_request_refresh.assert_not_called()

        # Test get_thread (success)
        call_thread = ServiceCall(hass, DOMAIN, "get_thread", {"thread_id": "t1", "config_entry_id": "test_entry"})
        response = await get_thread_handler(call_thread)
        assert response == {"id": "thread-123", "messages": []}
        coordinator_instance.wrapper.get_thread.assert_called_with("t1")

        # Test get_thread (missing entry)
        call_thread_missing = ServiceCall(hass, DOMAIN, "get_thread", {"thread_id": "t1", "config_entry_id": "wrong"})
        with pytest.raises(ServiceValidationError):
            await get_thread_handler(call_thread_missing)