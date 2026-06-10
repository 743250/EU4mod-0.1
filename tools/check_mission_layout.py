from __future__ import annotations

import argparse
import dataclasses
import html
import re
import sys
from pathlib import Path


TOKEN_RE = re.compile(r"\{|\}|=|[^\s{}=]+")
LOC_RE = re.compile(r'^\s*([^#\s:]+):\s*(?:\d+\s*)?"(.*)"\s*$')
GROUP_BLOCK_KEYS = {"potential"}


@dataclasses.dataclass
class Atom:
    value: str
    line: int


@dataclasses.dataclass
class Entry:
    key: str
    value: object
    line: int


@dataclasses.dataclass
class Mission:
    key: str
    group: str
    slot: int
    position: int
    required: list[str]
    line: int


@dataclasses.dataclass
class Issue:
    severity: str
    code: str
    message: str


@dataclasses.dataclass(frozen=True)
class LayoutStandard:
    max_col_gap: int
    max_row_gap: int
    fan_in_limit: int

    def lines(self) -> list[str]:
        return [
            "任务树布局观察标准：",
            "- 硬性检查只管脚本坏状态：同格、缺前置、自前置、倒挂前置。",
            "- 审图时重点看整体是否美观、紧凑、叙事线清楚，空位是否有分区或汇合理由。",
            f"- 超过 {self.max_col_gap} 列或 {self.max_row_gap} 行的连线会提示，但不是自动否决。",
            f"- 超过 {self.fan_in_limit} 条的汇入或分叉会提示，需要看图判断是否合理。",
            "- 整行空白、交叉线、贴脸线都是视觉风险；最终以 SVG 和进游戏观感为准。",
        ]


class ParseError(Exception):
    pass


def strip_comment(line: str) -> str:
    return line.split("#", 1)[0]


def tokenize(text: str) -> list[Atom]:
    tokens: list[Atom] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        clean = strip_comment(line)
        for match in TOKEN_RE.finditer(clean):
            tokens.append(Atom(match.group(0), line_no))
    return tokens


class Parser:
    def __init__(self, tokens: list[Atom]) -> None:
        self.tokens = tokens
        self.index = 0

    def peek(self) -> Atom | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def pop(self) -> Atom:
        token = self.peek()
        if token is None:
            raise ParseError("意外到达文件末尾")
        self.index += 1
        return token

    def parse(self) -> list[object]:
        return self.parse_items(stop_on_close=False)

    def parse_items(self, stop_on_close: bool) -> list[object]:
        items: list[object] = []
        while self.peek() is not None:
            token = self.pop()
            if token.value == "}":
                if stop_on_close:
                    return items
                raise ParseError(f"第 {token.line} 行出现多余的右花括号")
            if token.value in {"{", "="}:
                raise ParseError(f"第 {token.line} 行出现无法解析的标记 `{token.value}`")
            next_token = self.peek()
            if next_token is not None and next_token.value == "=":
                self.pop()
                value_token = self.pop()
                if value_token.value == "{":
                    value = self.parse_items(stop_on_close=True)
                elif value_token.value == "}":
                    raise ParseError(f"第 {value_token.line} 行赋值缺少内容")
                else:
                    value = value_token.value
                items.append(Entry(token.value, value, token.line))
            else:
                items.append(token)
        if stop_on_close:
            raise ParseError("文件结束前缺少右花括号")
        return items


def direct_entries(items: list[object], key: str | None = None) -> list[Entry]:
    result: list[Entry] = []
    for item in items:
        if isinstance(item, Entry) and (key is None or item.key == key):
            result.append(item)
    return result


def direct_scalar(items: list[object], key: str) -> str | None:
    for entry in direct_entries(items, key):
        if isinstance(entry.value, str):
            return entry.value
    return None


def direct_block(items: list[object], key: str) -> list[object] | None:
    for entry in direct_entries(items, key):
        if isinstance(entry.value, list):
            return entry.value
    return None


