import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_government_list_is_current():
    text = read("common/governments/mf_governments.txt")
    require(text.count("\n\t\t\t\tmf_daimyo\n") == 1, "政府列表必须只登记一次 mf_daimyo。")
    require(text.count("\n\t\t\t\tmf_retainer_daimyo\n") == 1, "政府列表必须只登记一次 mf_retainer_daimyo。")
    for key in (
        "zoroastrian_persian_government_reform",
        "turkoman_ottoman_institutions",
        "ayyubid_dynasty",
        "german_cultural_disunity_reform",
        "merchant_representation_reform",
    ):
        require(key in text, f"政府列表缺少 1.37.5 原版条目：{key}")


def check_subject_extension_boundaries():
    text = read("common/subject_types/mf_subject_types.txt")
    daimyo_start = re.search(r"(?m)^daimyo_vassal = \{", text).end()
    daimyo_end = daimyo_start + re.search(r"(?m)^mf_daimyo_vassal = \{", text[daimyo_start:]).start()
    daimyo = text[daimyo_start:daimyo_end]
    require("has_reform = shogunate" in daimyo, "普通大名属国只能由幕府建立。")
    require("overlord_can_be_subject = yes" not in daimyo, "普通大名属国不得允许属国型宗主。")
    require("modifier = subject_nation" not in daimyo, "普通大名不得同时叠加原版属国与大名领国的固定军队上限惩罚。")
    require(daimyo.count("modifier = mf_daimyo_nation") == 1, "普通大名必须只应用一次大名领国修正。")

    require("mf_retainer_daimyo_vassal = {" in text, "缺少家臣属国类型。")
    retainer = text.split("mf_retainer_daimyo_vassal = {", 2)[2]
    require("copy_from = vassal" in retainer, "家臣必须直接继承普通附庸，不能继承大名的外交与战争许可。")
    require("count = vassal" in retainer, "家臣必须按普通属国计数，不能触发原版大名转挂。")
    require("has_reform = daimyo" in retainer, "家臣宗主必须允许普通大名。")
    require("has_reform = mf_daimyo" in retainer, "家臣宗主必须允许谱代大名。")
    require("has_reform = indep_daimyo" in retainer, "家臣宗主必须允许独立大名。")
    require("NOT = { has_reform = shogunate }" in retainer, "幕府不得成为家臣宗主。")
    require(retainer.count("has_reform = ") == 4, "家臣宗主只能允许三种大名改革，并明确排除幕府。")
    require("NOT = { is_subject_of_type = mf_retainer_daimyo_vassal }" in retainer, "家臣不得成为第三级家臣的宗主。")
    require("overlord_can_be_subject = yes" in retainer, "家臣必须允许属国型大名成为宗主。")
    require("can_have_subjects_of_other_types = no" in retainer, "家臣不得建立其他类型属国。")
    require("can_fight_independence_war = no" in retainer, "家臣不得主动发动独立战争。")
    require("joins_overlords_wars = yes" in retainer, "家臣必须随宗主参加战争。")
    require("overlord_protects_external = yes" in retainer, "家臣受到体系外攻击时必须由宗主保护。")
    require("counts_for_borders = yes" in retainer, "家臣领土必须计入宗主边界。")
    for relation in ("can_fight", "can_rival", "can_ally", "can_marry"):
        require(f"{relation} =" not in retainer, f"家臣不得重新定义普通附庸没有的外交关系：{relation}")
    require("count = daimyo_vassal" in text, "谱代类型必须在原版判断中算作大名属国。")
    require("modifier = daimyo_subject" in text, "原版幕府大名宗主修正必须保留。")
    require("can_be_integrated = no" in text, "大名不得被外交整合。")
    require("can_be_annexed = no" in text, "大名不得被外交吞并。")

    decision = read("decisions/mf_daimyo_decisions.txt")
    peace = read("common/peace_treaties/00_mf_subjugate_daimyo.txt")
    require("subject_type = mf_retainer_daimyo_vassal" in decision, "大名分封必须创建家臣。")
    require("NOT = { is_subject_of_type = mf_retainer_daimyo_vassal }" in decision, "家臣不得继续分封第三级属国。")
    require("add_government_reform = mf_retainer_daimyo" in decision, "自定义家臣分封必须明确添加家臣改革。")
    require("modifier = released_vassal" in decision, "分封旧家必须使用原版释放属国好感。")
    require("adopt_reform_progress = ROOT" in decision, "分封旧家必须继承分封者的政府改革进度。")
    require("subject_type = mf_retainer_daimyo_vassal" in peace, "战国收服必须创建家臣。")
    require(peace.count("NOT = { has_reform = shogunate }") == 3, "战国收服必须在可见、允许和实际效果三层排除幕府。")
    require("every_subject_country" in peace, "战国收服必须读取败者原有直属家臣。")
    require("subject = PREV" in peace, "败者原有家臣必须转交给胜者。")
    require("grant_independence = yes" not in peace, "败者原有家臣必须直接转交，不能先释放给幕府截走。")
    require("mf_sengoku_transfer_retainer" not in peace, "直接转交家臣不得保留临时国家标记。")
    require(peace.count("add_government_reform = mf_retainer_daimyo") == 2, "败者和其原有家臣都必须明确使用家臣改革。")
    require("mf_normalize_daimyo" not in peace, "战国收服不得调用通用 normalize effect。")


