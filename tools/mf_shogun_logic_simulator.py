from dataclasses import dataclass, field
from pathlib import Path


DAIMYO_SUBJECTS = {"daimyo_vassal", "mf_daimyo_vassal", "mf_retainer_daimyo_vassal"}
ROOT = Path(__file__).resolve().parents[1]
HIGAN_ROOT = Path(r"E:\SteamLibrary\steamapps\workshop\content\236850\1635373831")


def read_mod_text(path):
    return (ROOT / path).read_bytes().decode("latin-1")


def read_higan_text(path):
    return (HIGAN_ROOT / path).read_bytes().decode("latin-1")


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


def daimyo_reform_allows_subject_type(subject_type):
    reforms = read_mod_text("common/government_reforms/mf_government_reforms_monarchies.txt")
    daimyo = named_block(reforms, "daimyo")
    potential = named_block(daimyo, "potential")
    return f"is_subject_of_type = {subject_type}" in potential


def indep_daimyo_reform_allows_free_or_tributary():
    reforms = read_mod_text("common/government_reforms/mf_government_reforms_monarchies.txt")
    indep_daimyo = named_block(reforms, "indep_daimyo")
    potential = named_block(indep_daimyo, "potential")
    return "is_subject = no" in potential and "is_subject_of_type = tributary_state" in potential


@dataclass
class Country:
    tag: str
    overlord: str | None = None
    subject_type: str | None = None
    reforms: set[str] = field(default_factory=set)
    provinces: set[str] = field(default_factory=set)
    modifiers: set[str] = field(default_factory=set)
    flags: set[str] = field(default_factory=set)
    cbs: set[tuple[str, str]] = field(default_factory=set)
    treasury: float = 100.0
    total_development: float = 60.0
    yearly_income: float = 120.0
    prestige: float = 0.0
    liberty_desire: float = 0.0
    loans: int = 0
    opinions: dict[str, int] = field(default_factory=dict)
    alive: bool = True