def block_atoms(items: list[object]) -> list[str]:
    return [item.value for item in items if isinstance(item, Atom)]


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def load_missions(path: Path) -> tuple[list[Mission], list[Issue]]:
    issues: list[Issue] = []
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        issues.append(Issue("WARN", "bom", f"{path} 带有 UTF-8 BOM"))
    text = raw.decode("utf-8-sig")
    tree = Parser(tokenize(text)).parse()
    missions: list[Mission] = []
    for group_entry in direct_entries(tree):
        if not isinstance(group_entry.value, list):
            continue
        slot = parse_int(direct_scalar(group_entry.value, "slot"))
        if slot is None:
            continue
        next_position = 1
        for mission_entry in direct_entries(group_entry.value):
            if mission_entry.key in GROUP_BLOCK_KEYS:
                continue
            if not isinstance(mission_entry.value, list):
                continue
            position = parse_int(direct_scalar(mission_entry.value, "position"))
            if position is None:
                position = next_position
            next_position = position + 1
            required_block = direct_block(mission_entry.value, "required_missions")
            required = block_atoms(required_block or [])
            missions.append(
                Mission(
                    key=mission_entry.key,
                    group=group_entry.key,
                    slot=slot,
                    position=position,
                    required=required,
                    line=mission_entry.line,
                )
            )
    return missions, issues


def load_mission_files(paths: list[Path]) -> tuple[list[Mission], list[Issue]]:
    missions: list[Mission] = []
    issues: list[Issue] = []
    for path in paths:
        file_missions, file_issues = load_missions(path)
        missions.extend(file_missions)
        issues.extend(file_issues)
    return missions, issues


