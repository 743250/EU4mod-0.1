import re
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


def last_named_block(text, name):
    start = text.rindex(f"{name} = {{")
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
        "NOT = { has_global_flag = shogun_weixin.h_global_flag }" in yearly,
        "yearly sankin pulse must stop after reform 5 is enacted.",
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


def check_sankin_formula_and_ai_weights():
    event_text = read_text("events/mf_daimyo_event.txt")
    event = block_between(event_text, "id = mf_daimyo.10", "id = mf_daimyo.12")
    require(re.search(r"export_to_variable\s*=\s*\{\s*variable_name\s*=\s*mf_sankin_fixed_cost\s*value\s*=\s*total_development", event), "sankin fixed cost must export total development.")
    require(re.search(r"divide_variable\s*=\s*\{\s*which\s*=\s*mf_sankin_fixed_cost\s*value\s*=\s*5", event), "sankin fixed cost must divide total development by five.")
    require(re.search(r"export_to_variable\s*=\s*\{\s*variable_name\s*=\s*mf_sankin_distance_multiplier\s*value\s*=\s*capital_distance\s*who\s*=\s*event_target:zhengyidajiangjun", event), "sankin distance must target the shogun rather than a retainer's direct overlord.")
    require(re.search(r"divide_variable\s*=\s*\{\s*which\s*=\s*mf_sankin_distance_multiplier\s*value\s*=\s*12", event), "sankin distance must be divided by twelve.")
    require(re.search(r"set_variable\s*=\s*\{\s*which\s*=\s*mf_sankin_distance_multiplier\s*value\s*=\s*3", event), "sankin distance multiplier must be capped at three.")
    require(re.search(r"export_to_variable\s*=\s*\{\s*variable_name\s*=\s*mf_sankin_year_cost\s*value\s*=\s*years_of_income", event), "sankin yearly cost must export one year of income.")
    require(re.search(r"divide_variable\s*=\s*\{\s*which\s*=\s*mf_sankin_year_cost\s*value\s*=\s*3", event), "sankin yearly cost must divide yearly income by three.")
    require(re.search(r"multiply_variable\s*=\s*\{\s*which\s*=\s*mf_sankin_year_cost\s*which\s*=\s*mf_sankin_distance_multiplier", event), "sankin yearly cost must multiply income by the distance multiplier.")
    require(re.search(r"set_variable\s*=\s*\{\s*which\s*=\s*mf_sankin_cost\s*which\s*=\s*mf_sankin_fixed_cost", event), "sankin total cost must start from the fixed cost.")
    require(re.search(r"change_variable\s*=\s*\{\s*which\s*=\s*mf_sankin_cost\s*which\s*=\s*mf_sankin_year_cost", event), "sankin total cost must add the yearly cost.")
    require("province_distance" not in event, "sankin cost must not keep province-distance threshold checks.")
    require("mf_sankin_fixed_cost" in event, "sankin cost must keep the development-based fixed cost separate.")
    require("mf_sankin_distance_multiplier" in event, "sankin cost must cap the distance multiplier explicitly.")
    require("mf_sankin_year_cost" in event, "sankin cost must still deduct yearly income.")
    require("year_treasury_reduce" not in event, "sankin event must not deduct yearly income a second time after calculating the total.")
    require(event.count("treasury_reduce") == 1, "sankin event must deduct the combined total exactly once.")
    require("mf_refuse_sankin_kotai_effect = yes" in event, "refusing sankin must use the shared refusal effect.")
    effects = read_text("common/scripted_effects/mf_shogun_reform_effects.txt")
    refusal = named_block(effects, "mf_refuse_sankin_kotai_effect")
    require("add_prestige = 10" in refusal, "refusing sankin must award prestige.")
    require("name = mf_sankin_kotai_refused" in refusal and "duration = 365" in refusal, "refusing sankin must apply only the one-year refusal modifier.")
    require("mf_change_shogun_value = { value = -0.5 }" in refusal, "refusing sankin must lower shogun authority by point five.")
    require("mf_refused_sankin_kotai" not in refusal, "refusing sankin must not set a persistent refusal flag.")
    require("add_casus_belli" not in refusal and "cb_disloyal_vassal" not in refusal, "refusing sankin must not grant a punishment cb.")
    require("country_event" not in refusal, "refusing sankin must not trigger a follow-up punishment event.")
    require("id = mf_daimyo.11" not in event_text, "the obsolete sankin-refusal punishment event must be removed.")
    require(event.count("\n\toption = {") == 2, "sankin event must contain exactly one accept option and one refusal option.")
    require(event.count('name = "mf_daimyo.10.a"') == 1, "sankin event must contain exactly one accept option.")
    require(event.count('name = "mf_daimyo.10.b"') == 1, "sankin event must contain exactly one refusal option.")
    require("factor = 0.2" in event and "factor = 0.1" in event, "accept chance must carry the liberty and loan multipliers.")
    require(event.count("mf_refuse_sankin_kotai_effect = yes") == 1, "the single refusal option must call the shared refusal effect once.")
    require("num_of_loans = 10" in event, "ten loans must force refusal.")


