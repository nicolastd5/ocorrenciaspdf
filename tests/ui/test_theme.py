from ui import theme


def test_dark_tokens_have_all_keys():
    required = {"bg", "surface", "surface_alt", "border", "fg",
                "fg_bright", "fg_dim", "success", "success_hover",
                "accent", "warning", "danger"}
    assert required <= set(theme.DARK_TOKENS.keys())
    assert required <= set(theme.LIGHT_TOKENS.keys())


def test_qss_for_dark_uses_dark_bg():
    qss = theme.qss_for("dark")
    assert theme.DARK_TOKENS["bg"] in qss


def test_qss_for_light_uses_light_bg():
    qss = theme.qss_for("light")
    assert theme.LIGHT_TOKENS["bg"] in qss


def test_qss_for_invalid_mode_defaults_to_dark():
    assert theme.qss_for("xyz") == theme.qss_for("dark")