def check_daimyo_reform_mapping():
    text = read("common/government_reforms/mf_government_reforms_monarchies.txt")
    daimyo = text.split("\ndaimyo = {", 1)[1].split("\nmf_daimyo = {", 1)[0]
    fudai = text.split("\nmf_daimyo = {", 1)[1].split("\nmf_retainer_daimyo = {", 1)[0]
    retainer = text.split("\nmf_retainer_daimyo = {", 1)[1].split("\nindep_daimyo = {", 1)[0]
    independent = text.split("\nindep_daimyo = {", 1)[1]

    require("is_subject_of_type = daimyo_vassal" in daimyo, "普通大名必须使用 daimyo 改革。")
    require("is_subject_of_type = mf_retainer_daimyo_vassal" not in daimyo, "原版 daimyo 改革不得继续覆盖家臣。")
    require("is_subject_of_type = mf_daimyo_vassal" not in daimyo, "谱代不得使用普通 daimyo 改革。")
    require("has_reform = shogunate" in daimyo, "普通大名改革必须要求幕府宗主。")
    require("is_subject_of_type = mf_daimyo_vassal" in fudai, "谱代类型必须使用 mf_daimyo 改革。")
    require("is_subject_of_type = mf_retainer_daimyo_vassal" in retainer, "家臣类型必须使用 mf_retainer_daimyo 改革。")
    for reform in ("daimyo", "mf_daimyo", "indep_daimyo"):
        require(f"has_reform = {reform}" in retainer, f"家臣改革缺少合法宗主：{reform}")
    require("is_subject = no" in independent, "独立大名改革必须允许无宗主国家。")

    decision = read("decisions/mf_daimyo_decisions.txt")
    peace = read("common/peace_treaties/00_mf_subjugate_daimyo.txt")
    diplomacy = read("common/new_diplomatic_actions/mf_diplomatic_actions.txt")
    effects = read("common/scripted_effects/mf_daimyo_efx.txt")
    identity = read("common/scripted_triggers/mf_daimyo_trigger.txt")
    require("add_government_reform = mf_retainer_daimyo" in decision, "分封家臣入口必须明确添加家臣改革。")
    require("add_government_reform = mf_retainer_daimyo" in peace, "战国收服入口必须明确添加家臣改革。")
    require("add_government_reform = mf_daimyo" in diplomacy, "提升谱代入口必须明确添加 mf_daimyo。")
    require("add_government_reform = mf_daimyo" in effects, "任命谱代执行者入口必须明确添加 mf_daimyo。")
    illegal_transfer = diplomacy.split("\nmf_transfer_illegal_subject = {", 1)[1].split("\nshouyexiayi = {", 1)[0]
    require("require_acceptance = yes" in illegal_transfer, "归还国家行动必须要求接受。")
    require("add_government_reform = daimyo" in illegal_transfer, "归还国家后必须恢复普通 daimyo 改革。")
    require("has_reform = mf_retainer_daimyo" in identity, "幕府大名身份判定必须覆盖家臣改革。")
    for forbidden in (
        "mf_normalize_daimyo_first_layer_reform_effect",
        "mf_normalize_daimyo_hierarchy_effect",
        "mf_rehome_daimyo_subjects_effect",
    ):
        require(forbidden not in "\n".join((decision, peace, diplomacy, effects)), f"不得保留通用整理 effect：{forbidden}")


