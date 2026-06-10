from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def read_text(path):
    return (ROOT / path).read_bytes().decode("utf-8", errors="replace")


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def find_matching_brace(text, open_index):
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unmatched brace")


def iter_top_blocks(text):
    pattern = re.compile(r"^([A-Za-z0-9_]+)\s*=\s*\{", re.MULTILINE)
    for match in pattern.finditer(text):
        name = match.group(1)
        brace = text.find("{", match.start())
        end = find_matching_brace(text, brace)
        yield name, brace, end, text[brace:end + 1]


def get_section(block, section_name):
    marker = f"{section_name} ="
    start = block.find(marker)
    if start == -1:
        return None
    brace = block.find("{", start)
    end = find_matching_brace(block, brace)
    return block[brace:end + 1]


def add_warning(warnings, path, text, index, message):
    warnings.append((path, line_of(text, index), message))


def strip_comments(text):
    lines = []
    for line in text.splitlines():
        lines.append(line.split("#", 1)[0])
    return "\n".join(lines)


def normalize_block(block):
    body = strip_comments(block)
    body = re.sub(r"tooltip\s*=\s*[A-Za-z0-9_.:]+", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body


def iter_sections(text, section_names):
    for section_name in section_names:
        pattern = re.compile(rf"\b{re.escape(section_name)}\s*=\s*\{{")
        for match in pattern.finditer(text):
            brace = text.find("{", match.start())
            end = find_matching_brace(text, brace)
            yield section_name, brace, end, text[brace:end + 1]


def check_commented_code(warnings):
    paths = []
    paths.extend((ROOT / "common" / "new_diplomatic_actions").glob("mf_*.txt"))
    paths.extend((ROOT / "common" / "diplomatic_actions").glob("*.txt"))
    paths.extend((ROOT / "common" / "scripted_triggers").glob("mf_*.txt"))
    paths.extend((ROOT / "common" / "scripted_effects").glob("mf_*.txt"))
    paths.extend((ROOT / "common" / "on_actions").glob("mf_*.txt"))
    paths.extend((ROOT / "common" / "peace_treaties").glob("mf_*.txt"))
    paths.extend((ROOT / "common" / "cb_types").glob("*.txt"))
    paths.extend((ROOT / "common" / "wargoal_types").glob("mf_*.txt"))
    paths.extend((ROOT / "decisions").glob("mf_*.txt"))
    paths.extend((ROOT / "events").glob("mf_*.txt"))
    flavor = ROOT / "events" / "flavorJAP.txt"
    if flavor.exists():
        paths.append(flavor)

    for path in paths:
        text = read_text(path.relative_to(ROOT))
        comment_run = 0
        run_start = 0
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            comment_body = stripped[1:].strip() if stripped.startswith("#") else ""
            looks_like_script = bool(comment_body) and any(
                pattern in comment_body
                for pattern in ["= {", "limit =", "trigger =", "effect =", "is_visible =", "is_allowed =", "option ="]
            )
            if looks_like_script:
                if comment_run == 0:
                    run_start = index
                comment_run += 1
            else:
                if comment_run >= 2:
                    warnings.append((str(path.relative_to(ROOT)), run_start, "发现连续注释掉的旧脚本块，容易变成旧逻辑残留。"))
                comment_run = 0
        if comment_run >= 2:
            warnings.append((str(path.relative_to(ROOT)), run_start, "发现连续注释掉的旧脚本块，容易变成旧逻辑残留。"))


def check_scripted_triggers(warnings):
    trigger_dir = ROOT / "common" / "scripted_triggers"
    all_text = "\n".join(
        read_text(path.relative_to(ROOT))
        for path in ROOT.rglob("*.txt")
    )

    for path in trigger_dir.glob("*.txt"):
        rel = path.relative_to(ROOT)
        text = read_text(rel)
        for name, start, _end, block in iter_top_blocks(text):
            body = block.strip()[1:-1].strip()
            body_without_comments = strip_comments(body).strip()
            if body_without_comments in {"always = yes", "always = no", ""}:
                add_warning(warnings, str(rel), text, start, f"{name} 是空壳触发器。")

            call_count = all_text.count(f"{name} = yes")
            if call_count <= 1:
                add_warning(
                    warnings,
                    str(rel),
                    text,
                    start,
                    f"{name} 只有 {call_count} 个外部调用；清理前应人工确认是否仍有存在价值。",
                )


def check_duplicate_sections(warnings):
    paths = []
    paths.extend((ROOT / "common" / "new_diplomatic_actions").glob("mf_*.txt"))
    paths.extend((ROOT / "decisions").glob("mf_*.txt"))
    paths.extend((ROOT / "missions").glob("mf_*.txt"))

    for path in paths:
        rel = str(path.relative_to(ROOT))
        text = read_text(path.relative_to(ROOT))
        seen = {}
        for section_name, start, _end, block in iter_sections(text, ["is_visible", "is_allowed", "allow", "trigger"]):
            signature = normalize_block(block)
            if len(signature) < 80:
                continue
            if signature in seen:
                old_section, old_line = seen[signature]
                warnings.append((
                    rel,
                    line_of(text, start),
                    f"{section_name} 与第 {old_line} 行的 {old_section} 条件块重复；请确认是否是必要重复。",
                ))
            else:
                seen[signature] = (section_name, line_of(text, start))


def check_redundant_conditions(warnings):
    rel = Path("common/new_diplomatic_actions/mf_diplomatic_actions.txt")
    text = read_text(rel)

    for name, start, _end, block in iter_top_blocks(text):
        for section_name, _section_start, _section_end, section in iter_sections(block, ["is_visible", "is_allowed"]):
            if "NOT = { sort_of_mf = yes }" in section:
                covered = [
                    "NOT = { tag = event_target:zhengyidajiangjun }",
                    "NOT = { is_subject_of = event_target:zhengyidajiangjun }",
                    "NOT = { is_subject_of = ROOT }",
                    "NOT = { has_reform = daimyo }",
                    "NOT = { is_subject_of_type = daimyo_vassal }",
                    "NOT = { is_subject_of_type = mf_daimyo_vassal }",
                    "NOT = { is_subject_of_type = mf_retainer_daimyo_vassal }",
                ]
                hit_count = sum(token in section for token in covered)
                if hit_count:
                    add_warning(
                        warnings,
                        str(rel),
                        text,
                        start,
                        f"{name} 的 {section_name} 在排除 sort_of_mf 后又写了 {hit_count} 个可能被覆盖的排除条件。",
                    )


def check_diplomatic_actions(warnings):
    rel = Path("common/new_diplomatic_actions/mf_diplomatic_actions.txt")
    text = read_text(rel)

    for name, start, _end, block in iter_top_blocks(text):
        visible = get_section(block, "is_visible")
        allowed = get_section(block, "is_allowed")
        if visible is None:
            continue

        root_gate_count = sum(
            token in visible
            for token in [
                "has_reform = shogunate",
                "tag = event_target:zhengyidajiangjun",
            ]
        )
        if root_gate_count == 0:
            add_warning(warnings, str(rel), text, start, f"{name} 的 is_visible 没有明确幕府/将军入口条件。")

        if "FROM = {" in visible:
            shogun_system_exclusions = [
                "NOT = { sort_of_mf = yes }",
                "NOT = { tag = event_target:zhengyidajiangjun }",
                "NOT = { is_subject_of = event_target:zhengyidajiangjun }",
                "NOT = { is_subject_of = ROOT }",
            ]
            hit_count = sum(token in visible for token in shogun_system_exclusions)
            if hit_count >= 3:
                add_warning(
                    warnings,
                    str(rel),
                    text,
                    start,
                    f"{name} 的目标排除条件写得过碎：同时用了 {hit_count} 个幕府体系排除判断。",
                )

            if "NOT = { sort_of_mf = yes }" in visible:
                add_warning(
                    warnings,
                    str(rel),
                    text,
                    start,
                    f"{name} 使用 sort_of_mf 抽象排除目标；需要人工确认它是否正好等于“目标不在幕府体系内”。",
                )

            if "has_country_flag = mf_tianhuang_target" in visible and "xiayi" in name:
                add_warning(
                    warnings,
                    str(rel),
                    text,
                    start,
                    f"{name} 的可见性排除了天皇目标；如果需求只是“目标不是虾夷”，这里需要复核。",
                )

        if allowed and "has_country_flag = mf_xiayi_target" in allowed and "has_country_flag = mf_xiayi_target" not in visible:
            add_warning(
                warnings,
                str(rel),
                text,
                start,
                f"{name} 把“不是当前虾夷目标”放在 is_allowed；若应直接不可见，应移到 is_visible。",
            )


def main():
    warnings = []
    check_commented_code(warnings)
    check_scripted_triggers(warnings)
    check_duplicate_sections(warnings)
    check_redundant_conditions(warnings)
    check_diplomatic_actions(warnings)

    if not warnings:
        print("PASS no script smells found")
        return

    for path, line, message in warnings:
        print(f"WARN {path}:{line}: {message}")


if __name__ == "__main__":
    main()