class World:
    def __init__(self):
        self.countries: dict[str, Country] = {}
        self.event_targets: dict[str, str] = {}
        self.shogun_authority = 50
        self.global_flags: set[str] = set()
        self.shogun_modifiers: set[str] = set()
        self.province_flags: dict[str, set[str]] = {}
        self.shogunate_province_home: dict[str, str] = {}

    def add_country(self, tag, reforms=None, provinces=None):
        self.countries[tag] = Country(
            tag=tag,
            reforms=set(reforms or []),
            provinces=set(provinces or []),
        )

    def set_subject(self, subject, overlord, subject_type):
        country = self.countries[subject]
        country.overlord = overlord
        country.subject_type = subject_type

    def grant_cb(self, holder, target, cb_type):
        self.countries[holder].cbs.add((cb_type, target))

    def remove_cb(self, holder, target, cb_type):
        self.countries[holder].cbs.discard((cb_type, target))

    def has_cb(self, holder, target, cb_type):
        return (cb_type, target) in self.countries[holder].cbs

    def normalize_daimyo_reform(self, tag):
        country = self.countries[tag]
        if not (country.reforms & {"daimyo", "mf_daimyo", "indep_daimyo"} or country.subject_type in DAIMYO_SUBJECTS):
            return
        country.reforms -= {"daimyo", "mf_daimyo", "indep_daimyo"}
        if country.subject_type == "mf_daimyo_vassal":
            country.reforms.add("mf_daimyo")
        elif country.subject_type in {"daimyo_vassal", "mf_retainer_daimyo_vassal"}:
            country.reforms.add("daimyo")
        elif country.overlord is None or country.subject_type == "tributary_state":
            country.reforms.add("indep_daimyo")

    def reform_potential_valid(self, tag, reform):
        country = self.countries[tag]
        if reform == "daimyo":
            if "formed_japan_flag" in country.flags:
                return False
            return daimyo_reform_allows_subject_type(country.subject_type)
        if reform == "mf_daimyo":
            return (
                country.subject_type == "mf_daimyo_vassal"
                and country.overlord is not None
                and "shogunate" in self.countries[country.overlord].reforms
            )
        if reform == "indep_daimyo":
            return indep_daimyo_reform_allows_free_or_tributary() and (
                country.overlord is None or country.subject_type == "tributary_state"
            )
        return True

    def refresh_first_layer_reform_validity(self, tag):
        country = self.countries[tag]
        for reform in list(country.reforms & {"daimyo", "mf_daimyo", "indep_daimyo"}):
            if not self.reform_potential_valid(tag, reform):
                country.reforms.remove(reform)

    def can_use_sengoku_cb(self, attacker, defender):
        a = self.countries[attacker]
        d = self.countries[defender]
        return (
            a.alive
            and d.alive
            and a.overlord == "SHO"
            and d.overlord == "SHO"
            and a.subject_type in {"daimyo_vassal", "mf_daimyo_vassal"}
            and d.subject_type in {"daimyo_vassal", "mf_daimyo_vassal"}
            and "jap_sengoku_jidai" in self.shogun_modifiers
            and "shogun_weixin.h_global_flag" not in self.global_flags
        )

    @staticmethod
    def sankin_cost(total_development, distance, yearly_income):
        fixed_cost = total_development / 5
        distance_multiplier = min(distance / 12, 3)
        yearly_income_cost = yearly_income / 3 * distance_multiplier
        total_cost = fixed_cost + yearly_income_cost
        return distance_multiplier, fixed_cost, yearly_income_cost, total_cost

    @staticmethod
    def sankin_refusal_chance(liberty_desire, loans):
        accept_weight = 100.0
        if loans >= 10:
            accept_weight *= 0
        if loans >= 5:
            accept_weight *= 0.1
        if liberty_desire >= 50:
            accept_weight *= 0.2
        refusal_weight = 100.0
        return refusal_weight / (accept_weight + refusal_weight)

    def sankin_targets(self):
        if "shogun_yuling_b" not in self.shogun_modifiers:
            return []
        if "shogun_weixin.h_global_flag" in self.global_flags:
            return []
        shogun = self.event_targets.get("zhengyidajiangjun")
        direct = [country for country in self.countries.values() if country.overlord == shogun]
        targets = [country.tag for country in direct if country.subject_type in DAIMYO_SUBJECTS]
        for lord in direct:
            targets.extend(
                country.tag
                for country in self.countries.values()
                if country.overlord == lord.tag and country.subject_type == "mf_retainer_daimyo_vassal"
            )
        return targets

    def accept_sankin(self, target, distance):
        country = self.countries[target]
        _, _, _, total_cost = self.sankin_cost(country.total_development, distance, country.yearly_income)
        country.treasury -= total_cost
        country.modifiers.add("mf_sankin_kotai_travel")

    def refuse_sankin(self, target):
        country = self.countries[target]
        country.prestige += 10
        country.modifiers.add("mf_sankin_kotai_refused")
        self.shogun_authority -= 0.5

    def complete_sankin_reform(self):
        targets = self.sankin_targets()
        self.global_flags.add("shogun_weixin.h_global_flag")
        self.shogun_modifiers.discard("shogun_yuling_b")
        self.shogun_modifiers.discard("mf_sankin_kotai_began")
        self.shogun_modifiers.add("jiujizhengshi_2")
        for target in targets:
            self.countries[target].modifiers.discard("mf_sankin_kotai_refused")
            self.countries[target].modifiers.discard("mf_sankin_kotai_travel")

    def can_form_alliance(self, actor, target):
        if "shogun_weixin.h_global_flag" not in self.global_flags:
            return True
        shogun = self.event_targets.get("zhengyidajiangjun")
        actor_is_daimyo = actor != shogun and self.is_shogunate_member(actor)
        target_is_daimyo = target != shogun and self.is_shogunate_member(target)
        return not (actor_is_daimyo and target_is_daimyo)

    def is_shogunate_member(self, tag):
        shogun = self.event_targets.get("zhengyidajiangjun")
        current = tag
        visited = set()
        while current and current not in visited:
            if current == shogun:
                return True
            visited.add(current)
            current = self.countries[current].overlord
        return False

    def owner_of(self, province):
        return next((country.tag for country in self.countries.values() if province in country.provinces), None)

    def transfer_province(self, province, new_owner):
        old_owner = self.owner_of(province)
        if old_owner:
            self.countries[old_owner].provinces.discard(province)
        self.countries[new_owner].provinces.add(province)

    def mark_shogunate_province(self, province):
        owner = self.owner_of(province)
        self.require(owner is not None and self.is_shogunate_member(owner), "province belongs to the shogunate system")
        self.province_flags.setdefault(province, set()).add("mf_shogunate_province")
        self.shogunate_province_home[province] = owner

    def return_marked_shogunate_province(self, province):
        self.require("mf_shogunate_province" in self.province_flags.get(province, set()), "province is marked by the shogunate")
        home = self.shogunate_province_home[province]
        self.transfer_province(province, home)

    def transfer_illegal_subject_to_shogun(self, former_lord, subject):
        self.require(self.countries[subject].overlord == former_lord, "illegal subject belongs to the requested daimyo")
        shogun = self.event_targets["zhengyidajiangjun"]
        self.set_subject(subject, shogun, "daimyo_vassal")
        self.normalize_daimyo_reform(subject)
        self.shogun_authority += 2

    def can_declare_war(self, attacker, defender):
        if "mf_shogunate_excommunication" in self.countries[attacker].modifiers:
            return False
        if "shogun_weixin.f_global_flag" not in self.global_flags:
            return True
        if self.countries[attacker].overlord == defender:
            return True
        return not (self.is_shogunate_member(attacker) and self.is_shogunate_member(defender))

    def demand_all_provinces(self, attacker, defender):
        self.require(self.can_use_sengoku_cb(attacker, defender), "A can declare sengoku war on B")
        a = self.countries[attacker]
        d = self.countries[defender]
        a.provinces |= d.provinces
        d.provinces.clear()
        d.alive = False
        d.overlord = None
        d.subject_type = None

    def subjugate_daimyo(self, attacker, defender):
        self.require(self.can_use_sengoku_cb(attacker, defender), "A can declare sengoku war on B")
        self.execute_po_mf_subjugate_daimyo(root=attacker, from_tag=defender)

    def execute_po_mf_subjugate_daimyo(self, root, from_tag):
        before = self.shogun_authority
        self.event_targets["mf_daimyo_rehome_lord"] = root
        self.create_subject(root=root, subject=from_tag, subject_type="mf_retainer_daimyo_vassal")
        self.execute_mf_rehome_daimyo_subjects_effect(scope=from_tag)
        self.execute_mf_normalize_daimyo_first_layer_reform_effect(scope=from_tag)
        self.execute_mf_promote_retainer_daimyos_to_shogunate_effect(scope=root)
        self.event_targets.pop("mf_daimyo_rehome_lord", None)
        self.require(self.shogun_authority == before, "private daimyo subjugation does not change shogun authority")

    def create_subject(self, root, subject, subject_type):
        self.set_subject(subject, root, subject_type)

    def execute_mf_rehome_daimyo_subjects_effect(self, scope):
        self.require("mf_daimyo_rehome_lord" in self.event_targets, "rehome lord event target exists")
        self.rehome_daimyo_subjects(old_lord=scope, new_lord=self.event_targets["mf_daimyo_rehome_lord"])

    def rehome_daimyo_subjects(self, old_lord, new_lord):
        for country in self.countries.values():
            if country.overlord == old_lord and country.subject_type in DAIMYO_SUBJECTS:
                country.overlord = new_lord
                if new_lord == "SHO":
                    country.subject_type = "daimyo_vassal"
                else:
                    country.subject_type = "mf_retainer_daimyo_vassal"
                self.execute_mf_normalize_daimyo_first_layer_reform_effect(scope=country.tag)

    def execute_mf_normalize_daimyo_first_layer_reform_effect(self, scope):
        self.normalize_daimyo_reform(scope)

    def execute_mf_promote_retainer_daimyos_to_shogunate_effect(self, scope):
        if "shogunate" in self.countries[scope].reforms:
            return
        for country in self.countries.values():
            if country.overlord == scope and country.subject_type == "mf_daimyo_vassal":
                self.set_subject(country.tag, scope, "mf_retainer_daimyo_vassal")
                self.execute_mf_normalize_daimyo_first_layer_reform_effect(scope=country.tag)

    def release_extinct_retainer(self, lord, tag, province):
        self.require(self.countries[lord].alive, "lord exists")
        self.require(province in self.countries[lord].provinces, "lord owns the release province")
        self.add_country(tag, reforms={"daimyo"}, provinces={province})
        self.countries[lord].provinces.remove(province)
        self.set_subject(tag, lord, "mf_retainer_daimyo_vassal")
        self.normalize_daimyo_reform(tag)

    def release_extinct_direct_daimyo(self, tag, province):
        self.require(province in self.countries["SHO"].provinces, "shogun owns the release province")
        self.add_country(tag, reforms={"daimyo"}, provinces={province})
        self.countries["SHO"].provinces.remove(province)
        self.set_subject(tag, "SHO", "daimyo_vassal")
        self.normalize_daimyo_reform(tag)
        self.shogun_authority += 2

    def return_land_accept(self, holder, tag, province):
        self.require(province in self.countries[holder].provinces, "holder owns the return province")
        self.add_country(tag, reforms={"daimyo"}, provinces={province})
        self.countries[holder].provinces.remove(province)
        self.set_subject(tag, "SHO", "daimyo_vassal")
        self.normalize_daimyo_reform(tag)
        self.countries[holder].flags.add("mf_recently_returned_daimyo_land")
        self.shogun_authority += 5

    def return_land_decline(self, holder, province):
        self.require(province in self.countries[holder].provinces, "holder owns the refused province")
        self.countries[holder].flags.add("mf_recently_refused_return_daimyo_land")
        self.countries[holder].modifiers.add("mf_unlawful_daimyo_land")
        self.grant_cb("SHO", holder, "cb_mf_return_daimyo_land")
        self.shogun_authority -= 5

    def lecture_daimyo(self, target):
        before = self.shogun_authority
        self.require(before >= 5, "shogun has enough authority to lecture")
        self.countries[target].flags.add("mf_recently_lectured_by_shogun")
        self.countries[target].modifiers.add("mf_shogunate_lecture")
        self.shogun_authority -= 5

    def grace_daimyo(self, target):
        before = self.shogun_authority
        self.require(before >= 5, "shogun has enough authority to pardon")
        self.countries[target].modifiers.discard("mf_shogunate_lecture")
        self.countries[target].modifiers.add("mf_shogunate_grace")
        self.shogun_authority -= 5

    def enforce_peace_accept(self, attacker, defender):
        self.shogun_authority -= 10

    def enforce_peace_decline(self, attacker, defender):
        self.countries[attacker].flags.add("mf_refused_enforce_daimyo_peace")
        self.shogun_authority -= 10

    def force_partition(self, target, released, province):
        self.require(province in self.countries[target].provinces, "partition target owns release province")
        self.add_country(released, reforms={"daimyo"}, provinces={province})
        self.countries[target].provinces.remove(province)
        self.set_subject(released, "SHO", "daimyo_vassal")
        self.normalize_daimyo_reform(released)
        self.shogun_authority += 5

    def partition_decline(self, target):
        self.countries[target].flags.add("mf_refused_partition_daimyo")
        self.grant_cb("SHO", target, "cb_mf_partition_daimyo")

    def appoint_executor(self, target):
        self.require(not any("mf_shogunate_executor" in c.modifiers for c in self.countries.values()), "no existing executor")
        self.set_subject(target, "SHO", "mf_daimyo_vassal")
        self.normalize_daimyo_reform(target)
        self.countries[target].modifiers.add("mf_shogunate_executor")
        self.shogun_authority += 5

    def executor_decline(self, target):
        self.countries[target].flags.add("mf_refused_executor_appointment")
        self.grant_cb("SHO", target, "cb_mf_enforce_executor_service")

    def excommunicate_daimyo(self, target):
        self.countries[target].flags.add("mf_under_shogunate_excommunication")
        self.countries[target].modifiers.add("mf_shogunate_excommunication")
        self.grant_cb("SHO", target, "cb_mf_shogunate_excommunication")
        self.shogun_authority += 2

    def transfer_shogunate(self, new_shogun):
        old_shogun = self.countries["SHO"]
        new = self.countries[new_shogun]
        old_shogun.reforms.discard("shogunate")
        new.reforms.add("shogunate")
        new.overlord = None
        new.subject_type = None
        self.event_targets["zhengyidajiangjun"] = new_shogun
        xiayi = self.event_targets.get("xiayi")
        if xiayi:
            self.grant_cb(new_shogun, xiayi, "cb_mf_xiayi_campaign")
        for country in self.countries.values():
            if country.tag not in {"SHO", new_shogun} and country.overlord == "SHO":
                country.overlord = new_shogun

    def demote_illegal_fudai_under_daimyo(self, target):
        overlord = self.countries[target].overlord
        self.require(overlord != "SHO", "target is under a non-shogun daimyo")
        self.require(self.countries[target].subject_type == "mf_daimyo_vassal", "target is illegal fudai")
        self.set_subject(target, overlord, "mf_retainer_daimyo_vassal")
        self.normalize_daimyo_reform(target)

    def set_xiayi_target(self, target):
        old_target = self.event_targets.get("xiayi")
        shogun = self.event_targets.get("zhengyidajiangjun")
        if old_target and shogun:
            self.remove_cb(shogun, old_target, "cb_mf_xiayi_campaign")
        for country in self.countries.values():
            country.flags.discard("mf_xiayi_target")
        self.countries[target].flags.add("mf_xiayi_target")
        self.event_targets["xiayi"] = target
        if shogun:
            self.grant_cb(shogun, target, "cb_mf_xiayi_campaign")

    def cb_mf_xiayi_campaign_available(self, attacker, target):
        assert_xiayi_cb_script_chain()
        target_country = self.countries[target]
        return (
            self.countries[attacker].alive
            and target_country.alive
            and self.has_cb(attacker, target, "cb_mf_xiayi_campaign")
        )

    def higan_cb_return_hecatia_war_available(self, attacker, target):
        assert_higan_return_hecatia_cb_script_chain()
        attacker_country = self.countries[attacker]
        target_country = self.countries[target]
        hecatia_exists = "HEC" in self.countries and self.countries["HEC"].alive
        return (
            attacker_country.alive
            and target_country.alive
            and "hig_has_return_hecatia_war_cb_flag" in attacker_country.flags
            and (
                target == "HEC"
                or (not hecatia_exists and 5327 in target_country.provinces)
            )
        )

    def subjugate_xiayi(self, target):
        self.require(self.cb_mf_xiayi_campaign_available("SHO", target), "xiayi campaign cb is available")
        self.set_subject(target, "SHO", "daimyo_vassal")
        self.countries[target].flags.discard("mf_xiayi_target")
        self.remove_cb("SHO", target, "cb_mf_xiayi_campaign")
        self.normalize_daimyo_reform(target)

    @staticmethod
    def require(condition, message):
        if not condition:
            raise AssertionError(message)