def check_shogun_cache_lifecycle():
    files = [
        *ROOT.glob("common/**/*.txt"),
        *ROOT.glob("events/*.txt"),
        *ROOT.glob("decisions/*.txt"),
        *ROOT.glob("missions/*.txt"),
    ]
    writers = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if re.search(r"save_global_event_target_as\s*=\s*zhengyidajiangjun", text):
            writers.append(path.relative_to(ROOT).as_posix())
    require(
        set(writers) == {
            "common/on_actions/mf_shogun_on_actions.txt",
            "decisions/mf_shogun_ai_decisions.txt",
            "events/mf_daimyo_event.txt",
        },
        f"将军缓存只能由开局初始化、玩家交接事件和 AI 交接决议写入，当前为：{writers}",
    )
    effect_text = read("common/scripted_effects/mf_daimyo_efx.txt")
    require("save_global_event_target_as = zhengyidajiangjun" not in effect_text, "scripted effect 不得写入将军缓存。")
    require("mf_sync_shogun_cache_effect = {" not in effect_text, "不得继续使用初始化与交接混合的缓存同步 effect。")
    require("mf_reconcile_shogunate_transfer_effect = {" not in effect_text, "属国交接不得再拆成第二层 scripted effect。")
    require("mf_shogunate_transfer_effect = {" not in effect_text, "单次交接逻辑不得再包装为 scripted effect。")

    on_actions = read("common/on_actions/mf_shogun_on_actions.txt")
    events = read("events/mf_daimyo_event.txt")
    ai_decisions = read("decisions/mf_shogun_ai_decisions.txt")
    startup = on_actions.split("on_startup = {", 1)[1].split("\non_monthly_pulse = {", 1)[0]
    monthly = on_actions.split("on_monthly_pulse = {", 1)[1].split("\non_siege_won_country = {", 1)[0]
    reconcile = events.split("id = mf_daimyo.13", 1)[1]
    ai_reconcile = ai_decisions.split("mf_ai_complete_shogunate_transfer = {", 1)[1].split("\n\tmf_ai_xuanxiafengxing = {", 1)[0]
    require("ai = no" in reconcile, "玩家幕府交接隐藏事件只能对玩家执行。")
    require("ai = yes" in ai_reconcile, "AI 幕府交接必须由 AI 专用决议执行。")
    require("ai_importance = 400" in ai_reconcile, "AI 幕府交接决议必须优先执行。")
    require("has_reform = shogunate" in reconcile, "幕府交接必须读取原版 shogunate 改革。")
    for transfer in (reconcile, ai_reconcile):
        require("event_target:zhengyidajiangjun = {" in transfer, "幕府交接必须从旧将军缓存读取直属属国。")
        for subject_type in ("mf_daimyo_vassal", "mf_retainer_daimyo_vassal"):
            require(f"is_subject_of_type = {subject_type}" in transfer, f"幕府交接缺少直属类型：{subject_type}")
        require(transfer.count("subject_type = daimyo_vassal") == 2, "旧幕府自定义属国和新幕府家臣都必须转为普通大名。")
        require(transfer.count("add_government_reform = daimyo") == 2, "转为幕府直属普通大名时必须同步恢复 daimyo 改革。")
        require("set_country_flag = mf_transfer_to_new_shogunate" in transfer, "旧幕府自定义属国必须先记录再解除旧关系。")
        require("has_country_flag = mf_transfer_to_new_shogunate" in transfer, "幕府交接第二步必须只读取已记录属国。")
        require("remove_government_reform" not in transfer, "幕府交接不得删除原版大名改革。")
        require("which = shogun_value value = 50" in transfer, "新幕府统御必须初始化为 50。")
        require("which = shogun_value_display value = 50" in transfer, "新幕府显示统御必须初始化为 50.00。")
        require("bl_mp_effect" not in transfer, "幕府交接不得执行月度统御结算。")

    require(startup.count("save_global_event_target_as = zhengyidajiangjun") == 1, "开局必须直接设置将军缓存。")
    require("which = shogun_value value = 50" in startup, "开局必须初始化统御变量。")
    require("which = shogun_value_display value = 50" in startup, "开局必须初始化统御显示变量。")
    require(startup.count("bl_shogun_refresh = yes") == 1, "开局必须建立大名盾徽目标。")
    for forbidden in ("mf_shogunate_transfer_effect", "tianhuang", "xiayi", "bl_mp_effect"):
        require(forbidden not in startup, f"开局初始化不得包含：{forbidden}")
    require("save_global_event_target_as" not in monthly, "月脉冲不得自动设置任何全局目标。")
    require("tag = event_target:zhengyidajiangjun" in monthly, "月度统御必须等待将军缓存交接完成。")
    require("on_reform_enacted = {" not in on_actions, "幕府交接不得挂在通用改革采用入口。")
    require("on_government_change = {" not in on_actions, "幕府交接不得挂在政府类型变化入口。")
    require("on_reform_changed = {" not in on_actions, "幕府交接不得挂在改革替换入口。")
    owner_change = on_actions.split("on_province_owner_change = {", 1)[1]
    require("province_id = 1020" in owner_change, "幕府后置事件只能由京都易主安排。")
    require("id = mf_daimyo.13 days = 1" in owner_change, "京都易主必须安排一天后的幕府交接事件。")
    require("ai = no" in owner_change, "京都易主后置事件只能为玩家安排，AI 使用专用决议。")
    require(re.search(r"events\s*=\s*\{[^}]*japan\.1", owner_change, re.S) is None, "本模组不得重复调用原版 japan.1。")
    require(reconcile.count("save_global_event_target_as = zhengyidajiangjun") == 1, "幕府交接必须直接写入一次新将军缓存。")
    require(ai_reconcile.count("save_global_event_target_as = zhengyidajiangjun") == 1, "AI 幕府交接必须直接写入一次新将军缓存。")
    target_effects = read("common/scripted_effects/mf_shogun_ai_effects.txt")
    tianhuang_refresh = target_effects.split("mf_refresh_tianhuang_target_effect = {", 1)[1].split("\nmf_set_xiayi_campaign_target_effect = {", 1)[0]
    require("random_subject_country" not in tianhuang_refresh, "天皇目标不得由刷新效果自动选择。")
    require("save_global_event_target_as = tianhuang" not in tianhuang_refresh, "天皇目标只能由外交行动设置。")
    require("on_create_vassal = {" not in on_actions, "属国层级必须由真实入口控制，不保留 on_create_vassal 兜底。")


