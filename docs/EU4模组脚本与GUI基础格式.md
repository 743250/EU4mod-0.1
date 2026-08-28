# EU4 模组脚本与 GUI 基础格式

## 文档定位

本文记录本项目反复使用、又容易因为漏字段或套错作用域而失效的 EU4 模组基础格式。它是动手前的格式核对表，不是完整指令手册，也不能代替目标版本原版文件。

资料使用顺序：

1. 先用项目指定 Wiki 确认概念、文件位置和基础骨架。
2. 再查 `v1.37.5.0` 原版中同目录、同类型、同作用域的实际实例。
3. 原版没有相同机制时，再对照已进游戏验证可用的参考模组；优先 Maid 和用户指定的来源模组。
4. 最后用本模组测试、静态检查和新生成的 `error.log` 验证。

Wiki 的一些页面明确标有较早版本信息，只能用于确认基本概念。不能因为 Wiki 给出了一个骨架，就推断未列出的字段、作用域或加载阶段也一定有效。

## 固定参考入口

Wiki：

- [模组制作](https://wiki.cmdz.top/wiki/模组制作.html)
- [事件修改：国家或省份事件](https://wiki.cmdz.top/wiki/事件修改.html#国家或省份事件)
- [作用域](https://wiki.cmdz.top/wiki/作用域.html)
- [条件](https://wiki.cmdz.top/wiki/条件.html)
- [指令](https://wiki.cmdz.top/wiki/指令.html)
- [界面修改](https://wiki.cmdz.top/wiki/界面修改.html)
- [外交行动修改](https://wiki.cmdz.top/wiki/外交行动修改.html)
- [决议修改](https://wiki.cmdz.top/wiki/决议修改.html)
- [本地化](https://wiki.cmdz.top/wiki/本地化.html)
- [On actions](https://wiki.cmdz.top/wiki/On_actions.html)
- [Mod 文件结构](https://wiki.cmdz.top/wiki/Mod文件结构.html)

原版 `v1.37.5.0`：

- `E:\SteamLibrary\steamapps\common\Europa Universalis IV\common\custom_gui\example.txt`
- `E:\SteamLibrary\steamapps\common\Europa Universalis IV\common\custom_gui\mission_previews.txt`
- `E:\SteamLibrary\steamapps\common\Europa Universalis IV\interface\countrymissionsview.gui`
- `E:\SteamLibrary\steamapps\common\Europa Universalis IV\events\BorderFriction.txt`
- `E:\SteamLibrary\steamapps\common\Europa Universalis IV\common\new_diplomatic_actions\00_diplomatic_actions.txt`
- `E:\SteamLibrary\steamapps\common\Europa Universalis IV\common\diplomatic_actions\00_diplomatic_actions.txt`
- `E:\SteamLibrary\steamapps\common\Europa Universalis IV\common\on_actions\00_on_actions.txt`

参考模组：

- `C:\Users\WANG HAO\Documents\Paradox Interactive\Europa Universalis IV\mod\Maid_nations\events\maid_start.txt`
- `C:\Users\WANG HAO\Documents\Paradox Interactive\Europa Universalis IV\mod\Maid_nations\common\new_diplomatic_actions\ms_dip_empire.txt`
- `C:\Users\WANG HAO\Documents\Paradox Interactive\Europa Universalis IV\mod\日本幕府拓展\common\custom_gui\shogun_gui.txt`
- `C:\Users\WANG HAO\Documents\Paradox Interactive\Europa Universalis IV\mod\日本幕府拓展\interface\topbar.gui`
- `C:\Users\WANG HAO\Documents\Paradox Interactive\Europa Universalis IV\mod\天朝修改0.7`
- `E:\SteamLibrary\steamapps\workshop\content\236850\1635373831`

## 通用脚本骨架

EU4 脚本的基本单位是键、值和块：

```txt
key = value

key = {
	child_key = value
}
```

最低规则：

- 使用半角 `=`、`{`、`}` 和 `#`。
- 注释从 `#` 开始；项目脚本注释只写中文。
- 同一条件块内并列条件按引擎的逻辑规则共同判断，不为“看起来整齐”额外套无意义的 `AND`、`OR`、`ROOT` 或事件目标。
- `trigger`、`potential`、`allow`、`is_visible`、`is_allowed` 和 `limit` 中写条件。
- `effect`、`immediate`、`on_accept`、`on_decline` 和事件选项主体中写效果。
- `if = { limit = { 条件 } 效果 }` 是效果环境的条件分支；不要把 `limit` 当成普通顶层条件块。
- 条件遍历通常使用 `any_*`、`all_*`；效果遍历通常使用 `every_*`、`random_*`。使用前必须在原版同类文件中确认具体关键字。
- 进入 `owner = {}`、`overlord = {}`、`FROM = {}`、`event_target:name = {}` 或地区、省份块后，当前作用域已经变化；块内只写该作用域合法的条件或效果。
- 默认作用域已经是目标国家时直接写条件，不重复进入 `ROOT` 或同一个事件目标。

修改任何脚本块后都要检查：

- 花括号总数与嵌套位置。
- 条件是否写进效果环境，或效果是否写进条件环境。
- 每次作用域跳转后的对象类型。
- 使用的 key 是否能在目标版本原版、Wiki 列表或已验证模组中找到。
- 新 `error.log` 是否出现解析错误、未知条件、未知效果或未知修正。

## 事件格式

Wiki 给出的最小事件容器是：

```txt
country_event = {
}

province_event = {
}
```

这两个容器首先决定事件的根作用域。国家事件的 `ROOT` 是国家，省份事件的 `ROOT` 是省份；后续可以通过合法作用域块切换对象。

本项目新增的普通国家事件至少按以下骨架起步：

```txt
namespace = mf_example

country_event = {
	id = mf_example.1
	title = mf_example.1.t
	desc = mf_example.1.d
	picture = DIPLOMACY_eventPicture

	is_triggered_only = yes

	trigger = {
		# 国家条件
	}

	immediate = {
		# 弹窗前必定执行的效果
	}

	option = {
		name = mf_example.1.a
		ai_chance = {
			factor = 100
		}
		# 选择后的效果
	}
}
```

事件核对：

- 文件开头定义 `namespace`，事件 `id` 使用同一命名空间且不重复。
- 可见事件定义合法的 `title`、`desc` 和 `picture`；图片 key 先在原版事件中确认。
- `is_triggered_only = yes` 表示只从事件、on_action、决议、外交行动或其他明确入口触发；它可以继续带 `trigger` 作为入口后的二次筛选。
- `trigger` 只决定事件是否可发生，不执行效果。
- `immediate` 在玩家选择前执行；不希望展示的内容放进 `hidden_effect`。
- 每个可见选项都要有 `name` 本地化；AI 权重写在该选项的 `ai_chance` 中，用 `factor` 和 `modifier` 调整。
- 需要玩家或 AI 选择时不能写成隐藏多选项事件。隐藏事件使用前先查目标版本原版实例，并保持单一路径清楚。
- 事件调用必须写真实事件类型，例如国家作用域使用 `country_event = { id = mf_example.1 }`。
- 事件本地化至少补标题、描述、所有选项；不得留下裸 key。

Wiki 只提供事件的一般结构。新增字段前仍要检查原版同类事件；不能根据名称猜测 `picture`、作用域、触发方式或 AI 字段。

## 决议格式

国家决议必须放在 `country_decisions` 容器内：

```txt
country_decisions = {
	mf_example_decision = {
		major = yes

		potential = {
			# 决议是否出现
		}

		allow = {
			# 决议当前是否可以点击
		}

		effect = {
			# 点击后效果
		}

		ai_will_do = {
			factor = 0
		}
	}
}
```

决议核对：

- `potential` 控制玩家和 AI 是否能看到、考虑该决议。
- `allow` 控制已经出现的决议是否可执行，并向玩家显示未满足条件。
- `effect` 只写执行结果。
- AI 不应使用时明确 `factor = 0`；需要 AI 使用时按原版同类决议写合法权重。
- 一次性决议通常在 `effect` 设置 flag，并在 `potential` 排除该 flag。
- 补齐 `<key>_title` 和 `<key>_desc` 本地化。

## on_action 格式

Wiki 说明从 1.36 起不同文件中的 on_action 会组合加载。目标版本为 1.37.5，仍应新建本模组专用文件，避免复制整份原版 `00_on_actions.txt`。

基础写法：

```txt
on_yearly_pulse = {
	events = {
		mf_example.1
	}

	mf_example_yearly_effect = yes
}
```

或者直接调用事件：

```txt
on_new_heir = {
	if = {
		limit = {
			# 条件
		}
		country_event = {
			id = mf_example.2
		}
	}
}
```

on_action 核对：

- 先在原版 `00_on_actions.txt` 查明入口真实名称和根作用域。
- `events = {}` 中列事件 id；需要延迟、目标或复杂条件时用合法事件调用块。
- 大段效果优先放进命名清楚的 scripted effect，on_action 只保留入口调用。
- 月脉冲和年度脉冲都要严格限定扫描范围；纯 UI 刷新不默认塞进月脉冲。
- 修改后必须用实际坏状态测试，并查看新 `error.log`。

## scripted effect 与 scripted trigger

基础格式：

```txt
mf_example_effect = {
	# 调用处当前作用域下执行的效果
}
```

```txt
mf_example_trigger = {
	# 调用处当前作用域下判断的条件
}
```

项目规则：

- scripted effect 放在 `common/scripted_effects/*.txt`，只能包含效果环境中合法的内容。
- scripted trigger 放在 `common/scripted_triggers/*.txt`，只能包含条件环境中合法的内容。
- 调用时的当前作用域就是定义体的入口作用域，定义本身不会自动切换成国家或省份。
- 本项目禁止由 Codex 新增 scripted trigger；简单条件直接写在调用处。
- 已有 scripted trigger 可能被用户机制使用。展开或删除前必须列出定义、所有调用、次数和用途，等待用户确认。
- 不同数据库目录的加载阶段不完全相同。某个 scripted key 在事件中可用，不代表在 `subject_types` 等更早或特殊加载阶段必然能被识别；必须查原版同目录实例和游戏日志。
- 对游戏中已确认实际生效的既有写法，不因一条孤立告警擅自改写；先复现功能坏状态，再决定是否处理。

## custom GUI 与 interface 绑定格式

这是本项目最重要的格式规则。

原版 `common/custom_gui/example.txt` 明确说明：自定义 `guiButtonType`、`instantTextBoxType`、`iconType` 必须在 `.gui` 元素中直接包含 `scripted = yes` 才能工作。原版还要求 `custom_*` 的 `name` 与 `.gui` 中的控件名完全一致。

类型对应关系：

| `common/custom_gui` 定义 | `interface/*.gui` 控件 |
|---|---|
| `custom_window` | `windowType` |
| `custom_button` | `guiButtonType` |
| `custom_shield` | `guiButtonType` |
| `custom_icon` | `iconType` |
| `custom_text_box` | `instantTextBoxType` |

按钮的最小双文件配对：

```gui
guiTypes = {
	windowType = {
		name = "mf_example_window"
		scripted = yes

		guiButtonType = {
			name = "mf_example_button"
			position = { x = 0 y = 0 }
			quadTextureSprite = "GFX_mf_example_button"
			scripted = yes
		}
	}
}
```

```txt
custom_window = {
	name = mf_example_window
	potential = {
		# 窗口是否显示
	}
}

custom_button = {
	name = mf_example_button

	potential = {
		# 按钮是否显示
	}

	trigger = {
		# 按钮是否可点击
	}

	effect = {
		# 点击效果
	}

	tooltip = mf_example_button.tt
}
```

图标和文本框同样必须双向配对：

```gui
iconType = {
	name = "mf_example_icon"
	spriteType = "GFX_mf_example_icon"
	position = { x = 0 y = 0 }
	scripted = yes
}

instantTextBoxType = {
	name = "mf_example_text"
	position = { x = 0 y = 0 }
	font = "vic_18"
	format = centre
	maxWidth = 100
	maxHeight = 30
	scripted = yes
}
```

```txt
custom_icon = {
	name = mf_example_icon
	potential = {
		# 图标是否显示
	}
	tooltip = mf_example_icon.tt
}

custom_text_box = {
	name = mf_example_text
	potential = {
		# 文本是否显示
	}
	tooltip = mf_example_text.tt
}
```

GUI 核对：

- 每个 `custom_*` 都必须找到同名、正确类型、直属 `scripted = yes` 的 `.gui` 控件。
- 每个带 `scripted = yes` 的自定义控件都必须找到同名 `custom_*` 定义。
- `name` 必须逐字符一致；不要只检查“看起来相似”。
- `custom_window.potential` 为假时，其内部自定义控件不会继续运行自己的 `potential`。
- GUI 对象必须位于原版 `common/custom_gui/example.txt` 支持的父窗口后代中；父窗口决定 `ROOT` 和 `FROM`。
- 不把某个按钮的默认国家作用域经验推广到所有窗口。先查原版 `example.txt` 的父窗口作用域表，再查已验证来源模组。
- `iconType` 的静态贴图通常使用 `spriteType`；动态或多帧贴图按原版实例使用 `quadTextureSprite` 和 `frame`。
- `position` 必须与 `Orientation` 一起理解；不能只按单一分辨率硬猜绝对坐标。
- 修改 `.gui` 后必须完全退出并重启 EU4；不能用热重载结果判断是否成功。
- 同时检查 `.gui`、`common/custom_gui`、`.gfx`、DDS 资源、本地化和入口 flag 链。
- 修改 `topbar.gui` 中已经验证可用的自定义窗口时，保留完整 `topbar.gui` 及原有控件层级。把窗口拆到独立 `.gui` 即使能被 `setup.log` 读取，也不代表游戏会按原父窗口环境注册和显示；没有目标版本原版或进游戏参考实例时不得这样拆分。同名 `topbar.gui` 的模组兼容问题应单独处理加载优先级或制作兼容文件。

本项目静态检查必须维持上述双向配对，不能只检查 GUI 控件到 `custom_gui` 的单向引用。

## 外交行动格式

原版和 Wiki 都明确：新的外交行动位于 `common/new_diplomatic_actions`。调用方是 `ROOT`，目标国家是 `FROM`。

基础骨架：

```txt
mf_example_action = {
	category = influence
	require_acceptance = yes

	is_visible = {
		# ROOT 与 FROM 的可见条件
	}

	is_allowed = {
		# ROOT 与 FROM 的执行条件
	}

	on_accept = {
		# 接受效果
	}

	on_decline = {
		# 拒绝效果
	}

	ai_acceptance = {
		add_entry = {
			name = mf_example_ai_reason
			export_to_variable = {
				variable_name = ai_value
				value = trust
				who = FROM
				with = THIS
			}
		}
	}

	ai_will_do = {
		always = no
	}
}
```

外交行动核对：

- `is_visible`、`is_allowed` 写条件；`on_accept`、`on_decline` 写效果。
- 先在原版文件顶部确认 `ROOT`、`FROM` 的定义，不从事件或和平条款类推。
- `require_acceptance = no` 时不要保留依赖拒绝分支的设计。
- `ai_acceptance` 按目标版本原版格式创建并修改 `ai_value`，不能把事件的 `ai_chance` 格式搬进来。
- `ai_will_do` 在原版新外交行动中是条件块，不是决议权重块；系统不允许 AI 使用时写 `always = no`，不能照搬决议的 `factor = 0`。
- 修改硬编码外交行动限制时，在 `common/diplomatic_actions/00_diplomatic_actions.txt` 的对应行动下使用原版 `condition = { tooltip potential allow }` 结构。
- 补齐 `<action>`、`<action>_title`、`<action>_desc`、`<action>_tooltip`、警告文本和 AI 理由文本。

## 修正、CB、战争目标、和平条款与属国类型

这些数据库没有一个可通用套用的万能骨架。最低规则是：

- 先在原版相同目录找一个功能最接近的完整条目，从顶层 key 开始复制结构。
- 修正 key 先查目标版本原版修正列表和实际文件，不能把效果名猜成修正名。
- CB、战争目标和和平条款要检查相互引用的真实 key、进攻方与目标方作用域，以及文件加载顺序。
- 一个和平条款文件优先只定义一个顶层和平条款，避免前一条解析失败导致后续条目未注册。
- 属国类型的 `is_potential_overlord`、`can_fight_independence_war`、修正块和触发块必须对照原版 `common/subject_types/00_subject_types.txt`。
- 政府改革的 `potential` 决定改革身份能否持续有效。身份型改革必须直接覆盖所有合法属国类型，不能依靠月脉冲反复删除、重加。
- 任何新增 key 都要补本地化，并在新 `error.log` 中检查 `Unknown`、`Parsing Error` 和未注册引用。

## 本地化基本格式

Wiki 给出的基础结构：

```yml
l_english:
 mf_example_title:0 "示例标题"
 mf_example_desc:0 "示例说明"
```

格式核对：

- 第一行是语言头，例如 `l_english:`。
- 每个本地化条目前保留一个空格。
- key 与半角冒号之间不能有空格。
- 文本放在双引号内；文本内双引号按实际文件规则转义。
- 文件名遵循原版语言文件命名方式，例如 `mf_example_l_english.yml`。
- 事件、选项、按钮、tooltip、外交行动、AI 理由、修正、CB、战争目标和和平条款不得留下裸 key。

Wiki 说明本地化文件与普通脚本文件的编码要求不同。中文源文件、游戏读取文件与 ParaTranz Toolbox 转码流程遵循根目录 `AGENTS.md`；编辑时保留目标文件现有编码和 BOM 状态，不手工仿造转码结果。

## 每次修改前的查证流程

1. 确定正在修改的数据库目录和当前根作用域。
2. 打开本文对应章节和 Wiki 基础页。
3. 用 `rg` 在原版同目录查找至少一个同类实例。
4. 若机制来自其他模组，再对照一个已验证可用的来源实现。
5. 只复制所需结构，逐项确认每个 key 在目标版本存在。
6. 先补或更新场景测试，再修改代码。
7. 修改后检查编码、BOM、乱码、花括号、双向引用和本地化。
8. 运行项目静态检查，并在涉及运行期生命周期时检查进游戏 `error.log`。
9. 完全重启游戏，生成新的 `error.log`；只分析时间晚于本次修改的日志。

## 提交前最低检查表

- [ ] 我查过 Wiki 的基础格式页。
- [ ] 我查过目标版本原版同目录实例，不是凭记忆写 key。
- [ ] 我查过相关参考模组，且没有整段覆盖用户的其他改动。
- [ ] 条件、效果和 `limit` 位于正确环境。
- [ ] 每次作用域跳转后的对象类型明确。
- [ ] 所有事件都有合法 id；可见事件有标题、描述、图片和选项。
- [ ] 所有 custom GUI 定义与 `.gui` 控件同名、同类型、双向存在。
- [ ] 所有 custom GUI 控件都直接包含 `scripted = yes`。
- [ ] 所有外交行动按原版确认 `ROOT` 与 `FROM`。
- [ ] 花括号平衡，无新增 BOM、乱码和注释粘连。
- [ ] 没有新增裸本地化 key。
- [ ] 静态检查通过；涉及运行期生命周期时已记录 `error.log` 检查结果。
- [ ] 完全重启游戏，并查看本次生成的新 `error.log`。
