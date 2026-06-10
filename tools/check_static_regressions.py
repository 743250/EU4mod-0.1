from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path):
    return (ROOT / path).read_bytes().decode("latin-1")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def block_between(text, start, end):
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def find_matching_brace(text, open_index):
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError("unmatched brace")


def named_block(text, name):
    start = text.index(f"{name} = {{")
    brace = text.index("{", start)
    end = find_matching_brace(text, brace)
    return text[start:end + 1]


def custom_button_block(text, button_name):
    name_index = text.index(f"name = {button_name}")
    start = text.rfind("custom_button = {", 0, name_index)
    require(start != -1, f"custom button not found: {button_name}")
    brace = text.index("{", start)
    end = find_matching_brace(text, brace)
    return text[start:end + 1]


def check_remove_natives_decision_removed():
    decision_path = ROOT / "decisions" / "mf_remove_natives.txt"
    require(
        not decision_path.exists(),
        "decisions/mf_remove_natives.txt should not exist.",
    )

    decision_text = "\n".join(
        path.read_bytes().decode("latin-1")
        for path in (ROOT / "decisions").glob("*.txt")
    )
    forbidden = [
        "mf_remove_natives",
        "remove_natives",
        "移除土著",
        "去除土著",
    ]
    for pattern in forbidden:
        require(
            pattern not in decision_text,
            f"forbidden native-removal decision text remains: {pattern}",
        )


def check_sankin_yearly_pulse_is_limited():
    text = read_text("common/on_actions/mf_shogun_on_actions.txt")
    yearly = block_between(text, "on_yearly_pulse", "on_government_change")

    require(
        "has_country_modifier = shogun_yuling_b" in yearly,
        "yearly sankin pulse must require the Sankin Kotai edict.",
    )
    require(
        "every_subject_country" in yearly,
        "yearly sankin pulse must trigger through subject scopes.",
    )
    require(
        "every_country" not in yearly,
        "yearly sankin pulse must not scan every country.",
    )
    require(
        "id = mf_daimyo.10" in yearly,
        "yearly sankin pulse must still trigger mf_daimyo.10.",
    )


def check_flavor_jap_57_excludes_mod_subjects():
    text = read_text("events/flavorJAP.txt")
    event = block_between(text, "id = flavor_jap.57", "id = flavor_jap.58")
    require(
        "NOT = { is_subject_of_type = mf_daimyo_vassal }" in event,
        "flavor_jap.57 must exclude mf_daimyo_vassal.",
    )
    require(
        "NOT = { is_subject_of_type = mf_retainer_daimyo_vassal }" in event,
        "flavor_jap.57 must exclude mf_retainer_daimyo_vassal.",
    )


def check_private_daimyo_subjugation_does_not_raise_authority():
    text = read_text("common/peace_treaties/mf_daimyo_peace_treaties.txt")
    treaty = block_between(text, "po_mf_subjugate_daimyo = {", "po_mf_partition_daimyo = {")
    require(
        "mf_change_shogun_value" not in treaty,
        "private daimyo subjugation must not raise shogun authority.",
    )


def check_xiayi_cb_target_scope_is_direct():
    text = read_text("common/cb_types/00_cb_types.txt")
    cb = block_between(text, "cb_mf_xiayi_campaign = {", "# A HRE prince has been annexed")
    prerequisites_self = block_between(cb, "prerequisites_self = {", "\n\t}\n\n\tprerequisites = {")
    prerequisites = block_between(cb, "prerequisites = {", "\n\t}\n\n\twar_goal = mf_xiayi_conquest_wg")

    require(
        "has_reform = shogunate" not in prerequisites_self,
        "xiayi cb attacker gate must not double-lock has_reform = shogunate with tag = event_target:zhengyidajiangjun.",
    )
    require(
        "tag = event_target:zhengyidajiangjun" in prerequisites_self,
        "xiayi cb attacker must be the saved shogun event target.",
    )

    require(
        "has_country_flag = mf_xiayi_target" in prerequisites,
        "xiayi cb target prerequisites must check mf_xiayi_target on the target country.",
    )
    require(
        "tag = event_target:xiayi" in prerequisites,
        "xiayi cb target prerequisites must match event_target:xiayi.",
    )
    require(
        "FROM = {" in prerequisites,
        "xiayi cb target prerequisites must wrap target checks in FROM scope.",
    )
    for redundant in [
        "sort_of_mf = yes",
        "mf_tianhuang_target",
        "is_subject_of = event_target:zhengyidajiangjun",
    ]:
        require(
            redundant not in prerequisites,
            f"xiayi cb target prerequisites must not keep redundant blocker: {redundant}",
        )