def check_vanilla_owner_change_is_not_reimplemented():
    on_actions = read("common/on_actions/mf_shogun_on_actions.txt")
    events = read("events/mf_daimyo_event.txt")
    effects = read("common/scripted_effects/mf_daimyo_efx.txt")
    owner_change = on_actions.split("on_province_owner_change = {", 1)[1]
    require("country_event = { id = mf_daimyo.13 days = 1 }" in owner_change, "京都易主入口只能安排后置事件。")
    require("save_global_event_target_as" not in owner_change, "京都易主当日不得提前切换幕府缓存。")
    require("add_government_reform = shogunate" not in events, "后置事件不得重新授予幕府改革。")
    require("mf_daimyo.14" not in events, "不得保留自定义幕府更替事件。")
    require("mf_relink_direct_daimyos_after_shogunate_transfer_effect" not in effects, "不得重新实现原版大名转挂。")
    monthly = on_actions.split("on_monthly_pulse = {", 1)[1].split("on_siege_won_country = {", 1)[0]
    require("change_subject_type" not in monthly, "月脉冲不得重写大名属国类型。")
    require("mf_normalize_shogunate_subjects_effect" not in monthly, "月脉冲不得批量整理原版幕府属国。")


def check_cb_override_is_isolated():
    require(not (ROOT / "common/cb_types/00_cb_types.txt").exists(), "本模组不得覆盖整份原版 CB 数据库。")
    text = read("common/cb_types/mf_cb_types.txt")
    require("\ncb_sengoku = {" not in text, "独立 CB 文件不得重复注册原版 cb_sengoku。")
    for key in (
        "cb_mf_return_daimyo_land",
        "cb_mf_partition_daimyo",
        "cb_mf_enforce_executor_service",
        "cb_mf_shogunate_excommunication",
        "cb_mf_xiayi_campaign",
        "cb_mf_shogunate_japan_campaign",
        "cb_mf_sengoku",
    ):
        require(text.count(f"{key} = {{") == 1, f"自定义 CB 必须只定义一次：{key}")
    sengoku = text.split("\ncb_mf_sengoku = {", 1)[1]
    require("exclusive = yes" in sengoku, "动态战国收服必须排除同一目标上的原版战国借口。")
    require("is_triggered_only" not in sengoku and "months =" not in sengoku, "战国收服不得使用事件型期限。")
    require("prerequisites_self = {" in sengoku and "prerequisites = {" in sengoku, "战国收服必须按条件实时判定。")
    for reform in ("daimyo", "mf_daimyo", "indep_daimyo"):
        require(sengoku.count(f"has_reform = {reform}") == 2, f"战国收服的进攻方和目标都必须允许：{reform}")
    require(sengoku.count("NOT = { is_subject_of_type = mf_retainer_daimyo_vassal }") == 2, "家臣不得获得战国收服或成为其目标。")
    require("is_neighbor_of = FROM" in sengoku, "战国收服必须保留原版邻接要求。")
    require("any_subject_country = {" in sengoku, "战国收服必须检查目标家臣的邻接。")
    require(
        re.search(
            r"FROM\s*=\s*\{\s*any_subject_country\s*=\s*\{\s*is_subject_of_type\s*=\s*mf_retainer_daimyo_vassal\s*is_neighbor_of\s*=\s*ROOT",
            sengoku,
            re.S,
        )
        is not None,
        "战国收服必须把与进攻方接壤的目标家臣归入宗主目标判定。",
    )
    require("war_goal = mf_sengoku_subjugation" in sengoku, "战国收服必须使用家臣收服战争目标。")
    require(not (ROOT / "events/flavorJAP.txt").exists(), "战国收服不得覆盖原版日本事件。")
    on_actions = read("common/on_actions/mf_shogun_on_actions.txt")
    require("cb_mf_sengoku" not in on_actions, "战国收服不得由脉冲反复刷新。")