def assert_private_subjugation_script_chain():
    treaty_text = read_mod_text("common/peace_treaties/00_mf_subjugate_daimyo.txt")
    treaty = treaty_text
    ordered_tokens = [
        "save_global_event_target_as = mf_daimyo_rehome_lord",
        "create_subject =",
        "subject_type = mf_retainer_daimyo_vassal",
        "mf_rehome_daimyo_subjects_effect = yes",
        "mf_normalize_daimyo_first_layer_reform_effect = yes",
        "mf_promote_retainer_daimyos_to_shogunate_effect = yes",
    ]
    position = -1
    for token in ordered_tokens:
        next_position = treaty.index(token)
        World.require(next_position > position, f"subjugation treaty order keeps {token}")
        position = next_position

    World.require("subject_type = mf_retainer_daimyo_vassal" in treaty, "subjugation treaty creates retainer daimyo subject")
    World.require("mf_rehome_daimyo_subjects_effect = yes" in treaty, "subjugation treaty calls subject rehome effect")
    World.require("mf_normalize_daimyo_first_layer_reform_effect = yes" in treaty, "subjugation treaty normalizes daimyo reform")
    World.require("mf_change_shogun_value" not in treaty, "subjugation treaty does not change shogun authority")

    effect_text = read_mod_text("common/scripted_effects/mf_daimyo_efx.txt")
    rehome = block_between(effect_text, "mf_rehome_daimyo_subjects_effect = {", "mf_relink_direct_daimyos_after_shogunate_transfer_effect = {")
    World.require("every_subject_country" in rehome, "rehome effect iterates old lord subjects")
    World.require("is_subject_of_type = daimyo_vassal" in rehome, "rehome effect covers outside daimyo")
    World.require("is_subject_of_type = mf_daimyo_vassal" in rehome, "rehome effect covers fudai daimyo")
    World.require("is_subject_of_type = mf_retainer_daimyo_vassal" in rehome, "rehome effect covers retainer daimyo")
    World.require("vassalize = PREV" in rehome, "rehome effect vassalizes old subjects to the saved new lord")
    World.require("subject_type = mf_retainer_daimyo_vassal" in rehome, "rehome effect demotes subjects under non-shogun lords to retainers")
    World.require("mf_normalize_daimyo_first_layer_reform_effect = yes" in rehome, "rehome effect normalizes moved subjects")


