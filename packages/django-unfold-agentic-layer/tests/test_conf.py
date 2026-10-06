from django_unfold_agentic_layer.conf import DEFAULTS, Settings, SettingsDict, get_config


def test_settings_enum_and_typed_dict_share_the_same_keys():
    assert SettingsDict.__optional_keys__ == set(Settings)


def test_every_setting_has_a_default():
    assert all(setting_key in DEFAULTS for setting_key in Settings)


def test_get_config_returns_defaults_untouched():
    assert get_config() == DEFAULTS


def test_get_config_merges_user_overrides(settings):
    settings.UNFOLD_AGENTIC_LAYER = {"PORTAL_TITLE": "Custom Title"}

    assert get_config()[Settings.PORTAL_TITLE] == "Custom Title"