def load_localisation(paths: list[Path]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for line in text.splitlines():
            match = LOC_RE.match(line)
            if match:
                key, value = match.groups()
                labels[key] = value.replace(r"\n", "\n")
    return labels


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def default_localisation_paths(mission_paths: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for mission_path in mission_paths:
        root = mission_path.resolve().parent.parent
        loc_root = root / "localisation"
        loc_dir = loc_root / "l_english"
        if loc_root.is_dir():
            paths.extend(sorted(loc_root.glob("*_l_english.yml")))
        if loc_dir.is_dir():
            paths.extend(sorted(loc_dir.glob("*_l_english.yml")))
    return unique_paths(paths)


def edge_intersects(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> bool:
    def orient(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def between(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> bool:
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if o1 == 0 and between(a, c, b):
        return True
    if o2 == 0 and between(a, d, b):
        return True
    if o3 == 0 and between(c, a, d):
        return True
    if o4 == 0 and between(c, b, d):
        return True
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def crossing_reason(e1: tuple[Mission, Mission], e2: tuple[Mission, Mission]) -> bool:
    a, b = e1
    c, d = e2
    shared = {a.key, b.key} & {c.key, d.key}
    if shared:
        return False
    p1 = (float(a.slot), float(a.position))
    p2 = (float(b.slot), float(b.position))
    p3 = (float(c.slot), float(c.position))
    p4 = (float(d.slot), float(d.position))
    if not edge_intersects(p1, p2, p3, p4):
        return False
    return True


def assess(missions: list[Mission], base_issues: list[Issue], standard: LayoutStandard) -> list[Issue]:
    issues = list(base_issues)
    by_key = {mission.key: mission for mission in missions}
    seen: dict[tuple[int, int], Mission] = {}
    children: dict[str, list[Mission]] = {}
    edges: list[tuple[Mission, Mission]] = []

    if len(by_key) != len(missions):
        counts: dict[str, int] = {}
        for mission in missions:
            counts[mission.key] = counts.get(mission.key, 0) + 1
        for key, count in counts.items():
            if count > 1:
                issues.append(Issue("ERROR", "duplicate_key", f"任务 `{key}` 定义了 {count} 次"))

    for mission in missions:
        coord = (mission.slot, mission.position)
        if coord in seen:
            other = seen[coord]
            issues.append(
                Issue(
                    "ERROR",
                    "same_cell",
                    f"`{mission.key}` 与 `{other.key}` 同处 slot={mission.slot}, position={mission.position}",
                )
            )
        else:
            seen[coord] = mission

    if missions:
        occupied_positions = {mission.position for mission in missions}
        for position in range(min(occupied_positions), max(occupied_positions) + 1):
            if position not in occupied_positions:
                issues.append(
                    Issue(
                        "INFO",
                        "empty_row",
                        f"position={position} 是整行空白，会让任务树链条显得断开",
                    )
                )

    for mission in missions:
        if len(mission.required) > standard.fan_in_limit:
            issues.append(
                Issue(
                    "INFO",
                    "too_many_parents",
                    f"`{mission.key}` 有 {len(mission.required)} 个前置，容易形成多线汇入",
                )
            )

        for parent_key in mission.required:
            if parent_key == mission.key:
                issues.append(Issue("ERROR", "self_dependency", f"`{mission.key}` 把自己写成前置"))
                continue
            parent = by_key.get(parent_key)
            if parent is None:
                issues.append(Issue("ERROR", "missing_parent", f"`{mission.key}` 引用了不存在的前置 `{parent_key}`"))
                continue
            edges.append((parent, mission))
            children.setdefault(parent.key, []).append(mission)
            if parent.position >= mission.position:
                issues.append(
                    Issue(
                        "ERROR",
                        "bad_vertical_order",
                        f"`{parent.key}` -> `{mission.key}` 不是向下连接，前置 position={parent.position}，子任务 position={mission.position}",
                    )
                )
            row_gap = mission.position - parent.position
            col_gap = abs(mission.slot - parent.slot)
            if row_gap > standard.max_row_gap:
                issues.append(
                    Issue(
                        "INFO",
                        "large_row_gap",
                        f"`{parent.key}` -> `{mission.key}` 跨 {row_gap} 行，连线会拖得很长",
                    )
                )
            if col_gap > standard.max_col_gap:
                issues.append(
                    Issue(
                        "INFO",
                        "large_col_gap",
                        f"`{parent.key}` -> `{mission.key}` 跨 {col_gap} 列，建议补中间节点或挪列",
                    )
                )

    for parent_key, child_list in children.items():
        if len(child_list) > standard.fan_in_limit:
            child_names = "、".join(child.key for child in sorted(child_list, key=lambda item: (item.position, item.slot)))
            issues.append(Issue("INFO", "too_many_children", f"`{parent_key}` 分出 {len(child_list)} 条线：{child_names}"))

    for index, edge_a in enumerate(edges):
        for edge_b in edges[index + 1 :]:
            if crossing_reason(edge_a, edge_b):
                issues.append(
                    Issue(
                        "INFO",
                        "crossing_edges",
                        f"`{edge_a[0].key}` -> `{edge_a[1].key}` 可能与 `{edge_b[0].key}` -> `{edge_b[1].key}` 交叉",
                    )
                )

    for parent, child in edges:
        if parent.slot != child.slot:
            low = min(parent.position, child.position)
            high = max(parent.position, child.position)
            left = min(parent.slot, child.slot)
            right = max(parent.slot, child.slot)
            for mission in missions:
                if mission.key in {parent.key, child.key}:
                    continue
                if low < mission.position < high and left <= mission.slot <= right:
                    issues.append(
                        Issue(
                            "INFO",
                            "edge_near_node",
                            f"`{parent.key}` -> `{child.key}` 的斜向跨度附近有 `{mission.key}`，游戏内连线可能贴脸或穿过图标",
                        )
                    )
                    break

    return issues


def render_map(missions: list[Mission]) -> str:
    if not missions:
        return "未找到任务。"
    slots = list(range(min(m.slot for m in missions), max(m.slot for m in missions) + 1))
    positions = list(range(min(m.position for m in missions), max(m.position for m in missions) + 1))
    labels = {mission.key: f"M{index:02d}" for index, mission in enumerate(sorted(missions, key=lambda m: (m.position, m.slot, m.key)), start=1)}
    by_coord = {(mission.slot, mission.position): labels[mission.key] for mission in missions}
    lines = ["布局图："]
    header = "pos | " + " ".join(f"s{slot:^4}" for slot in slots)
    lines.append(header)
    lines.append("-" * len(header))
    for position in positions:
        cells = []
        for slot in slots:
            cells.append(f"{by_coord.get((slot, position), '....'):^5}")
        lines.append(f"{position:>3} | " + " ".join(cells))
    lines.append("")
    lines.append("图例：")
    for mission in sorted(missions, key=lambda m: labels[m.key]):
        parents = ", ".join(mission.required) if mission.required else "-"
        lines.append(f"{labels[mission.key]} {mission.key}  slot={mission.slot} position={mission.position}  前置={parents}")
    return "\n".join(lines)


def mission_title(mission: Mission, labels: dict[str, str]) -> str:
    return labels.get(f"{mission.key}_title") or labels.get(mission.key) or mission.key


def short_title(text: str, max_len: int = 11) -> str:
    one_line = text.replace("\n", " ").strip()
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1] + "…"


def svg_text(text: str) -> str:
    clean = "".join(
        ch
        for ch in text
        if ch in "\t\n\r" or ord(ch) >= 0x20
    )
    return html.escape(clean)


def render_svg(missions: list[Mission], labels: dict[str, str]) -> str:
    if not missions:
        return "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n"
    slots = list(range(min(m.slot for m in missions), max(m.slot for m in missions) + 1))
    positions = list(range(min(m.position for m in missions), max(m.position for m in missions) + 1))
    slot_index = {slot: index for index, slot in enumerate(slots)}
    position_index = {position: index for index, position in enumerate(positions)}
    margin_x = 52
    margin_y = 54
    col_w = 180
    row_h = 110
    node_w = 132
    node_h = 46
    width = margin_x * 2 + (len(slots) - 1) * col_w + node_w
    height = margin_y * 2 + (len(positions) - 1) * row_h + node_h + 70

    def center(mission: Mission) -> tuple[float, float]:
        x = margin_x + slot_index[mission.slot] * col_w + node_w / 2
        y = margin_y + position_index[mission.position] * row_h + node_h / 2
        return x, y

    by_key = {mission.key: mission for mission in missions}
    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text{font-family:'Microsoft YaHei','Noto Sans CJK SC',Arial,sans-serif;}",
        ".bg{fill:#17252f;}",
        ".grid{stroke:#34444e;stroke-width:1;opacity:.45;}",
        ".edge{fill:none;stroke:#b8c0c5;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;}",
        ".node{fill:#283842;stroke:#b8c0c5;stroke-width:2;rx:7;}",
        ".nodeText{fill:#f2f3f0;font-size:14px;font-weight:700;text-anchor:middle;dominant-baseline:central;}",
        ".caption{fill:#cad0d3;font-size:12px;}",
        ".title{fill:#f2f3f0;font-size:18px;font-weight:700;}",
        "</style>",
        '<rect class="bg" x="0" y="0" width="100%" height="100%"/>',
        f'<text class="title" x="{margin_x}" y="28">EU4 任务树布局预览</text>',
    ]

    for slot in slots:
        x = margin_x + slot_index[slot] * col_w + node_w / 2
        lines.append(f'<line class="grid" x1="{x:.1f}" y1="{margin_y - 20}" x2="{x:.1f}" y2="{height - 45}"/>')
        lines.append(f'<text class="caption" x="{x - 15:.1f}" y="{height - 18}">slot {slot}</text>')
    for position in positions:
        y = margin_y + position_index[position] * row_h + node_h / 2
        lines.append(f'<text class="caption" x="12" y="{y + 4:.1f}">pos {position}</text>')

    for child in missions:
        child_x, child_y = center(child)
        for parent_key in child.required:
            parent = by_key.get(parent_key)
            if parent is None:
                continue
            parent_x, parent_y = center(parent)
            start_y = parent_y + node_h / 2
            end_y = child_y - node_h / 2
            mid_y = (start_y + end_y) / 2
            points = [
                f"{parent_x:.1f},{start_y:.1f}",
                f"{parent_x:.1f},{mid_y:.1f}",
                f"{child_x:.1f},{mid_y:.1f}",
                f"{child_x:.1f},{end_y:.1f}",
            ]
            lines.append(f'<polyline class="edge" points="{" ".join(points)}"/>')

    for mission in missions:
        x, y = center(mission)
        title = short_title(mission_title(mission, labels))
        tooltip = svg_text(mission.key)
        text = svg_text(title)
        lines.append(f'<g><title>{tooltip}</title><rect class="node" x="{x - node_w / 2:.1f}" y="{y - node_h / 2:.1f}" width="{node_w}" height="{node_h}"/>')
        lines.append(f'<text class="nodeText" x="{x:.1f}" y="{y:.1f}">{text}</text></g>')

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def print_report(paths: list[Path], missions: list[Mission], issues: list[Issue], show_map: bool, standard: LayoutStandard) -> None:
    print("检查文件：")
    for path in paths:
        print(f"- {path}")
    print(f"任务数量：{len(missions)}")
    print()
    print("\n".join(standard.lines()))
    if show_map:
        print()
        print(render_map(missions))
    print()
    if not issues:
        print("未发现布局问题。")
        return
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for issue in sorted(issues, key=lambda item: (order.get(item.severity, 9), item.code, item.message)):
        print(f"[{issue.severity}] {issue.code}: {issue.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 EU4 任务树坐标和前置连线布局。")
    parser.add_argument("files", nargs="*", help="要检查的任务文件；可传多个文件合并成一张任务图")
    parser.add_argument("--max-col-gap", type=int, default=1, help="前置连线允许跨越的最大列数")
    parser.add_argument("--max-row-gap", type=int, default=3, help="前置连线允许跨越的最大行数")
    parser.add_argument("--fan-in-limit", type=int, default=2, help="单个任务建议的最大前置数量")
    parser.add_argument("--map", action="store_true", help="输出坐标图和任务图例")
    parser.add_argument("--svg", type=Path, help="输出 SVG 任务树预览")
    parser.add_argument("--localisation", action="append", type=Path, default=[], help="读取本地化标题，可重复传入")
    parser.add_argument("--strict", action="store_true", help="出现 WARN 时返回失败；INFO 只作为审图提示")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    paths = [Path(file) for file in (args.files or ["missions/mf_shogun_missions.txt"])]
    standard = LayoutStandard(args.max_col_gap, args.max_row_gap, args.fan_in_limit)
    try:
        missions, base_issues = load_mission_files(paths)
        issues = assess(missions, base_issues, standard)
    except (OSError, UnicodeDecodeError, ParseError) as exc:
        print(f"[ERROR] parse: {exc}")
        return 2
    if args.svg is not None:
        loc_paths = args.localisation or default_localisation_paths(paths)
        labels = load_localisation(loc_paths)
        args.svg.write_text(render_svg(missions, labels), encoding="utf-8")
        print(f"SVG 预览已写入：{args.svg}")
        if loc_paths:
            print(f"本地化标题来源：{len(loc_paths)} 个文件")
    print_report(paths, missions, issues, args.map, standard)
    has_error = any(issue.severity == "ERROR" for issue in issues)
    has_warn = any(issue.severity == "WARN" for issue in issues)
    if has_error or (args.strict and has_warn):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