def check_sankin_reform_closes_temporary_edict():
    gui = read_text("common/custom_gui/shogun_gui.txt")
    event_text = read_text("events/mf_daimyo_event.txt")
    ai_events = read_text("events/mf_shogun_ai_events.txt")
    ai_decisions = read_text("decisions/mf_shogun_ai_decisions.txt")
    effects = read_text("common/scripted_effects/mf_shogun_reform_effects.txt")
    diplomatic_actions = read_text("common/new_diplomatic_actions/mf_diplomatic_actions.txt")
    missions = read_text("missions/mf_shogun_missions.txt")
    alliance_actions = read_text("common/diplomatic_actions/00_diplomatic_actions.txt")
    modifiers = read_text("common/event_modifiers/shogun_weixin_modifiers.txt")
    sankin_button = custom_button_block(gui, "shogun_yuling.b")
    sankin_reform = custom_button_block(gui, "shogun_weixin.h")
    ai_option = block_between(ai_events, 'name = "shogun_yuling.b_title"', 'name = "shogun_yuling.c_title"')
    ai_reform = named_block(ai_decisions, "mf_ai_shogun_weixin_h")
    formal_effect = named_block(effects, "mf_complete_sankin_reform_effect")
    cleanup_effect = named_block(effects, "mf_end_sankin_event_state_effect")
    alliance_action = named_block(alliance_actions, "allianceaction")
    formal_modifier = named_block(modifiers, "jiujizhengshi_2")

    require(
        "NOT = { has_global_flag = shogun_weixin.h_global_flag }" in sankin_button,
        "temporary sankin edict button must be hidden after reform 5.",
    )
    require("mf_complete_sankin_reform_effect = yes" in sankin_reform, "the player reform button must call the shared completion effect.")
    require("mf_complete_sankin_reform_effect = yes" in ai_reform, "the AI reform decision must call the shared completion effect.")
    require("remove_country_modifier = shogun_yuling_b" in formal_effect, "reform 5 must clear the temporary sankin edict modifier.")
    require("remove_country_modifier = mf_sankin_kotai_began" in formal_effect, "reform 5 must clear the legacy sankin stage modifier too.")
    require("mf_end_sankin_event_state_effect = yes" in formal_effect, "formal reform must end direct and second-layer daimyo event states.")
    require("remove_country_modifier = mf_sankin_kotai_refused" in cleanup_effect, "formal reform must clear refusal modifiers.")
    require("remove_country_modifier = mf_sankin_kotai_travel" in cleanup_effect, "formal reform must clear active sankin travel modifiers.")
    require("break_alliance = PREV" in cleanup_effect, "formal reform must break existing daimyo alliances.")
    require("name = jiujizhengshi_2" in formal_effect, "formal reform must immediately grant the shogun modifier.")
    require("liberty_desire_from_subject_development = -0.20" in formal_modifier, "formal sankin modifier must lower subject-development liberty desire by twenty percent.")
    require("mf_sankin_reform_daimyo_alliance_forbidden_tt" in alliance_action, "formal reform must block daimyo alliances through allianceaction.")
    require("has_global_flag = shogun_weixin.h_global_flag" in alliance_action, "the daimyo alliance ban must start only after the formal reform.")
    require("mf_enforce_sankin_kotai = {" not in diplomatic_actions, "forced sankin diplomatic action must be removed.")
    require("mf_shogun_punish_sankin_refusal = {" not in missions, "forced sankin punishment mission must be removed.")
    require("mf_refused_sankin_kotai" not in effects + diplomatic_actions + event_text, "persistent sankin-refusal flags must not remain in functional scripts.")
    for obsolete_key in ["mf_shogun_forced_sankin_kotai", "mf_shogun_sankin_punishment_upgraded"]:
        require(obsolete_key not in diplomatic_actions + missions + effects, f"obsolete forced sankin key must be removed: {obsolete_key}")
    require(
        "NOT = { has_global_flag = shogun_weixin.h_global_flag }" in ai_option,
        "AI sankin edict selection must stop once reform 5 is enacted.",
    )