def assert_xiayi_cb_script_chain():
    cb_text = read_mod_text("common/cb_types/00_cb_types.txt")
    cb = named_block(cb_text, "cb_mf_xiayi_campaign")
    World.require("is_triggered_only = yes" in cb, "xiayi cb is granted explicitly")
    World.require("prerequisites_self" not in cb, "xiayi cb does not wait for attacker prerequisite refresh")
    World.require("prerequisites =" not in cb, "xiayi cb does not wait for target prerequisite refresh")

    effect_text = read_mod_text("common/scripted_effects/mf_shogun_ai_effects.txt")
    effect = effect_text[effect_text.index("mf_set_xiayi_campaign_target_effect = {"):]
    World.require("add_casus_belli = {" in effect, "xiayi target effect grants the cb immediately")
    World.require("type = cb_mf_xiayi_campaign" in effect, "xiayi target effect grants the real cb key")
    World.require("target = ROOT" in effect, "xiayi target effect grants the cb against its target scope")


def assert_higan_return_hecatia_cb_script_chain():
    cb_text = read_higan_text("common/cb_types/touhou_cb_types.txt")
    cb = block_between(cb_text, "cb_return_hecatia_war = {", "# War of Repentance")
    World.require("has_country_flag = hig_has_return_hecatia_war_cb_flag" in cb, "higan Hecatia cb uses attacker flag")
    World.require("NOT = { exists = HEC }" in cb, "higan Hecatia cb checks missing HEC branch")
    World.require("FROM = { owns = 5327 }" in cb, "higan Hecatia cb checks target province owner through FROM")
    World.require("FROM = { tag = HEC }" in cb, "higan Hecatia cb checks direct HEC target through FROM")


def build_world():
    world = World()
    world.add_country("SHO", reforms={"shogunate"}, provinces={"kyoto"})
    world.add_country("A", reforms={"daimyo"}, provinces={"a1", "a2"})
    world.add_country("B", reforms={"daimyo"}, provinces={"b1", "b2"})
    world.set_subject("A", "SHO", "daimyo_vassal")
    world.set_subject("B", "SHO", "daimyo_vassal")
    world.event_targets["zhengyidajiangjun"] = "SHO"
    world.shogun_modifiers.add("jap_sengoku_jidai")
    return world


def test_private_war_annex():
    world = build_world()
    world.demand_all_provinces("A", "B")
    world.require(not world.countries["B"].alive, "B is annexed")
    world.require(world.countries["A"].provinces == {"a1", "a2", "b1", "b2"}, "A owns all former B provinces")
    world.require(world.countries["A"].overlord == "SHO", "A remains a direct daimyo under the shogunate")
    world.require(world.countries["A"].subject_type == "daimyo_vassal", "A remains an outside daimyo")


def test_private_war_subjugation():
    world = build_world()
    world.subjugate_daimyo("A", "B")
    world.require(world.countries["B"].alive, "B still exists")
    world.require(world.countries["B"].overlord == "A", "B's overlord is A")
    world.require(world.countries["B"].subject_type == "mf_retainer_daimyo_vassal", "B is A's retainer daimyo")
    world.require(world.countries["B"].reforms == {"daimyo"}, "B keeps the daimyo reform")
    world.require(world.countries["A"].overlord == "SHO", "A remains under the shogunate")
    world.require(world.countries["A"].subject_type == "daimyo_vassal", "A remains an outside daimyo")


