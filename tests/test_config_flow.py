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
        wrapper.list_auth = AsyncMock(return_value='{"accounts":[]}')
        wrapper.start_auth = AsyncMock()
        
        mock_process = MagicMock()
        mock_stdout = AsyncMock()
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
        assert result.get("description_placeholders") is None
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
    # Mock manual interaction methods
    mock_process.stdin = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.drain = AsyncMock()
    mock_process.stdin.close = MagicMock()
    mock_process.wait = AsyncMock()
    mock_process.returncode = 0
    
    flow.auth_process = mock_process
    
    user_input = {CONF_AUTH_CODE: "123456"}
    
    result = await flow.async_step_auth(user_input)
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "gogcli (test@gmail.com)"
    mock_process.stdin.write.assert_called_with(b"123456\n")
    mock_process.wait.assert_called()

@pytest.mark.asyncio
async def test_step_auth_submit_full_url_success():
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.data = {CONF_ACCOUNT: "test@gmail.com"}
    flow.config_dir = "/tmp"
    flow.wrapper = MagicMock()
    flow.wrapper.executable_path = "/mock/gog"
    
    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.drain = AsyncMock()
    mock_process.stdin.close = MagicMock()
    mock_process.wait = AsyncMock()
    mock_process.returncode = 0
    
    flow.auth_process = mock_process
    
    # Simulate user pasting full URL
    user_input = {CONF_AUTH_CODE: "http://127.0.0.1:46579/oauth2/callback?code=4/0ASc3gC0...&scope=email"}
    
    result = await flow.async_step_auth(user_input)
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Ensure extracted code is sent
    mock_process.stdin.write.assert_called_with(b"4/0ASc3gC0...\n")
    mock_process.wait.assert_called()

@pytest.mark.asyncio
async def test_step_auth_submit_code_failure():
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.data = {CONF_ACCOUNT: "test@gmail.com"}
    flow.wrapper = MagicMock()
    
    retry_process = MagicMock()
    retry_process.stdout.readline = AsyncMock(side_effect=[b"Go to: https://retry\n", b""])
    flow.wrapper.start_auth = AsyncMock(return_value=retry_process)
    
    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.drain = AsyncMock()
    mock_process.stdin.close = MagicMock()
    mock_process.wait = AsyncMock()
    mock_process.returncode = 1
    
    flow.auth_process = mock_process
    # Populate buffer manually since we don't run _drain_stdout in this unit test
    flow._proc_output = ["Error: invalid code"]
    
    user_input = {CONF_AUTH_CODE: "wrong"}
    
    result = await flow.async_step_auth(user_input)
    
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "auth_failed"
    assert flow.auth_process == retry_process