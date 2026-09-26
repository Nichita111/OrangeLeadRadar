"""[Plug-in availability](/architecture/rules.md#plug-in-availability): whether a source plug-in
may make a request now. The plug-ins that need a key are the "Needs a key" column of the
[`source_plugin`](/architecture/sql-store.md#source_plugin) plug-in values table."""

from __future__ import annotations

from leadradar.core.enums import SourcePluginCode

PLUGINS_NEEDING_A_KEY = frozenset(
    {SourcePluginCode.CRUNCHBASE, SourcePluginCode.NEWSAPI, SourcePluginCode.SERPAPI}
)


def is_plugin_available(
    *,
    code: SourcePluginCode,
    enabled: bool,
    key_configured: bool,
    requests_today: int,
    daily_quota: int | None,
) -> bool:
    """Available: `enabled`, its key configured if it needs one, and today's requests below
    `daily_quota` when a quota is set."""
    if not enabled:
        return False
    if code in PLUGINS_NEEDING_A_KEY and not key_configured:
        return False
    return daily_quota is None or requests_today < daily_quota