def test_release_extinct_retainer():
    world = build_world()
    world.demand_all_provinces("A", "B")
    world.release_extinct_retainer("A", "B2", "b1")
    world.require(world.countries["B2"].overlord == "A", "released daimyo's overlord is A")
    world.require(world.countries["B2"].subject_type == "mf_retainer_daimyo_vassal", "released daimyo is A's retainer daimyo")
    world.require(world.countries["B2"].reforms == {"daimyo"}, "released daimyo has the daimyo reform")
    world.require(world.countries["A"].overlord == "SHO", "A remains under the shogunate")
    world.require(world.countries["A"].subject_type == "daimyo_vassal", "A remains an outside daimyo")


def test_independent_daimyo_normalization_without_flavor_jap_57():
    world = World()
    world.add_country("A", reforms={"daimyo"}, provinces={"a1"})

    world.normalize_daimyo_reform("A")
    world.require(world.countries["A"].reforms == {"indep_daimyo"}, "mod normalization handles a truly independent daimyo")


def test_fudai_subjugated_by_outside_daimyo():
    assert_private_subjugation_script_chain()
    world = build_world()
    world.add_country("C", reforms={"daimyo"}, provinces={"c1"})
    world.set_subject("B", "SHO", "mf_daimyo_vassal")
    world.normalize_daimyo_reform("B")
    world.set_subject("C", "B", "mf_retainer_daimyo_vassal")
    world.subjugate_daimyo("A", "B")
    world.require(world.countries["B"].overlord == "A", "B's overlord is A")
    world.require(world.countries["B"].subject_type == "mf_retainer_daimyo_vassal", "B becomes a retainer under A")
    world.require(world.countries["B"].reforms == {"daimyo"}, "B no longer keeps the fudai reform")
    world.require(world.countries["C"].overlord == "A", "B's retainer is moved to A")
    world.require(world.countries["C"].subject_type == "mf_retainer_daimyo_vassal", "B's retainer remains a retainer daimyo")
    world.require(world.countries["C"].reforms == {"daimyo"}, "B's retainer keeps the daimyo reform")


def test_direct_shogun_release():
    world = build_world()
    world.countries["SHO"].provinces.add("old1")
    before = world.shogun_authority
    world.release_extinct_direct_daimyo("OLD", "old1")
    world.require(world.countries["OLD"].overlord == "SHO", "released daimyo is direct shogun subject")
    world.require(world.countries["OLD"].subject_type == "daimyo_vassal", "released daimyo is outside daimyo")
    world.require(world.countries["OLD"].reforms == {"daimyo"}, "released daimyo has daimyo reform")
    world.require(world.shogun_authority > before, "direct shogun release raises authority")


def test_return_land_accept_and_decline():
    world = build_world()
    world.countries["A"].provinces.add("old1")
    before = world.shogun_authority
    world.return_land_accept("A", "OLD", "old1")
    world.require(world.countries["OLD"].overlord == "SHO", "returned land restores direct daimyo")
    world.require("mf_recently_returned_daimyo_land" in world.countries["A"].flags, "holder gets return cooldown")
    world.require(world.shogun_authority > before, "accepted return raises authority")

    world = build_world()
    world.countries["A"].provinces.add("old1")
    before = world.shogun_authority
    world.return_land_decline("A", "old1")
    world.require("mf_unlawful_daimyo_land" in world.countries["A"].modifiers, "decline marks unlawful land")
    world.require(world.has_cb("SHO", "A", "cb_mf_return_daimyo_land"), "decline gives return land cb against its holder")
    world.require(world.shogun_authority < before, "decline lowers authority")


def test_lecture_grace_enforce_partition_executor():
    world = build_world()
    before = world.shogun_authority
    world.lecture_daimyo("A")
    world.require("mf_recently_lectured_by_shogun" in world.countries["A"].flags, "lecture cooldown flag is applied")
    world.require("mf_shogunate_lecture" in world.countries["A"].modifiers, "lecture modifier is applied")
    world.require(world.shogun_authority < before, "lecture costs authority")
    before = world.shogun_authority
    world.grace_daimyo("A")
    world.require("mf_shogunate_lecture" not in world.countries["A"].modifiers, "grace removes lecture")
    world.require("mf_shogunate_grace" in world.countries["A"].modifiers, "grace modifier is applied")
    world.require(world.shogun_authority < before, "grace costs authority")

    before = world.shogun_authority
    world.enforce_peace_accept("A", "B")
    world.require(world.shogun_authority < before, "accepted enforcement costs authority")
    before = world.shogun_authority
    world.enforce_peace_decline("A", "B")
    world.require("mf_refused_enforce_daimyo_peace" in world.countries["A"].flags, "declined enforcement is recorded")
    world.require(world.shogun_authority < before, "declined enforcement costs authority")

    world.countries["A"].provinces.add("old1")
    world.partition_decline("A")
    world.require(world.has_cb("SHO", "A", "cb_mf_partition_daimyo"), "partition decline gives cb against its target")
    world.force_partition("A", "OLD", "old1")
    world.require(world.countries["OLD"].overlord == "SHO", "partition restores old daimyo")

    world.appoint_executor("A")
    world.require(world.countries["A"].subject_type == "mf_daimyo_vassal", "executor becomes fudai")
    world.require(world.countries["A"].reforms == {"mf_daimyo"}, "executor has fudai reform")
    world.executor_decline("B")
    world.require("mf_refused_executor_appointment" in world.countries["B"].flags, "executor decline flag is applied")
    world.require(world.has_cb("SHO", "B", "cb_mf_enforce_executor_service"), "executor decline gives cb against its target")


