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
    prerequisites = block_between(cb, "prerequisites = {", "\n\t}\n\n\twar_goal = mf_xiayi_conquest_wg")

    require(
        "has_country_flag = mf_xiayi_target" in prerequisites,
        "xiayi cb target prerequisites must check mf_xiayi_target on the target country.",
    )
    require(
        "tag = event_target:xiayi" in prerequisites,
        "xiayi cb target prerequisites must match event_target:xiayi.",
    )
    require(
        "FROM = {" not in prerequisites and "from = {" not in prerequisites,
        "xiayi cb target prerequisites must not wrap target checks in FROM scope.",
    )


def main():
    checks = [
        check_remove_natives_decision_removed,
        check_sankin_yearly_pulse_is_limited,
        check_flavor_jap_57_excludes_mod_subjects,
        check_private_daimyo_subjugation_does_not_raise_authority,
        check_xiayi_cb_target_scope_is_direct,
    ]
    for check in checks:
        check()
        print(f"PASS {check.__name__}")


if __name__ == "__main__":
    main()
