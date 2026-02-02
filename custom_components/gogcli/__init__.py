"""The gogcli integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, CONF_CONFIG_DIR
from .coordinator import GogGmailCoordinator
from .utils import sync_config, check_binary, install_binary, get_binary_path

_LOGGER = logging.getLogger(__name__)

# List the platforms that you want to support.
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up gogcli from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Ensure binary exists
    gog_path = get_binary_path(hass)
    if not await check_binary(gog_path):
        try:
            await install_binary(hass)
        except Exception as err:
            _LOGGER.error("Failed to install gogcli during setup: %s", err)
            return False

    # Sync YAML config
    if config_dir := entry.data.get(CONF_CONFIG_DIR):
        await hass.async_add_executor_job(sync_config, hass, config_dir)
    
    coordinator = GogGmailCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    setup_services(hass)

    return True

def setup_services(hass: HomeAssistant) -> None:
    """Register services for the gogcli integration."""
    if hass.services.has_service(DOMAIN, "update_gmail"):
        return

    async def handle_update_gmail(call: ServiceCall):
        """Handle the update_gmail service call."""
        entry_ids = call.data.get("config_entry_ids")
        
        if not entry_ids:
            # Update all
            entry_ids = list(hass.data[DOMAIN].keys())
        
        for entry_id in entry_ids:
            if coordinator := hass.data[DOMAIN].get(entry_id):
                await coordinator.async_request_refresh()
            else:
                _LOGGER.warning("Config entry %s not found for update_gmail", entry_id)

    hass.services.async_register(
        DOMAIN, 
        "update_gmail", 
        handle_update_gmail,
        schema=vol.Schema({
            vol.Optional("config_entry_ids"): cv.ensure_list_csv,
        })
    )

    async def handle_get_thread(call: ServiceCall) -> dict:
        """Handle get_thread service."""
        thread_id = call.data["thread_id"]
        entry_id = call.data["config_entry_id"]

        target_coordinator = hass.data[DOMAIN].get(entry_id)
        if not target_coordinator:
            raise ServiceValidationError(f"Config entry {entry_id} not found")

        try:
            thread = await target_coordinator.wrapper.get_thread(thread_id)
            return thread
        except Exception as err:
            raise ServiceValidationError(f"Failed to get thread: {err}")

    hass.services.async_register(
        DOMAIN, 
        "get_thread", 
        handle_get_thread,
        schema=vol.Schema({
            vol.Required("config_entry_id"): cv.string,
            vol.Required("thread_id"): cv.string,
        }),
        supports_response=SupportsResponse.ONLY
    )

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