def test_sankin_refusal_and_reform_cleanup():
    world = build_world()
    world.shogun_modifiers.add("shogun_yuling_b")
    world.add_country("C", reforms={"daimyo"}, provinces={"c1"})
    world.set_subject("C", "A", "mf_retainer_daimyo_vassal")
    world.add_country("D", reforms={"daimyo"}, provinces={"d1"})
    world.set_subject("D", "A", "mf_retainer_daimyo_vassal")
    world.countries["A"].yearly_income = 120
    world.countries["A"].treasury = 500
    world.countries["A"].liberty_desire = 60
    world.countries["B"].yearly_income = 120
    world.countries["B"].treasury = 500
    world.countries["B"].liberty_desire = 40
    world.countries["B"].loans = 6
    world.countries["D"].loans = 11

    distance_multiplier, fixed_cost, yearly_income_cost, total_cost = world.sankin_cost(60, 24, 120)
    world.require(distance_multiplier == 2, "sankin distance multiplier follows distance divided by twelve")
    world.require(fixed_cost == 12, "sankin fixed cost follows total development divided by five")
    world.require(yearly_income_cost == 80, "sankin yearly income cost follows income divided by three times distance")
    world.require(total_cost == 92, "sankin total cost combines fixed and yearly costs")
    world.require(world.sankin_refusal_chance(50, 10) == 1.0, "ten-loan daimyo always refuses")
    world.require(abs(world.sankin_refusal_chance(49, 5) - 100 / 110) < 1e-12, "five loans use accept weight ten against refusal weight one hundred")
    world.require(abs(world.sankin_refusal_chance(50, 0) - 100 / 120) < 1e-12, "fifty liberty desire uses accept weight twenty against refusal weight one hundred")
    world.require(abs(world.sankin_refusal_chance(50, 5) - 100 / 102) < 1e-12, "debt and liberty modifiers multiply on the accept option")
    world.require(world.sankin_refusal_chance(49, 0) == 0.5, "unmodified accept and refusal weights are equal")

    targets = world.sankin_targets()
    world.require(targets == ["A", "B", "C", "D"], "annual sankin targets include direct daimyos and their retainers")

    before = world.countries["A"].treasury
    world.accept_sankin("A", 24)
    world.require(world.countries["A"].treasury == before - 92, "accepting sankin removes the combined fixed and yearly cost")
    world.require("mf_sankin_kotai_travel" in world.countries["A"].modifiers, "accepted sankin applies the travel modifier")

    before = world.countries["B"].prestige
    authority_before = world.shogun_authority
    world.refuse_sankin("B")
    world.require(world.countries["B"].prestige == before + 10, "refusing sankin adds prestige")
    world.require("mf_sankin_kotai_refused" in world.countries["B"].modifiers, "refusing sankin applies the refusal modifier")
    world.require(world.shogun_authority == authority_before - 0.5, "refusing sankin lowers shogun authority by point five")
    world.require("mf_refused_sankin_kotai" not in world.countries["B"].flags, "refusing sankin does not set a persistent refusal flag")
    world.require(not world.has_cb("SHO", "B", "cb_disloyal_vassal"), "refusing sankin does not grant a punishment cb")

    world.refuse_sankin("D")
    world.require("mf_sankin_kotai_refused" in world.countries["D"].modifiers, "retainer refusal applies only the temporary modifier")
    world.require(world.can_form_alliance("A", "B"), "daimyos can ally before the formal reform")

    world.complete_sankin_reform()
    world.require("shogun_weixin.h_global_flag" in world.global_flags, "sankin reform flag is recorded")
    world.require("shogun_yuling_b" not in world.shogun_modifiers, "sankin reform clears the temporary edict")
    world.require(world.sankin_targets() == [], "yearly sankin pulse stops after the reform")
    world.require(not world.can_use_sengoku_cb("A", "B"), "sankin reform also closes the sengoku CB")
    for tag in ["B", "D"]:
        world.require("mf_sankin_kotai_refused" not in world.countries[tag].modifiers, f"reform clears {tag}'s refusal modifier")
    world.require("mf_sankin_kotai_travel" not in world.countries["A"].modifiers, "formal reform ends an active sankin journey")
    world.require("jiujizhengshi_2" in world.shogun_modifiers, "formal sankin reform lowers subject-development liberty desire")
    world.require(not world.can_form_alliance("A", "B"), "formal sankin reform forbids alliances between shogunate daimyos")
    world.add_country("X", reforms={"indep_daimyo"}, provinces={"x1"})
    world.add_country("Y", reforms=set(), provinces={"y1"})
    world.require(world.can_form_alliance("X", "Y"), "the shogunate reform does not block external alliances")


def test_internal_war_ban_scope():
    world = build_world()
    world.global_flags.add("shogun_weixin.f_global_flag")
    world.add_country("X", reforms={"daimyo"}, provinces={"x1"})
    world.add_country("Y", reforms={"daimyo"}, provinces={"y1"})
    world.add_country("Z", reforms=set(), provinces={"z1"})
    world.set_subject("X", "SHO", "daimyo_vassal")
    world.set_subject("Y", "SHO", "daimyo_vassal")

    world.require(not world.can_declare_war("X", "Y"), "sibling daimyos cannot declare internal wars once reform 6 is active")
    world.require(world.can_declare_war("X", "SHO"), "independence wars remain allowed")
    world.require(world.can_declare_war("X", "Z"), "external wars remain allowed")


def test_shogunate_transfer_and_layer_cleanup():
    world = build_world()
    world.add_country("C", reforms={"daimyo"}, provinces={"c1"})
    world.set_subject("C", "B", "mf_retainer_daimyo_vassal")
    world.transfer_shogunate("A")
    world.require("shogunate" in world.countries["A"].reforms, "A becomes shogun")
    world.require(world.countries["B"].overlord == "A", "old direct daimyo moves to new shogun")
    world.require(world.countries["C"].overlord == "B", "legal retainer stays under its daimyo")

    world = build_world()
    world.set_subject("B", "SHO", "mf_retainer_daimyo_vassal")
    world.execute_mf_promote_retainer_daimyos_to_shogunate_effect("SHO")
    world.normalize_daimyo_reform("B")
    world.require(world.countries["B"].subject_type == "mf_retainer_daimyo_vassal", "direct shogun retainer stays legal")
    world.require(world.countries["B"].reforms == {"daimyo"}, "direct shogun retainer keeps daimyo reform")

    world = build_world()
    world.set_subject("B", "A", "mf_daimyo_vassal")
    world.demote_illegal_fudai_under_daimyo("B")
    world.require(world.countries["B"].subject_type == "mf_retainer_daimyo_vassal", "non-shogun fudai becomes retainer")
    world.require(world.countries["B"].reforms == {"daimyo"}, "demoted fudai gets daimyo reform")