def check_weixin_conditions_are_inline():
    gui = read_text("common/custom_gui/shogun_gui.txt")
    ai = read_text("decisions/mf_shogun_ai_decisions.txt")
    forbidden = [
        "mf_shogun_controls_japan_region = yes",
        "mf_shogun_controls_japan_region_except_hokkaido = yes",
        "mf_shogun_controls_hokkaido_area = yes",
        "mf_target_owns_hokkaido_province = yes",
        "mf_shogun_system_holds_province = yes",
        "is_empty = yes",
    ]

    for suffix in "abcdefghijkl":
        button = custom_button_block(gui, f"shogun_weixin.{suffix}")
        decision = named_block(ai, f"mf_ai_shogun_weixin_{suffix}")
        for pattern in forbidden:
            require(
                pattern not in button,
                f"shogun_weixin.{suffix} must not use scripted/empty reform condition: {pattern}",
            )
            require(
                pattern not in decision,
                f"mf_ai_shogun_weixin_{suffix} must not use scripted/empty reform condition: {pattern}",
            )

    for block_name, block in [
        ("shogun_weixin.i", custom_button_block(gui, "shogun_weixin.i")),
        ("mf_ai_shogun_weixin_i", named_block(ai, "mf_ai_shogun_weixin_i")),
    ]:
        require("japan_region = {" in block, f"{block_name} must inline japan_region control.")
        require("type = all" in block, f"{block_name} must check the whole japan_region.")
        for province_id in ["1031", "1032", "1847", "1852", "4193"]:
            require(
                f"province_id = {province_id}" in block,
                f"{block_name} must directly exclude Hokkaido province {province_id}.",
            )


def check_shouyexiayi_target_rules_are_direct():
    diplomacy = read_text("common/new_diplomatic_actions/mf_diplomatic_actions.txt")
    ai = read_text("decisions/mf_shogun_ai_decisions.txt")
    action = named_block(diplomacy, "shouyexiayi")
    ai_decision = named_block(ai, "mf_ai_shouyexiayi")

    for block_name, block in [
        ("shouyexiayi", action),
        ("mf_ai_shouyexiayi", ai_decision),
    ]:
        for pattern in ["sort_of_mf = yes", "mf_target_owns_hokkaido_province = yes"]:
            require(
                pattern not in block,
                f"{block_name} must not use old abstract xiayi target rule: {pattern}",
            )
        for province_id in ["1031", "1032", "1847", "1852", "4193"]:
            require(
                f"owns_or_non_sovereign_subject_of = {province_id}" in block,
                f"{block_name} must directly check Hokkaido province {province_id}.",
            )

    visible = block_between(action, "is_visible = {", "\n\t}\n\n\tis_allowed = {")
    allowed = block_between(action, "is_allowed = {", "\n\t}\n\n\ton_accept = {")
    require(
        "NOT = { has_country_flag = mf_xiayi_target }" in visible,
        "shouyexiayi must hide current xiayi target in is_visible.",
    )
    require(
        "has_country_flag = mf_xiayi_target" not in allowed,
        "shouyexiayi must not repeat current xiayi target check in is_allowed.",
    )
    require(
        "has_global_flag = shogun_weixin.f_global_flag" not in allowed,
        "shouyexiayi cooldown must not be bypassed by shogun_weixin.f_global_flag.",
    )


def check_ai_weixin_decisions_cover_all_buttons():
    text = read_text("decisions/mf_shogun_ai_decisions.txt")
    for suffix in "abcdefghijkl":
        name = f"mf_ai_shogun_weixin_{suffix}"
        flag = f"shogun_weixin.{suffix}_global_flag"
        require(
            name in text,
            f"AI weixin decision is missing: {name}.",
        )
        decision = named_block(text, name)
        require(
            f"set_global_flag = {flag}" in decision,
            f"{name} must set {flag}.",
        )
        require(
            "mf_change_shogun_value = { value = -70 }" in decision,
            f"{name} must spend 70 shogun authority like the UI button.",
        )

    for suffix in ["a", "b", "e"]:
        name = f"mf_ai_shogun_weixin_{suffix}"
        decision = named_block(text, name)
        require(
            "stability = 1" not in decision,
            f"{name} must not add stability requirements that the UI button does not have.",
        )

    f_decision = named_block(text, "mf_ai_shogun_weixin_f")
    f_count = block_between(f_decision, "calc_true_if = {", "\n\t\t\t}")
    require(
        "has_global_flag = shogun_weixin.i_global_flag" in f_count,
        "AI weixin f must count shogun_weixin.i_global_flag like the UI button.",
    )
    require(
        "has_global_flag = shogun_weixin.f_global_flag" not in f_count,
        "AI weixin f must not count its own flag.",
    )


def main():
    checks = [
        check_remove_natives_decision_removed,
        check_sankin_yearly_pulse_is_limited,
        check_flavor_jap_57_excludes_mod_subjects,
        check_private_daimyo_subjugation_does_not_raise_authority,
        check_xiayi_cb_target_scope_is_direct,
        check_weixin_conditions_are_inline,
        check_shouyexiayi_target_rules_are_direct,
        check_ai_weixin_decisions_cover_all_buttons,
    ]
    for check in checks:
        check()
        print(f"PASS {check.__name__}")


if __name__ == "__main__":
    main()