def check_flavor_jap_57_is_removed():
    text = read_text("events/flavorJAP.txt")
    require(
        "id = flavor_jap.57" not in text,
        "flavor_jap.57 must be removed from the mod override.",
    )


def check_private_daimyo_subjugation_does_not_raise_authority():
    text = read_text("common/peace_treaties/00_mf_subjugate_daimyo.txt")
    treaty = text
    require(
        "mf_change_shogun_value" not in treaty,
        "private daimyo subjugation must not raise shogun authority.",
    )


def check_xiayi_cb_is_granted_explicitly():
    text = read_text("common/cb_types/00_cb_types.txt")
    cb = named_block(text, "cb_mf_xiayi_campaign")
    require("is_triggered_only = yes" in cb, "xiayi cb must be granted explicitly.")
    require("prerequisites_self" not in cb, "xiayi cb must not wait for attacker prerequisite refresh.")
    require("prerequisites =" not in cb, "xiayi cb must not wait for target prerequisite refresh.")

    effects = read_text("common/scripted_effects/mf_shogun_ai_effects.txt")
    set_target = named_block(effects, "mf_set_xiayi_campaign_target_effect")
    require("add_casus_belli = {" in set_target, "setting xiayi must immediately add its cb.")
    require("type = cb_mf_xiayi_campaign" in set_target, "setting xiayi must add the real cb key.")
    require("target = ROOT" in set_target, "setting xiayi must target the selected country.")

    daimyo_effects = read_text("common/scripted_effects/mf_daimyo_efx.txt")
    refresh = named_block(daimyo_effects, "mf_refresh_shogun_leader_target_effect")
    require("type = cb_mf_xiayi_campaign" in refresh, "a new shogun must receive the current xiayi cb.")


def check_governance_cb_actions_and_peace_treaties():
    diplomacy = read_text("common/new_diplomatic_actions/mf_diplomatic_actions.txt")
    for action_name, cb_type in [
        ("mf_excommunicate_daimyo", "cb_mf_shogunate_excommunication"),
        ("mf_return_daimyo_land", "cb_mf_return_daimyo_land"),
    ]:
        action = named_block(diplomacy, action_name)
        require("add_casus_belli = {" in action, f"{action_name} must grant a cb.")
        require(f"type = {cb_type}" in action, f"{action_name} must grant {cb_type}.")
        require("target = FROM" in action, f"{action_name} must target the selected daimyo.")
    excommunicate = named_block(diplomacy, "mf_excommunicate_daimyo")
    require(
        "mf_change_shogun_value = {" in excommunicate,
        "excommunication must raise shogun authority.",
    )
    require(
        "value = 2" in excommunicate,
        "excommunication must use the agreed authority gain.",
    )
    require(
        excommunicate.count("mf_change_shogun_value = {") == 1,
        "excommunication must raise authority exactly once.",
    )
    modifiers = read_text("common/event_modifiers/mf_daimyo_modifires.txt")
    excommunication_modifier = named_block(modifiers, "mf_shogunate_excommunication")
    require(
        "can_not_declare_war = yes" in excommunication_modifier,
        "an excommunicated daimyo must not be able to declare war.",
    )