def test_retainer_daimyo_reform_stability():
    world = build_world()
    world.countries["A"].reforms = {"mf_daimyo"}
    world.set_subject("A", "SHO", "mf_daimyo_vassal")
    world.set_subject("B", "A", "mf_retainer_daimyo_vassal")
    world.countries["B"].reforms = {"daimyo"}

    world.add_country("I", reforms={"indep_daimyo"}, provinces={"i1"})
    world.add_country("C", reforms={"daimyo"}, provinces={"c1"})
    world.set_subject("C", "I", "mf_retainer_daimyo_vassal")

    world.add_country("D", reforms={"daimyo"}, provinces={"d1"})
    world.set_subject("D", "SHO", "mf_retainer_daimyo_vassal")

    world.add_country("T", reforms={"indep_daimyo"}, provinces={"t1"})
    world.set_subject("T", "SHO", "tributary_state")

    world.add_country("V", reforms={"indep_daimyo"}, provinces={"v1"})
    world.set_subject("V", "I", "vassal")
    world.require(not world.reform_potential_valid("V", "indep_daimyo"), "ordinary subjects cannot keep indep_daimyo")

    for _ in range(8):
        for tag, overlord in [("B", "A"), ("C", "I"), ("D", "SHO")]:
            world.require(world.reform_potential_valid(tag, "daimyo"), f"{tag}'s daimyo reform remains valid")
            world.refresh_first_layer_reform_validity(tag)
            world.require(world.countries[tag].reforms == {"daimyo"}, f"{tag} keeps daimyo before normalization")
            world.execute_mf_normalize_daimyo_first_layer_reform_effect(scope=tag)
            world.require(world.countries[tag].overlord == overlord, f"{tag}'s overlord remains stable")
            world.require(
                world.countries[tag].subject_type == "mf_retainer_daimyo_vassal",
                f"{tag} remains a retainer daimyo",
            )
            world.require(world.countries[tag].reforms == {"daimyo"}, f"{tag} keeps daimyo after normalization")

        for tag in ["I", "T"]:
            world.require(world.reform_potential_valid(tag, "indep_daimyo"), f"{tag}'s indep_daimyo remains valid")
            world.refresh_first_layer_reform_validity(tag)
            world.execute_mf_normalize_daimyo_first_layer_reform_effect(scope=tag)
            world.require(world.countries[tag].reforms == {"indep_daimyo"}, f"{tag} keeps indep_daimyo")

        world.refresh_first_layer_reform_validity("V")
        world.execute_mf_normalize_daimyo_first_layer_reform_effect(scope="V")
        world.require("indep_daimyo" not in world.countries["V"].reforms, "ordinary vassal loses indep_daimyo")

    world.require(world.countries["A"].reforms == {"mf_daimyo"}, "fudai overlord keeps mf_daimyo")
    world.require(world.countries["I"].reforms == {"indep_daimyo"}, "independent overlord keeps indep_daimyo")


def test_xiayi_campaign():
    world = build_world()
    world.add_country("XIA", reforms=set(), provinces={"x1"})
    world.set_xiayi_target("XIA")
    world.require(world.cb_mf_xiayi_campaign_available("SHO", "XIA"), "xiayi cb is available for current target")
    world.subjugate_xiayi("XIA")
    world.require(world.countries["XIA"].overlord == "SHO", "xiayi target becomes direct shogun subject")
    world.require(world.countries["XIA"].subject_type == "daimyo_vassal", "xiayi target becomes outside daimyo")
    world.require("mf_xiayi_target" not in world.countries["XIA"].flags, "xiayi target flag is cleared")
    world.require(not world.cb_mf_xiayi_campaign_available("SHO", "XIA"), "xiayi cb disappears after subjugation")


def test_xiayi_campaign_cb_availability():
    world = build_world()
    world.add_country("XIA", reforms=set(), provinces={"x1"})
    world.add_country("OTHER", reforms=set(), provinces={"o1"})
    world.set_xiayi_target("XIA")

    world.require(world.cb_mf_xiayi_campaign_available("SHO", "XIA"), "shogun has xiayi cb against current target")
    world.require(not world.cb_mf_xiayi_campaign_available("SHO", "OTHER"), "shogun has no xiayi cb against non-target")
    world.require(not world.cb_mf_xiayi_campaign_available("A", "XIA"), "daimyo subject does not get xiayi cb")
    world.require("mf_xiayi_target" in world.countries["XIA"].flags, "xiayi target flag is set")
    world.require(world.event_targets.get("xiayi") == "XIA", "xiayi event target points to XIA")


def test_shogun_governance_cbs_coexist():
    world = build_world()
    world.add_country("XIA", reforms=set(), provinces={"x1"})
    world.set_xiayi_target("XIA")
    world.require(world.has_cb("SHO", "XIA", "cb_mf_xiayi_campaign"), "xiayi designation immediately grants its targeted cb")

    world.countries["A"].provinces.add("old1")
    world.return_land_decline("A", "old1")
    world.excommunicate_daimyo("A")
    world.require(world.has_cb("SHO", "A", "cb_mf_return_daimyo_land"), "return-land refusal grants its targeted cb")
    world.require(world.has_cb("SHO", "A", "cb_mf_shogunate_excommunication"), "excommunication grants its targeted cb")
    world.require(world.has_cb("SHO", "XIA", "cb_mf_xiayi_campaign"), "governance cbs do not overwrite the xiayi cb")

    world.add_country("NEW", reforms={"daimyo"}, provinces={"new1"})
    world.transfer_shogunate("NEW")
    world.require(world.has_cb("NEW", "XIA", "cb_mf_xiayi_campaign"), "new shogun inherits the current xiayi campaign cb")


