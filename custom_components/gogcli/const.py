"""Constants for the gogcli integration."""

DOMAIN = "gogcli"

CONF_GOG_PATH = "gog_path"
CONF_ACCOUNT = "account"
CONF_CONFIG_DIR = "config_dir"
CONF_CREDENTIALS_FILE = "credentials_file"
CONF_AUTH_CODE = "auth_code"
CONF_POLLING_INTERVAL = "polling_interval"

DEFAULT_GOG_PATH = "gog"
GOG_YAML_CONFIG = "gogcli.yaml"
DEFAULT_POLLING_INTERVAL = 5

DASHBOARD_CARD_YAML = """type: markdown
content: >
  {{% set prefix = '{prefix}' %}}
  <table style="width: 100%; border-collapse: collapse; border: none;">
    {{% for i in range(1, 6) %}}
      {{% set sensor = 'sensor.' ~ prefix ~ '_gmail_email_' ~ i %}}
      {{% if states(sensor) not in ['unknown', 'unavailable', 'Empty'] %}}
      <tr style="border: none;">
        <td style="width: 30px; text-align: center;">
          {{% if state_attr(sensor, 'priority') %}}❗{{% endif %}}
        </td>
        <td style="width: 30px; text-align: center;">
          {{% if state_attr(sensor, 'starred') %}}⭐{{% endif %}}
        </td>
        <td style="width: 30px; text-align: center;">
          {{% if state_attr(sensor, 'is_unread') %}}✉️{{% else %}}📑{{% endif %}}
        </td>
        <td style="width: 30px; text-align: center;">
          {{% if state_attr(sensor, 'have_replied') %}}↩️{{% endif %}}
        </td>
        <td>
          {{{{ states(sensor) }}}}
        </td>
      </tr>
      {{% endif %}}
    {{% endfor %}}
  </table>
  {{% set last_update = 'sensor.' ~ prefix ~ '_gmail_last_update' %}}
  {{% if states(last_update) not in ['unknown', 'unavailable', 'None'] %}}
  <div style="text-align: right; margin-top: 10px; font-size: 0.8em; color: var(--secondary-text-color);">
    Last updated: {{{{ relative_time(as_datetime(states(last_update))) }}}} ago
  </div>
  {{% endif %}}
title: Recent Emails ({account})"""
