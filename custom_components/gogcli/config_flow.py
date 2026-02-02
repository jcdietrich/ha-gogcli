"""Config flow for gogcli integration."""
from __future__ import annotations

import asyncio
import logging
import os
import re
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
    CONF_AUTH_CODE,
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
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for gogcli."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.wrapper: GogWrapper | None = None
        self.auth_process: asyncio.subprocess.Process | None = None
        self.config_dir: str | None = None
        self.data: dict[str, Any] = {}

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
            
            self.data = user_input
            
            try:
                # Basic validation and setup
                self.config_dir = self.hass.config.path(".storage/gogcli")
                gog_path = get_binary_path(self.hass)
                
                # Check/Install binary
                version = await check_binary(gog_path)
                if not version:
                    gog_path = await install_binary(self.hass)
                
                # Sync config
                await self.hass.async_add_executor_job(sync_config, self.hass, self.config_dir)
                
                self.wrapper = GogWrapper(gog_path, self.config_dir)
                
                # Set credentials if provided
                if creds := user_input.get(CONF_CREDENTIALS_FILE):
                    full_path = self.hass.config.path(creds) if not os.path.isabs(creds) else creds
                    if not os.path.exists(full_path):
                        raise CredentialsFileNotFound
                    await self.wrapper.set_credentials(full_path)

                # Check auth status
                auth_list = await self.wrapper.list_auth()
                if user_input[CONF_ACCOUNT] in auth_list:
                    return self.async_create_entry(
                        title=f"gogcli ({user_input[CONF_ACCOUNT]})", 
                        data={**user_input, CONF_GOG_PATH: gog_path, CONF_CONFIG_DIR: self.config_dir}
                    )
                
                # Not authorized, start interactive flow
                return await self.async_step_auth()

            except CredentialsFileNotFound:
                errors["base"] = "credentials_file_not_found"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle interactive authentication."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Send code to process
            if self.auth_process:
                code = user_input[CONF_AUTH_CODE] + "\n"
                stdout, stderr = await self.auth_process.communicate(input=code.encode())
                
                if self.auth_process.returncode == 0:
                     return self.async_create_entry(
                        title=f"gogcli ({self.data[CONF_ACCOUNT]})", 
                        data={**self.data, CONF_GOG_PATH: self.wrapper.executable_path, CONF_CONFIG_DIR: self.config_dir}
                    )
                else:
                    _LOGGER.error("Auth failed: %s", stderr.decode())
                    errors["base"] = "auth_failed"
                    self.auth_process = None # Reset to try again
            else:
                 errors["base"] = "process_lost"

        # Start process and get URL
        if not self.auth_process:
            self.auth_process = await self.wrapper.start_auth(self.data[CONF_ACCOUNT])
            
            # Read stdout line by line until we find the URL
            url = None
            while True:
                line = await self.auth_process.stdout.readline()
                if not line:
                    break
                decoded = line.decode().strip()
                if "https://" in decoded:
                    # Simple extraction, gogcli prints "Go to the following link in your browser:" then the link
                    match = re.search(r'(https://[^\s]+)', decoded)
                    if match:
                        url = match.group(1)
                        break
            
            if not url:
                errors["base"] = "url_not_found"
                self.auth_process.kill()
                self.auth_process = None
                return self.async_show_form(step_id="user", errors=errors)

            self.auth_url = url

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema({vol.Required(CONF_AUTH_CODE): str}),
            description_placeholders={"url": self.auth_url},
            errors=errors
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