def test_sankin_cost_refusal_and_reform_end():
    world = build_world()
    world.shogun_modifiers.add("shogun_yuling_b")
    world.add_country("C", reforms={"daimyo"}, provinces={"c1"})
    world.set_subject("C", "A", "mf_retainer_daimyo_vassal")

    expected = {
        0: (0.0, 12.0, 0.0, 12.0),
        12: (1.0, 12.0, 40.0, 52.0),
        24: (2.0, 12.0, 80.0, 92.0),
        48: (3.0, 12.0, 120.0, 132.0),
    }
    for distance, result in expected.items():
        world.require(world.sankin_cost(60, distance, 120) == result, f"sankin cost is correct at distance {distance}")

    world.require(abs(world.sankin_refusal_chance(50, 0) - 100 / 120) < 1e-12, "fifty liberty desire multiplies accept weight by point two")
    world.require(abs(world.sankin_refusal_chance(0, 5) - 100 / 110) < 1e-12, "five loans multiply accept weight by point one")
    world.require(world.sankin_refusal_chance(80, 10) == 1.0, "ten loans force refusal even when other modifiers overlap")
    world.require(world.sankin_refusal_chance(0, 0) == 0.5, "base accept and refusal weights are both one hundred")
    world.require(set(world.sankin_targets()) == {"A", "B", "C"}, "yearly sankin covers direct and second-layer daimyo")

    before_treasury = world.countries["A"].treasury
    world.accept_sankin("A", 12)
    world.require(world.countries["A"].treasury == before_treasury - 52, "sankin removes the combined development and income cost")
    before_authority = world.shogun_authority
    world.refuse_sankin("B")
    world.require(world.countries["B"].prestige == 10, "sankin refusal raises daimyo prestige")
    world.require("mf_sankin_kotai_refused" in world.countries["B"].modifiers, "sankin refusal applies its one-year modifier")
    world.require("mf_refused_sankin_kotai" not in world.countries["B"].flags, "sankin refusal does not create a persistent flag")
    world.require(not world.has_cb("SHO", "B", "cb_disloyal_vassal"), "sankin refusal does not create a punishment cb")
    world.require(world.shogun_authority == before_authority - 0.5, "sankin refusal lowers shogun authority by point five")

    world.complete_sankin_reform()
    world.require(world.sankin_targets() == [], "sankin reform stops the yearly event")
    world.require(not world.can_use_sengoku_cb("A", "B"), "sankin reform removes the Onin internal cb")
    world.require("mf_sankin_kotai_refused" not in world.countries["B"].modifiers, "formal reform ends the active refusal modifier")
    world.require("jiujizhengshi_2" in world.shogun_modifiers, "formal reform grants the shogun liberty-desire control")


def test_shogunate_province_marking_and_return():
    world = build_world()
    world.add_country("OUT", reforms=set(), provinces={"o1"})
    world.mark_shogunate_province("a1")
    world.transfer_province("a1", "OUT")
    world.require("mf_shogunate_province" in world.province_flags["a1"], "shogunate province mark survives owner change")
    world.return_marked_shogunate_province("a1")
    world.require(world.owner_of("a1") == "A", "marked province returns to its shogunate home")


def test_transfer_illegal_subject_to_shogun():
    world = build_world()
    world.set_subject("B", "A", "mf_retainer_daimyo_vassal")
    before = world.shogun_authority
    world.transfer_illegal_subject_to_shogun("A", "B")
    world.require(world.countries["B"].overlord == "SHO", "illegal subject is transferred to the shogun")
    world.require(world.countries["B"].subject_type == "daimyo_vassal", "transferred subject becomes direct outside daimyo")
    world.require(world.countries["B"].reforms == {"daimyo"}, "transferred subject receives daimyo reform")
    world.require(world.shogun_authority == before + 2, "accepted illegal-subject transfer raises authority")


def test_excommunication_and_internal_war_boundaries():
    world = build_world()
    world.add_country("C", reforms={"daimyo"}, provinces={"c1"})
    world.add_country("OUT", reforms=set(), provinces={"o1"})
    world.set_subject("C", "A", "mf_retainer_daimyo_vassal")

    before = world.shogun_authority
    world.excommunicate_daimyo("A")
    world.require(not world.can_declare_war("A", "OUT"), "excommunicated daimyo cannot declare an external war")
    world.require(world.countries["A"].subject_type == "daimyo_vassal", "excommunication does not change subject type")
    world.require(world.shogun_authority == before + 2, "excommunication raises shogun authority")

    world.countries["A"].modifiers.discard("mf_shogunate_excommunication")
    world.global_flags.add("shogun_weixin.f_global_flag")
    world.require(not world.can_declare_war("A", "B"), "buke law blocks direct daimyo internal war")
    world.require(not world.can_declare_war("C", "B"), "buke law blocks retainer internal war")
    world.require(world.can_declare_war("A", "OUT"), "buke law allows external war")
    world.require(world.can_declare_war("C", "A"), "buke law preserves independence war against the overlord")


def test_higan_return_hecatia_cb_scope():
    world = World()
    world.add_country("HIG", reforms=set(), provinces={"h1"})
    world.add_country("HEC", reforms=set(), provinces={5327})
    world.add_country("OTHER", reforms=set(), provinces={"o1"})
    world.countries["HIG"].flags.add("hig_has_return_hecatia_war_cb_flag")

    world.require(world.higan_cb_return_hecatia_war_available("HIG", "HEC"), "higan cb works against HEC target")
    world.require(not world.higan_cb_return_hecatia_war_available("HIG", "OTHER"), "higan cb rejects unrelated target while HEC exists")

    world.countries["HEC"].alive = False
    world.countries["OTHER"].provinces.add(5327)
    world.require(world.higan_cb_return_hecatia_war_available("HIG", "OTHER"), "higan cb works against 5327 owner when HEC is missing")


def main():
    tests = [
        test_private_war_annex,
        test_private_war_subjugation,
        test_release_extinct_retainer,
        test_independent_daimyo_normalization_without_flavor_jap_57,
        test_fudai_subjugated_by_outside_daimyo,
        test_direct_shogun_release,
        test_return_land_accept_and_decline,
        test_lecture_grace_enforce_partition_executor,
        test_sankin_refusal_and_reform_cleanup,
        test_internal_war_ban_scope,
        test_shogunate_transfer_and_layer_cleanup,
        test_retainer_daimyo_reform_stability,
        test_xiayi_campaign,
        test_xiayi_campaign_cb_availability,
        test_shogun_governance_cbs_coexist,
        test_sankin_cost_refusal_and_reform_end,
        test_shogunate_province_marking_and_return,
        test_transfer_illegal_subject_to_shogun,
        test_excommunication_and_internal_war_boundaries,
        test_higan_return_hecatia_cb_scope,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
