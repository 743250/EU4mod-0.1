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


def check_commented_code(warnings):
    paths = []
    paths.extend((ROOT / "common" / "new_diplomatic_actions").glob("mf_*.txt"))
    paths.extend((ROOT / "common" / "scripted_triggers").glob("mf_*.txt"))
    paths.extend((ROOT / "common" / "scripted_effects").glob("mf_*.txt"))
    paths.extend((ROOT / "decisions").glob("mf_*.txt"))
    paths.extend((ROOT / "events").glob("mf_*.txt"))

    for path in paths:
        text = read_text(path.relative_to(ROOT))
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") and any(pattern in stripped for pattern in [" = {", "= {"]):
                if not stripped.startswith("# "):
                    warnings.append((str(path.relative_to(ROOT)), index, "发现被注释掉的脚本块，容易变成旧逻辑残留。"))


def check_scripted_triggers(warnings):
    trigger_dir = ROOT / "common" / "scripted_triggers"
    all_text = "\n".join(
        read_text(path.relative_to(ROOT))
        for path in ROOT.rglob("*.txt")
        if "common/scripted_triggers" not in path.as_posix().replace("\\", "/")
    )

    for path in trigger_dir.glob("*.txt"):
        rel = path.relative_to(ROOT)
        text = read_text(rel)
        for name, start, _end, block in iter_top_blocks(text):
            body = block.strip()[1:-1].strip()
            if body == "always = yes":
                add_warning(warnings, str(rel), text, start, f"{name} 是 always = yes 空壳触发器。")

            call_count = all_text.count(f"{name} = yes")
            if call_count <= 1:
                add_warning(
                    warnings,
                    str(rel),
                    text,
                    start,
                    f"{name} 只有 {call_count} 个外部调用；清理前应人工确认是否仍有存在价值。",
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
    check_diplomatic_actions(warnings)

    if not warnings:
        print("PASS no script smells found")
        return

    for path, line, message in warnings:
        print(f"WARN {path}:{line}: {message}")


if __name__ == "__main__":
    main()
