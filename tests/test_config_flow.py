import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from homeassistant.data_entry_flow import FlowResultType
from custom_components.gogcli.config_flow import ConfigFlow, CONF_GOG_PATH, CONF_CONFIG_DIR, CONF_CREDENTIALS_FILE, CONF_AUTH_CODE, CONF_ACCOUNT, CredentialsFileNotFound

@pytest.mark.asyncio
async def test_step_user_already_authorized():
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.config.path.side_effect = lambda p: f"/mock/config/{p}"
    
    flow = ConfigFlow()
    flow.hass = hass
    
    data = {CONF_ACCOUNT: "test@gmail.com"}

    with patch("custom_components.gogcli.config_flow.get_binary_path", return_value="/mock/gog"), \
         patch("custom_components.gogcli.config_flow.check_binary", return_value="1.0.0"), \
         patch("custom_components.gogcli.config_flow.sync_config"), \
         patch("custom_components.gogcli.config_flow.GogWrapper") as MockWrapper:
        
        wrapper = MockWrapper.return_value
        wrapper.list_auth = AsyncMock(return_value='{"accounts":[{"email":"test@gmail.com"}]}')
        
        # Assume unique_id check passes (mocking async_set_unique_id on flow if needed, but it's internal)
        # We need to mock the mixin methods
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        result = await flow.async_step_user(data)
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "gogcli (test@gmail.com)"

@pytest.mark.asyncio
async def test_step_user_needs_auth():
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.config.path.return_value = "/mock/config/.storage/gogcli"
    
    flow = ConfigFlow()
    flow.hass = hass
    data = {CONF_ACCOUNT: "test@gmail.com"}

    with patch("custom_components.gogcli.config_flow.get_binary_path", return_value="/mock/gog"), \
         patch("custom_components.gogcli.config_flow.check_binary", return_value="1.0.0"), \
         patch("custom_components.gogcli.config_flow.sync_config"), \
         patch("custom_components.gogcli.config_flow.GogWrapper") as MockWrapper:
        
        wrapper = MockWrapper.return_value
        wrapper.list_auth = AsyncMock(return_value='{"accounts":[]}') # Not authorized
        wrapper.start_auth = AsyncMock()
        
        # Mock process stdout for URL
        mock_process = MagicMock()
        mock_stdout = AsyncMock()
        # First call returns line with URL, second returns empty (EOF)
        mock_stdout.readline.side_effect = [
            b"Go to: https://google.com/auth\n",
            b""
        ]
        mock_process.stdout = mock_stdout
        wrapper.start_auth.return_value = mock_process

        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        result = await flow.async_step_user(data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["description_placeholders"]["url"] == "https://google.com/auth"
        assert flow.auth_process == mock_process

@pytest.mark.asyncio
async def test_step_auth_submit_code_success():
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.data = {CONF_ACCOUNT: "test@gmail.com"}
    flow.config_dir = "/tmp"
    flow.wrapper = MagicMock()
    flow.wrapper.executable_path = "/mock/gog"
    
    mock_process = MagicMock()
    # communicate returns (stdout, stderr)
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_process.returncode = 0
    flow.auth_process = mock_process
    
    user_input = {CONF_AUTH_CODE: "123456"}
    
    result = await flow.async_step_auth(user_input)
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "gogcli (test@gmail.com)"
    mock_process.communicate.assert_called_with(input=b"123456\n")

@pytest.mark.asyncio
async def test_step_auth_submit_code_failure():
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.data = {CONF_ACCOUNT: "test@gmail.com"}
    flow.wrapper = MagicMock() # Mock wrapper
    
    # Mock start_auth for retry
    retry_process = MagicMock()
    retry_process.stdout.readline = AsyncMock(side_effect=[b"Go to: https://retry\n", b""])
    flow.wrapper.start_auth = AsyncMock(return_value=retry_process)
    
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b"Error: invalid code"))
    mock_process.returncode = 1
    flow.auth_process = mock_process
    
    user_input = {CONF_AUTH_CODE: "wrong"}
    
    result = await flow.async_step_auth(user_input)
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"]["base"] == "auth_failed"
    assert flow.auth_process == retry_process # Should be the new process
