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


@dataclass
class Country:
    tag: str
    overlord: str | None = None
    subject_type: str | None = None
    reforms: set[str] = field(default_factory=set)
    provinces: set[str] = field(default_factory=set)
    modifiers: set[str] = field(default_factory=set)
    flags: set[str] = field(default_factory=set)
    cbs: set[str] = field(default_factory=set)
    alive: bool = True


class World:
    def __init__(self):
        self.countries: dict[str, Country] = {}
        self.event_targets: dict[str, str] = {}
        self.shogun_authority = 50

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

    def normalize_daimyo_reform(self, tag):
        country = self.countries[tag]
        if not (country.reforms & {"daimyo", "mf_daimyo", "indep_daimyo"} or country.subject_type in DAIMYO_SUBJECTS):
            return
        country.reforms -= {"daimyo", "mf_daimyo", "indep_daimyo"}
        if country.subject_type == "mf_daimyo_vassal":
            country.reforms.add("mf_daimyo")
        else:
            country.reforms.add("daimyo")

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
        )

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
        if "shogunate" not in self.countries[scope].reforms:
            return
        for country in self.countries.values():
            if country.overlord == scope and country.subject_type == "mf_retainer_daimyo_vassal":
                self.set_subject(country.tag, scope, "daimyo_vassal")
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
        self.countries["SHO"].cbs.add("cb_mf_return_daimyo_land")
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
        self.countries["SHO"].cbs.add("cb_mf_partition_daimyo")

    def appoint_executor(self, target):
        self.require(not any("mf_shogunate_executor" in c.modifiers for c in self.countries.values()), "no existing executor")
        self.set_subject(target, "SHO", "mf_daimyo_vassal")
        self.normalize_daimyo_reform(target)
        self.countries[target].modifiers.add("mf_shogunate_executor")
        self.shogun_authority += 5

    def executor_decline(self, target):
        self.countries[target].flags.add("mf_refused_executor_appointment")
        self.countries["SHO"].cbs.add("cb_mf_enforce_executor_service")

    def transfer_shogunate(self, new_shogun):
        old_shogun = self.countries["SHO"]
        new = self.countries[new_shogun]
        old_shogun.reforms.discard("shogunate")
        new.reforms.add("shogunate")
        new.overlord = None
        new.subject_type = None
        for country in self.countries.values():
            if country.tag not in {"SHO", new_shogun} and country.overlord == "SHO":
                country.overlord = new_shogun

    def promote_direct_retainer_under_shogun(self, target):
        self.require(self.countries[target].overlord == "SHO", "target is direct subject of shogun")
        self.require(self.countries[target].subject_type == "mf_retainer_daimyo_vassal", "target is direct retainer")
        self.set_subject(target, "SHO", "daimyo_vassal")
        self.normalize_daimyo_reform(target)

    def demote_illegal_fudai_under_daimyo(self, target):
        overlord = self.countries[target].overlord
        self.require(overlord != "SHO", "target is under a non-shogun daimyo")
        self.require(self.countries[target].subject_type == "mf_daimyo_vassal", "target is illegal fudai")
        self.set_subject(target, overlord, "mf_retainer_daimyo_vassal")
        self.normalize_daimyo_reform(target)

    def set_xiayi_target(self, target):
        for country in self.countries.values():
            country.flags.discard("mf_xiayi_target")
        self.countries[target].flags.add("mf_xiayi_target")
        self.event_targets["xiayi"] = target

    def cb_mf_xiayi_campaign_available(self, attacker, target):
        assert_xiayi_cb_script_chain()
        attacker_country = self.countries[attacker]
        target_country = self.countries[target]
        return (
            attacker_country.alive
            and target_country.alive
            and "shogunate" in attacker_country.reforms
            and self.event_targets.get("zhengyidajiangjun") == attacker
            and self.event_targets.get("xiayi") == target
            and "mf_xiayi_target" in target_country.flags
            and target != self.event_targets.get("zhengyidajiangjun")
            and target_country.overlord != self.event_targets.get("zhengyidajiangjun")
            and target_country.subject_type not in DAIMYO_SUBJECTS
            and "sort_of_mf" not in target_country.flags
            and "mf_tianhuang_target" not in target_country.flags
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
        self.normalize_daimyo_reform(target)

    def flavor_jap_57_can_trigger(self, tag):
        country = self.countries[tag]
        return (
            country.alive
            and "daimyo" in country.reforms
            and country.subject_type not in {"daimyo_vassal", "mf_daimyo_vassal", "mf_retainer_daimyo_vassal"}
        )

    @staticmethod
    def require(condition, message):
        if not condition:
            raise AssertionError(message)


def assert_private_subjugation_script_chain():
    treaty_text = read_mod_text("common/peace_treaties/mf_daimyo_peace_treaties.txt")
    treaty = block_between(treaty_text, "po_mf_subjugate_daimyo = {", "po_mf_partition_daimyo = {")
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
    cb = block_between(cb_text, "cb_mf_xiayi_campaign = {", "# A HRE prince has been annexed")
    prerequisites_self = block_between(cb, "prerequisites_self = {", "\n\t}\n\n\tprerequisites = {")
    prerequisites = block_between(cb, "prerequisites = {", "\n\t}\n\n\twar_goal = mf_xiayi_conquest_wg")

    World.require("has_reform = shogunate" in prerequisites_self, "xiayi cb requires shogunate attacker")
    World.require("tag = event_target:zhengyidajiangjun" in prerequisites_self, "xiayi cb attacker must be current shogun")
    World.require("has_country_flag = mf_xiayi_target" in prerequisites, "xiayi cb target must have xiayi flag")
    World.require("tag = event_target:xiayi" in prerequisites, "xiayi cb target must match xiayi event target")
    World.require("FROM = {" not in prerequisites and "from = {" not in prerequisites, "xiayi cb target checks stay in target scope")


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
    world.require(not world.flavor_jap_57_can_trigger("B"), "flavor_jap.57 cannot turn B into an independent daimyo")
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
    world.require(not world.flavor_jap_57_can_trigger("B2"), "flavor_jap.57 cannot turn the released retainer into an independent daimyo")


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
    world.require("cb_mf_return_daimyo_land" in world.countries["SHO"].cbs, "decline gives return land cb")
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
    world.require("cb_mf_partition_daimyo" in world.countries["SHO"].cbs, "partition decline gives cb")
    world.force_partition("A", "OLD", "old1")
    world.require(world.countries["OLD"].overlord == "SHO", "partition restores old daimyo")

    world.appoint_executor("A")
    world.require(world.countries["A"].subject_type == "mf_daimyo_vassal", "executor becomes fudai")
    world.require(world.countries["A"].reforms == {"mf_daimyo"}, "executor has fudai reform")
    world.executor_decline("B")
    world.require("mf_refused_executor_appointment" in world.countries["B"].flags, "executor decline flag is applied")
    world.require("cb_mf_enforce_executor_service" in world.countries["SHO"].cbs, "executor decline gives cb")


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
    world.promote_direct_retainer_under_shogun("B")
    world.require(world.countries["B"].subject_type == "daimyo_vassal", "direct shogun retainer becomes outside daimyo")

    world = build_world()
    world.set_subject("B", "A", "mf_daimyo_vassal")
    world.demote_illegal_fudai_under_daimyo("B")
    world.require(world.countries["B"].subject_type == "mf_retainer_daimyo_vassal", "non-shogun fudai becomes retainer")
    world.require(world.countries["B"].reforms == {"daimyo"}, "demoted fudai gets daimyo reform")


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
        test_fudai_subjugated_by_outside_daimyo,
        test_direct_shogun_release,
        test_return_land_accept_and_decline,
        test_lecture_grace_enforce_partition_executor,
        test_shogunate_transfer_and_layer_cleanup,
        test_xiayi_campaign,
        test_xiayi_campaign_cb_availability,
        test_higan_return_hecatia_cb_scope,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
