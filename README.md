# gogcli for Home Assistant
<img src="https://raw.githubusercontent.com/jcdietrich/ha-gogcli/refs/heads/main/logo.png" width="100" />

This integration uses [gogcli](https://github.com/steipete/gogcli?tab=readme-ov-file) to currently allow you to:

  * Gmail
    * supports multiple accounts
    * monitor your Gmail inbox
    * provides sensors
      * get your recent emails, updating the sensors
      * retrieve thread details
    * provides yaml, on this page, to create a card for your dashboard
      showing info about your recent email

## Installation

1. Copy the `custom_components/gogcli` directory to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings > Devices & Services**.
4. Click **Add Integration** and search for "gogcli".
5. Follow the configuration steps to authenticate with your Google account.

## Services

### `gogcli.update_gmail`

Forces an update of the Gmail sensors. This is useful if you want to trigger a refresh outside of the configured polling interval.

**Parameters:**

| Name | Type | Description |
| :--- | :--- | :--- |
| `config_entry_ids` | `list` (Optional) | A list of configuration entry IDs to update. If omitted or empty, **all** configured accounts will be updated. |

**Example:**
```yaml
service: gogcli.update_gmail
data:
  config_entry_ids:
    - "01J4..."
```

### `gogcli.get_thread`

Retrieves metadata and message snippets for a specific email thread. This service supports return values.

**Parameters:**

| Name | Type | Description |
| :--- | :--- | :--- |
| `config_entry_id` | `string` (Required) | The configuration entry ID of the account the thread belongs to. |
| `thread_id` | `string` (Required) | The ID of the thread to retrieve (available in sensor attributes). |

**Return Value:**
Returns a JSON object containing the thread details, including messages and their snippets.

**Example:**
```yaml
service: gogcli.get_thread
data:
  config_entry_id: "01J4..."
  thread_id: "194..."
response_variable: thread_data
```

## Language Support

This integration is available in:
- English
- French
- Spanish

## Advanced Configuration

You can configure global settings for the underlying `gogcli` tool by creating a `gogcli.yaml` file in your Home Assistant configuration directory (where your `configuration.yaml` lives).

**Example `gogcli.yaml`:**
```yaml
default_timezone: "Europe/Paris"
```

The integration will automatically sync this configuration to the tool whenever Home Assistant starts or the integration is reloaded.