def check_household_war_targets():
    diplomacy = read("common/new_diplomatic_actions/mf_diplomatic_actions.txt")
    excommunication = diplomacy.split("\nmf_excommunicate_daimyo = {", 1)[1].split("\nmf_return_daimyo_land = {", 1)[0]
    peace = read("common/peace_treaties/00_mf_enforce_shogunate_obedience.txt")
    peace_visible = peace.split("\tis_visible = {", 1)[1].split("\n\tis_allowed = {", 1)[0]
    declarewar = read("common/diplomatic_actions/00_diplomatic_actions.txt").split("\ndeclarewar = {", 1)[1]
    require("is_subject_of_type = daimyo_vassal" in excommunication, "绝罚必须以幕府直属普通大名为目标。")
    require("is_subject_of_type = mf_daimyo_vassal" in excommunication, "绝罚必须以幕府直属谱代为目标。")
    require("any_subject_country = {" in excommunication, "家臣拒令必须由宗主大名承担家内责任。")
    require("is_subject_of_type = mf_retainer_daimyo_vassal" in excommunication, "绝罚必须读取直属大名的拒令家臣。")
    require("target = FROM" in excommunication, "绝罚 CB 必须指向宗主大名。")
    require("is_subject_of_type = mf_retainer_daimyo_vassal" not in peace_visible, "强制服从和平不得把家臣作为和谈目标。")
    require("overlord = { is_subject_of = ROOT }" not in peace_visible, "强制服从和平只能针对幕府直属大名。")
    require("every_subject_country = {" in peace, "强制服从和平必须清理宗主直属家臣的拒命状态。")
    require("tooltip = NO_WAR_ON_OTHER_VASSALS" in declarewar, "宣战界面必须说明不能直接向他国属国宣战。")
    require("FROM = { is_subject_of_type = mf_retainer_daimyo_vassal }" in declarewar, "宣战界面必须识别家臣目标。")
    require("allow = { always = no }" in declarewar, "任何国家都不得单独向家臣宣战。")


def check_braces():
    for folder in ("common", "events", "decisions", "missions"):
        for path in (ROOT / folder).rglob("*.txt"):
            text = path.read_text(encoding="utf-8")
            require(text.count("{") == text.count("}"), f"花括号不平衡：{path.relative_to(ROOT)}")


def main():
    checks = (
        check_government_list_is_current,
        check_subject_extension_boundaries,
        check_daimyo_reform_mapping,
        check_shogun_cache_lifecycle,
        check_vanilla_owner_change_is_not_reimplemented,
        check_cb_override_is_isolated,
        check_household_war_targets,
        check_braces,
    )
    for check in checks:
        check()
        print(f"PASS {check.__name__}")


if __name__ == "__main__":
    main()
