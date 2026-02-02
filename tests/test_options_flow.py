import pytest
from unittest.mock import MagicMock
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import slugify
from custom_components.gogcli.config_flow import OptionsFlowHandler
from custom_components.gogcli.const import CONF_POLLING_INTERVAL, CONF_ACCOUNT, DASHBOARD_CARD_YAML

@pytest.mark.asyncio
async def test_options_flow_init_menu():
    entry = MagicMock()
    flow = OptionsFlowHandler(entry)
    
    result = await flow.async_step_init()
    
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    assert "polling" in result["menu_options"]
    assert "dashboard_yaml" in result["menu_options"]

@pytest.mark.asyncio
async def test_options_flow_polling():
    entry = MagicMock()
    entry.options = {}
    flow = OptionsFlowHandler(entry)
    flow.hass = MagicMock()
    
    # Test showing the form
    result = await flow.async_step_polling()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "polling"
    
    # Test saving
    user_input = {CONF_POLLING_INTERVAL: 10}
    result = await flow.async_step_polling(user_input)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == user_input

@pytest.mark.asyncio
async def test_options_flow_dashboard_yaml():
    entry = MagicMock()
    account = "test@gmail.com"
    entry.data = {CONF_ACCOUNT: account}
    flow = OptionsFlowHandler(entry)
    
    result = await flow.async_step_dashboard_yaml()
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "dashboard_yaml"
    
    expected_yaml = DASHBOARD_CARD_YAML.format(prefix=slugify(account), account=account)
    assert result["description_placeholders"]["card_yaml"] == expected_yaml