def check_reform_governance_actions():
    diplomacy = read_text("common/new_diplomatic_actions/mf_diplomatic_actions.txt")
    province_return = named_block(diplomacy, "mf_return_shogunate_province")
    require("has_global_flag = shogun_weixin.b_global_flag" in province_return, "province return must require reform 2.")
    require("has_province_flag = mf_shogunate_province" in province_return, "province return must require a registered province.")
    require("mf_pick_returnable_shogunate_province_effect = yes" in province_return, "province return must use the shared target picker.")

    subject_transfer = named_block(diplomacy, "mf_transfer_illegal_subject")
    require("has_global_flag = shogun_weixin.c_global_flag" in subject_transfer, "subject transfer must require reform 3.")
    require("require_acceptance = no" in subject_transfer, "the shogun must directly choose the lower subject to release.")
    require("subject = FROM" in subject_transfer, "the selected diplomatic target must be the released subject.")
    require("random_subject_country" not in subject_transfer, "subject transfer must not randomly choose another country.")
    require("subject_type = daimyo_vassal" in subject_transfer, "transferred subject must become a direct ordinary daimyo.")
    require("mf_change_shogun_value = { value = 2 }" in subject_transfer, "accepted transfer must raise authority by 2.")

    combined = read_text("common/peace_treaties/00_mf_subjugate_daimyo.txt")
    treaty_files = {
        "po_mf_partition_daimyo": "common/peace_treaties/00_mf_partition_daimyo.txt",
        "po_mf_enforce_executor_appointment": "common/peace_treaties/00_mf_enforce_executor_appointment.txt",
        "po_mf_enforce_shogunate_obedience": "common/peace_treaties/00_mf_enforce_shogunate_obedience.txt",
    }
    wargoals = read_text("common/wargoal_types/mf_wargoal_types.txt")
    for treaty_name, treaty_path in treaty_files.items():
        require(treaty_name not in combined, f"{treaty_name} must not remain behind the first treaty in a combined file.")
        path = ROOT / treaty_path
        require(path.exists(), f"missing standalone peace treaty file: {treaty_path}")
        treaty_text = path.read_bytes().decode("latin-1").strip()
        require(treaty_text.startswith(f"{treaty_name} = {{"), f"{treaty_path} must define {treaty_name} first.")
        require(named_block(treaty_text, treaty_name).strip() == treaty_text, f"{treaty_path} must contain one top-level treaty.")
        require(treaty_name in wargoals, f"wargoals must reference {treaty_name}.")


def check_executor_presence_checks_are_direct():
    diplomacy = read_text("common/new_diplomatic_actions/mf_diplomatic_actions.txt")
    action = named_block(diplomacy, "mf_appoint_executor_daimyo")
    treaty = read_text("common/peace_treaties/00_mf_enforce_executor_appointment.txt")
    for block_name, block in [
        ("mf_appoint_executor_daimyo", action),
        ("po_mf_enforce_executor_appointment", treaty),
    ]:
        require(
            "any_subject_country = {" in block,
            f"{block_name} must directly check whether an executor subject exists.",
        )
        require(
            "calc_true_if = {" not in block,
            f"{block_name} must not count one executor and then negate the count.",
        )


def check_sengoku_cb_is_disabled_by_reform_five():
    text = read_text("common/cb_types/00_cb_types.txt")
    cb = named_block(text, "cb_sengoku")
    require(
        "NOT = { has_global_flag = shogun_weixin.h_global_flag }" in cb,
        "sengoku CB must be disabled once reform 5 is enacted.",
    )
    require(
        "has_country_modifier = jap_sengoku_jidai" in cb,
        "sengoku CB must still require the sengoku-jidai modifier.",
    )


