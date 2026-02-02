"""Coordinator for gogcli."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_GOG_PATH, CONF_CONFIG_DIR, CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL, DOMAIN
from .utils import GogWrapper

_LOGGER = logging.getLogger(__name__)

class GogGmailCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Gmail data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        polling_interval = entry.options.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
        if polling_interval < 5:
            polling_interval = 5

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=polling_interval),
        )
        self.entry = entry
        
        gog_path = entry.data[CONF_GOG_PATH]
        config_dir = entry.data[CONF_CONFIG_DIR]
        self.wrapper = GogWrapper(gog_path, config_dir)

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            # Fetch 5 newest messages from INBOX
            messages = await self.wrapper.search_messages("label:INBOX", limit=5, include_body=True)
            
            # Fetch threads in parallel
            async def _fetch_thread(message):
                try:
                    thread = await self.wrapper.get_thread(message['threadId'])
                    message['_thread'] = thread
                except Exception as e:
                    _LOGGER.warning("Failed to fetch thread %s: %s", message.get('threadId'), e)
                    message['_thread'] = {}

            await asyncio.gather(*[_fetch_thread(msg) for msg in messages])

            return messages
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
