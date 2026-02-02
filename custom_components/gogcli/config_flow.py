"""Config flow for gogcli integration."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from homeassistant.util import slugify
from .const import (
    CONF_ACCOUNT, 
    CONF_GOG_PATH, 
    CONF_CONFIG_DIR, 
    CONF_CREDENTIALS_FILE, 
    CONF_POLLING_INTERVAL, 
    DEFAULT_GOG_PATH, 
    DEFAULT_POLLING_INTERVAL, 
    DOMAIN,
    DASHBOARD_CARD_YAML
)
from .utils import check_binary, install_binary, get_binary_path, sync_config, GogWrapper

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT): str,
        vol.Optional(CONF_CREDENTIALS_FILE): str,
        vol.Optional(CONF_GOG_PATH): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    gog_path = data.get(CONF_GOG_PATH)
    account = data[CONF_ACCOUNT]
    credentials_file = data.get(CONF_CREDENTIALS_FILE)
    
    # Define config directory
    config_dir = hass.config.path(".storage/gogcli")

    # If no path provided, try default or install
    if not gog_path:
        default_bin_path = get_binary_path(hass)
        version = await check_binary(default_bin_path)
        
        if version:
            gog_path = default_bin_path
        else:
            # Try to install
            try:
                gog_path = await install_binary(hass)
            except Exception as err:
                _LOGGER.error("Failed to install gogcli: %s", err)
                raise CannotConnect

    # Sync configuration
    await hass.async_add_executor_job(sync_config, hass, config_dir)
    
    wrapper = GogWrapper(gog_path, config_dir)

    # Check if gogcli is executable and get version
    try:
        await wrapper.version()
    except (FileNotFoundError, RuntimeError) as err:
        _LOGGER.error("gogcli version failed: %s", err)
        raise CannotConnect

    # If credentials file provided, set it
    if credentials_file:
        full_credentials_path = hass.config.path(credentials_file) if not os.path.isabs(credentials_file) else credentials_file
        if not os.path.exists(full_credentials_path):
             _LOGGER.error("Credentials file not found: %s", full_credentials_path)
             raise CredentialsFileNotFound
        
        try:
            await wrapper.set_credentials(full_credentials_path)
        except Exception as err:
            _LOGGER.error("Failed to set credentials: %s", err)
            raise CannotConnect

    # Check if account is authorized
    try:
        auth_json = await wrapper.list_auth()
        
        if account not in auth_json:
             _LOGGER.error("Account %s not found in gog auth list", account)
             # We should tell the user what to do
             raise AccountNotAuthorized(f"Run `HOME={config_dir} {gog_path} auth add {account}` in terminal")

    except (CannotConnect, AccountNotAuthorized):
        raise
    except Exception as err:
        _LOGGER.exception("Unexpected error validating gogcli: %s", err)
        raise CannotConnect

    return {
        "title": f"gogcli ({account})", 
        "data": {
            **data, 
            CONF_GOG_PATH: gog_path,
            CONF_CONFIG_DIR: config_dir
        }
    }

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for gogcli."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ACCOUNT])
            self._abort_if_unique_id_configured()
            
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except AccountNotAuthorized:
                errors["base"] = "account_not_authorized"
            except CredentialsFileNotFound:
                errors["base"] = "credentials_file_not_found"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=info["data"])

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for gogcli."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["polling", "dashboard_yaml"],
        )

    async def async_step_polling(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle polling interval settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLLING_INTERVAL,
                    default=self._config_entry.options.get(
                        CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5)),
            }
        )

        return self.async_show_form(step_id="polling", data_schema=schema)

    async def async_step_dashboard_yaml(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Display the dashboard card YAML."""
        if user_input is not None:
            return await self.async_step_init()

        account = self._config_entry.data[CONF_ACCOUNT]
        prefix = slugify(account)
        card_yaml = DASHBOARD_CARD_YAML.format(prefix=prefix, account=account)

        return self.async_show_form(
            step_id="dashboard_yaml",
            description_placeholders={"card_yaml": card_yaml}
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class AccountNotAuthorized(HomeAssistantError):
    """Error to indicate the account is not authorized in gogcli."""

class CredentialsFileNotFound(HomeAssistantError):
    """Error to indicate the credentials file was not found."""