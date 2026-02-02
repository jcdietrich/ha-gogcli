import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from custom_components.gogcli.config_flow import validate_input, CannotConnect, AccountNotAuthorized, CredentialsFileNotFound, CONF_GOG_PATH, CONF_CONFIG_DIR, CONF_CREDENTIALS_FILE

@pytest.mark.asyncio
async def test_validate_input_with_credentials_file():
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.config.path.side_effect = lambda p: f"/mock/config/{p}"
    data = {
        "account": "test@gmail.com",
        "credentials_file": "credentials.json",
        "gog_path": "/existing/gog"
    }

    with patch("custom_components.gogcli.config_flow.sync_config"), \
         patch("custom_components.gogcli.config_flow.GogWrapper") as MockWrapper, \
         patch("os.path.exists", return_value=True):
        
        wrapper_instance = MockWrapper.return_value
        wrapper_instance.version = AsyncMock(return_value="gog version 1.0.0")
        wrapper_instance.set_credentials = AsyncMock()
        wrapper_instance.list_auth = AsyncMock(return_value='{"accounts":[{"email":"test@gmail.com"}]}')

        result = await validate_input(hass, data)
        
        assert result["title"] == "gogcli (test@gmail.com)"
        wrapper_instance.set_credentials.assert_called_with("/mock/config/credentials.json")

@pytest.mark.asyncio
async def test_validate_input_credentials_file_not_found():
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.config.path.side_effect = lambda p: f"/mock/config/{p}"
    data = {
        "account": "test@gmail.com",
        "credentials_file": "missing.json"
    }

    with patch("custom_components.gogcli.config_flow.get_binary_path", return_value="/mock/gog"), \
         patch("custom_components.gogcli.config_flow.check_binary", return_value="1.0.0"), \
         patch("custom_components.gogcli.config_flow.sync_config"), \
         patch("custom_components.gogcli.config_flow.GogWrapper") as MockWrapper, \
         patch("os.path.exists", return_value=False):
        
        wrapper_instance = MockWrapper.return_value
        wrapper_instance.version = AsyncMock(return_value="gog version 1.0.0")

        with pytest.raises(CredentialsFileNotFound):
            await validate_input(hass, data)

@pytest.mark.asyncio
async def test_validate_input_success_existing_binary():
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.config.path.return_value = "/mock/config/path/.storage/gogcli"
    data = {
        "account": "test@gmail.com",
        "gog_path": "/existing/gog"
    }

    with patch("custom_components.gogcli.config_flow.sync_config") as mock_sync, \
         patch("custom_components.gogcli.config_flow.GogWrapper") as MockWrapper:
        
        wrapper_instance = MockWrapper.return_value
        wrapper_instance.version = AsyncMock(return_value="gog version 1.0.0")
        wrapper_instance.list_auth = AsyncMock(return_value='{"accounts":[{"email":"test@gmail.com"}]}')

        result = await validate_input(hass, data)
        
        assert result["title"] == "gogcli (test@gmail.com)"
        assert result["data"][CONF_GOG_PATH] == "/existing/gog"
        assert result["data"][CONF_CONFIG_DIR] == "/mock/config/path/.storage/gogcli"
        
        # Verify sync_config was scheduled
        hass.async_add_executor_job.assert_called_with(mock_sync, hass, "/mock/config/path/.storage/gogcli")

@pytest.mark.asyncio
async def test_validate_input_install_success():
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.config.path.return_value = "/mock/config/path/.storage/gogcli"
    data = {
        "account": "test@gmail.com"
    }

    with patch("custom_components.gogcli.config_flow.get_binary_path", return_value="/install/path/gog"), \
         patch("custom_components.gogcli.config_flow.check_binary", return_value=None), \
         patch("custom_components.gogcli.config_flow.install_binary", return_value="/install/path/gog") as mock_install, \
         patch("custom_components.gogcli.config_flow.sync_config") as mock_sync, \
         patch("custom_components.gogcli.config_flow.GogWrapper") as MockWrapper:
        
        wrapper_instance = MockWrapper.return_value
        wrapper_instance.version = AsyncMock(return_value="gog version 1.0.0")
        wrapper_instance.list_auth = AsyncMock(return_value='{"accounts":[{"email":"test@gmail.com"}]}')

        result = await validate_input(hass, data)
        
        mock_install.assert_called_once()
        assert result["title"] == "gogcli (test@gmail.com)"
        assert result["data"][CONF_GOG_PATH] == "/install/path/gog"

@pytest.mark.asyncio
async def test_validate_input_install_fail():
    hass = MagicMock()
    hass.config.path.return_value = "/mock/config/path/.storage/gogcli"
    data = {
        "account": "test@gmail.com"
    }

    with patch("custom_components.gogcli.config_flow.get_binary_path", return_value="/install/path/gog"), \
         patch("custom_components.gogcli.config_flow.check_binary", return_value=None), \
         patch("custom_components.gogcli.config_flow.install_binary", side_effect=RuntimeError("Install failed")
        ):
        
        with pytest.raises(CannotConnect):
            await validate_input(hass, data)

@pytest.mark.asyncio
async def test_validate_input_auth_failed():
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.config.path.return_value = "/mock/config/path/.storage/gogcli"
    data = {
        "account": "wrong@gmail.com",
        "gog_path": "gog"
    }

    with patch("custom_components.gogcli.config_flow.sync_config"), \
         patch("custom_components.gogcli.config_flow.GogWrapper") as MockWrapper:
        
        wrapper_instance = MockWrapper.return_value
        wrapper_instance.version = AsyncMock(return_value="gog version 1.0.0")
        wrapper_instance.list_auth = AsyncMock(return_value='{"accounts":[{"email":"other@gmail.com"}]}')

        with pytest.raises(AccountNotAuthorized):
            await validate_input(hass, data)