def check_internal_war_ban_scope():
    text = read_text("common/diplomatic_actions/00_diplomatic_actions.txt")
    declarewar = block_between(text, "declarewar = {", "allianceaction = {")
    require("sort_of_mf = yes" in declarewar, "declarewar ban must require a shogunate-identity attacker.")
    require(
        declarewar.count("is_subject_of = event_target:zhengyidajiangjun") >= 3,
        "declarewar ban must recognize direct and second-layer shogunate members.",
    )
    require(
        "FROM = { overlord_of = ROOT }" in declarewar,
        "declarewar ban must still permit independence wars against the overlord.",
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
        region = named_block(block, "japan_region")
        require("type = all" not in region, f"{block_name} must use the direct japan_region province scope.")
        require("NOT = {" in region, f"{block_name} must exclude Hokkaido in province scope.")
        require("area = hokkaido_area" in region, f"{block_name} must exclude Hokkaido by area.")
        require(
            "owned_by = ROOT" in region,
            f"{block_name} must require ROOT to own every selected province.",
        )
        for pattern in ["OR = {", "country_or_non_sovereign_subject_holds", "owner = {"]:
            require(pattern not in region, f"{block_name} must not keep the old control branch: {pattern}")
        for province_id in ["1031", "1032", "1847", "1852", "4193"]:
            require(
                f"province_id = {province_id}" not in region,
                f"{block_name} must not hard-code Hokkaido province {province_id}.",
            )


def check_weixin_relationship_trigger_and_gui_tail():
    gui = read_text("common/custom_gui/shogun_gui.txt")
    ai = read_text("decisions/mf_shogun_ai_decisions.txt")
    reform_e_blocks = [
        ("shogun_weixin.e", custom_button_block(gui, "shogun_weixin.e")),
        ("mf_ai_shogun_weixin_e", named_block(ai, "mf_ai_shogun_weixin_e")),
    ]

    for block_name, block in reform_e_blocks:
        require(
            "has_opinion = {" in block,
            f"{block_name} must use the valid has_opinion trigger.",
        )
        require(
            re.search(r"(?m)^[ \t]*opinion\s*=\s*\{", block) is None,
            f"{block_name} must not use the invalid bare opinion trigger.",
        )

    for suffix in "fghijkl":
        custom_button_block(gui, f"shogun_weixin.{suffix}")
    for gui_tail_name in [
        "name = shogun_weixin_gunlun.a",
        "name = shogun_weixin_gunlun.d",
        "name = shogun_daming_refresh",
        "name = shogun_daming_1",
        "name = shogun_daming_30",
    ]:
        require(gui_tail_name in gui, f"GUI tail definition is missing: {gui_tail_name}")


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
        if suffix == "h":
            require(
                "mf_complete_sankin_reform_effect = yes" in decision,
                "mf_ai_shogun_weixin_h must use the shared formal sankin completion effect.",
            )
            continue
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


def check_weixin_page_flag_nots_are_grouped():
    gui = read_text("common/custom_gui/shogun_gui.txt")
    separate_nots = re.compile(
        r"NOT\s*=\s*\{\s*has_country_flag\s*=\s*weixin_page_2\s*\}"
        r"\s*NOT\s*=\s*\{\s*has_country_flag\s*=\s*weixin_page_3\s*\}"
    )
    grouped_nots = re.compile(
        r"NOT\s*=\s*\{\s*has_country_flag\s*=\s*weixin_page_2"
        r"\s*has_country_flag\s*=\s*weixin_page_3\s*\}"
    )
    require(not separate_nots.search(gui), "weixin page flags must not use adjacent single-condition NOT blocks.")
    require(len(grouped_nots.findall(gui)) >= 9, "weixin first-page selectors must group both absent flags in one NOT block.")


def check_gui_default_country_scope_is_direct():
    gui = read_text("common/custom_gui/shogun_gui.txt")
    redundant_root = re.compile(
        r"ROOT\s*=\s*\{\s*tag\s*=\s*event_target:zhengyidajiangjun\s*\}"
    )
    require(not redundant_root.search(gui), "GUI country triggers must not re-enter ROOT only to check the shogun tag.")
    require(
        gui.count("tag = event_target:zhengyidajiangjun") >= 22,
        "GUI shogun gates must remain as direct tag checks in the default country scope.",
    )
    for suffix in ["b", "f", "g", "h"]:
        button = custom_button_block(gui, f"shogun_weixin.{suffix}")
        require(
            "event_target:zhengyidajiangjun = {" not in button,
            f"shogun_weixin.{suffix} must not re-enter the current shogun through its event target.",
        )


def check_gui_scripted_element_types_match():
    gui = read_text("common/custom_gui/shogun_gui.txt")
    topbar = read_text("interface/topbar.gui")

    def has_direct_scripted_flag(block):
        depth = 0
        for line in block.splitlines()[1:-1]:
            code = line.split("#", 1)[0]
            if depth == 0 and re.fullmatch(r"\s*scripted\s*=\s*yes\s*", code):
                return True
            depth += code.count("{") - code.count("}")
        return False

    definition_types = {}
    for definition_type in ["custom_window", "custom_button", "custom_shield", "custom_icon", "custom_text_box"]:
        for match in re.finditer(rf"(?m)^{definition_type}\s*=\s*\{{", gui):
            brace = gui.index("{", match.start())
            block = gui[match.start():find_matching_brace(gui, brace) + 1]
            name_match = re.search(r"(?m)^\s*name\s*=\s*([^\s#]+)", block)
            require(name_match is not None, f"{definition_type} definition is missing its name.")
            name = name_match.group(1).strip('"')
            require(name not in definition_types, f"duplicate custom GUI definition: {name}")
            definition_types[name] = definition_type

    allowed_types = {
        "windowType": {"custom_window"},
        "instantTextBoxType": {"custom_text_box"},
        "iconType": {"custom_icon"},
        "guiButtonType": {"custom_button", "custom_shield"},
    }
    scripted_gui_types = {}
    for gui_type, allowed_definitions in allowed_types.items():
        for match in re.finditer(rf"(?m)^[ \t]*{gui_type}\s*=\s*\{{", topbar):
            brace = topbar.index("{", match.start())
            block = topbar[match.start():find_matching_brace(topbar, brace) + 1]
            if not has_direct_scripted_flag(block):
                continue
            name_match = re.search(r'(?m)^[ \t]*name\s*=\s*"([^\"]+)"', block)
            require(name_match is not None, f"scripted {gui_type} is missing its name.")
            name = name_match.group(1)
            require(name not in scripted_gui_types, f"duplicate scripted GUI control: {name}")
            scripted_gui_types[name] = gui_type
            require(
                definition_types.get(name) in allowed_definitions,
                f"{gui_type} {name} must use one of the matching definitions: {sorted(allowed_definitions)}.",
            )

    allowed_gui_types = {
        "custom_window": {"windowType"},
        "custom_text_box": {"instantTextBoxType"},
        "custom_icon": {"iconType"},
        "custom_button": {"guiButtonType"},
        "custom_shield": {"guiButtonType"},
    }
    for name, definition_type in definition_types.items():
        require(
            scripted_gui_types.get(name) in allowed_gui_types[definition_type],
            f"{definition_type} {name} must have a matching scripted GUI control.",
        )


def check_shogun_gui_visibility_chain():
    gui = read_text("common/custom_gui/shogun_gui.txt")

    def custom_gui_block(definition_type, name):
        name_index = gui.index(f"name = {name}")
        start = gui.rfind(f"{definition_type}  = {{", 0, name_index)
        if start == -1:
            start = gui.rfind(f"{definition_type} = {{", 0, name_index)
        require(start != -1, f"custom GUI definition not found: {name}")
        brace = gui.index("{", start)
        return gui[start:find_matching_brace(gui, brace) + 1]

    launcher = custom_gui_block("custom_window", "shogun_button_gui_window")
    main_window = custom_gui_block("custom_window", "shogun_gui_window")
    toggle = custom_button_block(gui, "enable_shogun_gui")
    require("has_discovered = 1818" in launcher, "shogun GUI launcher must remain visible to countries that know Japan.")
    require(
        re.search(r"ROOT\s*=\s*\{\s*has_discovered\s*=\s*1818\s*\}", launcher) is not None,
        "shogun GUI launcher window must enter ROOT to test the player country's discovery state.",
    )
    require("has_country_flag = shogun_gui_window_open" in main_window, "shogun GUI main window must use its open flag.")
    require("set_country_flag = shogun_gui_window_open" in toggle, "shogun GUI toggle must open the main window.")
    require("clr_country_flag = shogun_gui_window_open" in toggle, "shogun GUI toggle must close the main window.")


def check_shogun_gui_refresh_is_event_driven():
    on_actions = read_text("common/on_actions/mf_shogun_on_actions.txt")
    old_refresh = read_text("common/scripted_effects/BL_shougun_effect.txt")
    cleanup = read_text("common/scripted_effects/mf_shogun_ui_effects.txt")
    monthly = named_block(on_actions, "on_monthly_pulse")
    refresh = named_block(old_refresh, "bl_shogun_refresh")
    require("bl_shogun_refresh = yes" not in monthly, "monthly pulse must not rebuild the shogun GUI daimyo list.")
    require(
        "mf_clear_shogun_daimyo_targets_effect = yes" in refresh,
        "bl_shogun_refresh must call the guarded daimyo-target cleanup effect.",
    )
    for index in range(1, 31):
        target = f"shogun_daming_{index}"
        guarded_cleanup = re.compile(
            rf"if\s*=\s*\{{\s*limit\s*=\s*\{{\s*has_saved_global_event_target\s*=\s*{target}\s*\}}\s*"
            rf"clear_global_event_target\s*=\s*{target}\s*\}}"
        )
        require(guarded_cleanup.search(cleanup) is not None, f"{target} must only be cleared when it exists.")


def check_daimyo_identity_boundaries():
    reforms = read_text("common/government_reforms/mf_government_reforms_monarchies.txt")
    daimyo = named_block(reforms, "daimyo")
    daimyo_potential = named_block(daimyo, "potential")
    mf_daimyo = named_block(reforms, "mf_daimyo")
    mf_daimyo_potential = named_block(mf_daimyo, "potential")
    indep_daimyo = named_block(reforms, "indep_daimyo")
    indep_daimyo_potential = named_block(indep_daimyo, "potential")
    for subject_type in ["daimyo_vassal", "mf_retainer_daimyo_vassal"]:
        require(
            f"is_subject_of_type = {subject_type}" in daimyo_potential,
            f"daimyo reform potential must directly allow {subject_type}.",
        )
    require(
        "overlord = {" not in daimyo_potential,
        "daimyo reform potential must use the exact subject types instead of guessing from the overlord reform.",
    )
    require("is_subject_of_type = mf_daimyo_vassal" in mf_daimyo_potential, "fudai reform must require its subject type.")
    require("has_reform = shogunate" in mf_daimyo_potential, "fudai reform must require a shogunate overlord.")
    for independent_gate in ["is_subject = no", "is_subject_of_type = tributary_state"]:
        require(
            independent_gate in indep_daimyo_potential,
            f"indep_daimyo reform must keep its global subject gate: {independent_gate}.",
        )
    for substantive_subject in ["daimyo_vassal", "mf_daimyo_vassal", "mf_retainer_daimyo_vassal"]:
        require(
            f"is_subject_of_type = {substantive_subject}" not in indep_daimyo_potential,
            f"indep_daimyo must not allow substantive subject type {substantive_subject}.",
        )

    subject_types = read_text("common/subject_types/mf_subject_types.txt")
    retainer = last_named_block(subject_types, "mf_retainer_daimyo_vassal")
    potential_overlord = named_block(retainer, "is_potential_overlord")
    require("sort_of_mf = yes" in potential_overlord, "retainer overlord must be any shogunate-system country.")
    require("NOT = { has_reform = shogunate }" not in potential_overlord, "the shogun must remain a legal retainer overlord.")

    effects = read_text("common/scripted_effects/mf_daimyo_efx.txt")
    hierarchy = named_block(effects, "mf_promote_retainer_daimyos_to_shogunate_effect")
    require(
        "subject_type = daimyo_vassal" not in hierarchy,
        "hierarchy refresh must not convert a direct shogun retainer into an outside daimyo.",
    )
    normalize = named_block(effects, "mf_normalize_daimyo_first_layer_reform_effect")
    for reform in ["mf_daimyo", "daimyo", "indep_daimyo"]:
        require(f"add_government_reform = {reform}" in normalize, f"normalization must add {reform} for its exact identity.")
    require("is_subject = no" in normalize, "normalization must recognize a truly independent daimyo.")
    require("is_subject_of_type = tributary_state" in normalize, "normalization must preserve tributary indep_daimyo.")


def check_reform_localization_keys():
    localization = "\n".join(
        path.read_bytes().decode("latin-1")
        for path in (ROOT / "localisation").glob("*.yml")
    )
    required = [
        "mf_register_shogunate_provinces_title",
        "mf_register_shogunate_provinces_desc",
        "mf_return_shogunate_province",
        "mf_return_shogunate_province_tooltip",
        "mf_transfer_illegal_subject",
        "mf_transfer_illegal_subject_tooltip",
        "mf_shogunate_internal_war_forbidden_tt",
        "cb_mf_shogunate_japan_campaign",
        "cb_mf_shogunate_japan_campaign_desc",
        "mf_daimyo.10.formula.d",
        "mf_daimyo.10.formula.a.tt",
        "mf_daimyo.10.formula.b.tt",
        "shogun_yuling_x_b_formula.tt",
        "shogun_weixin.h.formal.a.tt",
        "mf_sankin_reform_daimyo_alliance_forbidden_tt",
    ]
    for key in required:
        require(f" {key}:" in localization, f"missing reform localization key: {key}")


def check_vanilla_modifier_names():
    modifiers = read_text("common/event_modifiers/shogun_weixin_modifiers.txt")
    preparation = named_block(modifiers, "mf_ezo_campaign_preparation")
    require(
        re.search(r"(?m)^[ \t]*army_tradition\s*=\s*1\s*$", preparation) is not None,
        "mf_ezo_campaign_preparation must use the vanilla army_tradition modifier.",
    )
    require(
        "yearly_army_tradition" not in preparation,
        "mf_ezo_campaign_preparation must not use the invalid yearly_army_tradition modifier.",
    )


def check_ai_shogun_event_has_picture():
    events = read_text("events/mf_shogun_ai_events.txt")
    event = block_between(events, "id = mf_shogun_ai.1", "\n}")
    require(
        re.search(r"(?m)^\s*picture\s*=\s*[^\s#]+", event) is not None,
        "mf_shogun_ai.1 must define a picture like vanilla country events.",
    )


def main():
    checks = [
        check_remove_natives_decision_removed,
        check_sankin_yearly_pulse_is_limited,
        check_sankin_formula_and_ai_weights,
        check_sankin_reform_closes_temporary_edict,
        check_flavor_jap_57_is_removed,
        check_private_daimyo_subjugation_does_not_raise_authority,
        check_xiayi_cb_is_granted_explicitly,
        check_governance_cb_actions_and_peace_treaties,
        check_executor_presence_checks_are_direct,
        check_reform_governance_actions,
        check_sengoku_cb_is_disabled_by_reform_five,
        check_internal_war_ban_scope,
        check_weixin_conditions_are_inline,
        check_weixin_relationship_trigger_and_gui_tail,
        check_shouyexiayi_target_rules_are_direct,
        check_ai_weixin_decisions_cover_all_buttons,
        check_weixin_page_flag_nots_are_grouped,
        check_gui_default_country_scope_is_direct,
        check_gui_scripted_element_types_match,
        check_shogun_gui_visibility_chain,
        check_shogun_gui_refresh_is_event_driven,
        check_daimyo_identity_boundaries,
        check_reform_localization_keys,
        check_vanilla_modifier_names,
        check_ai_shogun_event_has_picture,
    ]
    for check in checks:
        check()
        print(f"PASS {check.__name__}")


if __name__ == "__main__":
    main()
