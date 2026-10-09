# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import json
from pathlib import Path
from bpy.props import EnumProperty, StringProperty

_STATE = '_maya_suite_language'
_MODULE = __package__

def language():
    state = bpy.app.driver_namespace
    if _STATE not in state:
        try:
            settings = json.loads(_settings_path().read_text(encoding='utf-8'))
            state[_STATE] = settings.get('language', 'EN') if settings.get('default_revision', 0) >= 2 else 'EN'
        except (OSError, ValueError):
            state[_STATE] = 'EN'
    return state[_STATE]

def _settings_path():
    return Path(bpy.utils.user_resource('CONFIG')) / 'maya_tools_language.json'

def get_language(_self):
    return {'ZH': 0, 'EN': 1, 'JA': 2}.get(language(), 1)

def set_language(_self, value):
    chosen = ('ZH', 'EN', 'JA')[value]
    bpy.app.driver_namespace[_STATE] = chosen
    try:
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'language': chosen, 'default_revision': 2}), encoding='utf-8')
    except OSError as error:
        print('Maya Tools: language retained for this session; save failed:', error)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()

_TRANSLATIONS = {'Shared language for all Maya tools': '这几个 Maya 工具共用此语言设置', 'Maya Channels': 'Maya 通道', 'Enable Left Channel List': '开启左侧通道列表', 'Version 1.21 · Press R for Region Box': '版本 1.21 · 按 R 调出编辑框', 'R: Show Editing Box': 'R：调出编辑框', 'B: Box Select Keys': 'B：框选关键帧', 'Show All': '显示全部', 'Restore': '恢复', 'Frame': '聚焦曲线', 'Box Zoom': '框选放大视图', 'Auto Frame': '自动聚焦', 'Frame Range': '聚焦时间范围', 'Current Time Range': '当前视图时间范围', 'Playback Range': '播放区间', 'All Frames': '全部帧', 'Show All Rig Bones': '显示全部骨骼通道', 'Select an animated object or rig.': '请选择带动画的物体或骨架。', 'Shift/Ctrl-click: multiple curves': 'Shift/Ctrl 点击：多选曲线', 'Box: keys only · Click: edit handles': '框选只选关键帧 · 单击可编辑手柄', 'Drag Keys Vertically · Shift: Free': '默认上下拖动 · Shift：自由拖动', 'Thin Curves': '细曲线', 'Handles: selected keys only': '只显示选中关键帧的手柄', 'Loop Start': '设为循环首帧', 'Loop End': '设为循环尾帧', 'Diamond Keys / Triangle Handles': '菱形关键帧 / 三角形手柄', 'Key Size': '关键帧大小', 'Handle Size': '手柄大小', 'Edit Selected Region': '编辑选中区域', 'Inside: move · Shift: vertical only': '拖动框内移动 · Shift：只上下移动', 'Drag edges/corners to scale': '拖动边缘或角点缩放', 'Bounds about center · 100% = original': '以选区中心为基准 · 100% 为原始值', 'Lower Boundary %': '下边界比例 %', 'Upper Boundary %': '上边界比例 %', 'Time Width %': '时间宽度比例 %', 'Apply Percentages': '应用比例', 'Move Values': '上下移动数值', 'Move Time': '左右移动时间', 'Scale Values': '缩放数值幅度', 'Scale Time': '缩放时间间距', 'Automatic: ALL Channels': '全部通道：自动手柄', 'G: move · S: scale · X/Y: axis': 'G：移动 · S：缩放 · X/Y：限制轴', 'Channel changed; choose it again': '通道已变化，请重新选择。', 'Select keyframe points first': '请先选择关键帧。', 'Select only one boundary key per curve': '每条曲线只选择一个首帧或尾帧。', 'Select boundary keys first': '请先选择首帧或尾帧的关键帧。', 'Boundary keys must be on the same frame': '所选关键帧必须位于同一帧。', 'Mark Loop Start for every selected curve first': '请先为每条选中曲线指定循环首帧。', 'Start is missing, ambiguous, or not before End; mark Start again': '首帧不存在、重合或不在尾帧之前，请重新指定首帧。', 'Loop Start saved: ': '已记录循环首帧：', 'Loop End matched: ': '已匹配循环尾帧：', ' curves': ' 条曲线', 'Automatic applied to %d keys across ALL listed channels': '已将所有列出通道的 %d 个关键帧设为自动手柄', 'Drag: vertical only · Shift: free movement · Release: confirm · Esc: cancel': '拖动：只上下 · Shift：自由移动 · 松开：确认 · Esc：取消', 'Drag to select keyframe POINTS · Shift: add · Ctrl: subtract · Esc: cancel': '拖动框选关键帧 · Shift：添加 · Ctrl：减选 · Esc：取消', 'Inside: move · Edges/corners: scale · Shift: vertical only · Enter: finish': '框内移动 · 边角缩放 · Shift：只上下 · Enter：完成', 'Enable a Maya-style channel list on the left; restore editor layout when disabled': '开启左侧 Maya 通道列表；关闭时恢复原布局。', 'Click to isolate and frame; Shift/Ctrl-click to add or remove a curve': '点击单独显示并聚焦曲线；Shift/Ctrl 点击添加或移除曲线。', 'Show all channels belonging to the selected controllers': '显示选中控制器的全部通道。', 'Restore channel visibility and selection from before isolation': '恢复单独显示之前的通道显示与选择。', 'Fit all currently visible curves in the editor': '聚焦当前显示的全部曲线。', 'Drag a rectangle in the graph to zoom into it (also Ctrl+B)': '拖出矩形放大其中的曲线，也可按 Ctrl+B。', 'Drag a box over keyframe points; ignores tangent handles. Shift adds, Ctrl subtracts': '只框选关键帧，忽略手柄；Shift 添加，Ctrl 减选。', 'R: show an editing box around selected keys; without keys, start point-only box selection': 'R：为选中关键帧显示编辑框；没有选择时先框选关键帧。', 'Start preserves the right tangent; End flattens peak/trough seams or matches the start slope. Key values are unchanged': '首帧保留右手柄；尾帧按邻帧高低拉平波峰波谷或匹配斜率，关键帧数值不变。', 'Move or scale selected keyframes; horizontal is time, vertical is value': '移动或缩放所选关键帧；横向是时间，纵向是数值。', 'Set EVERY key on selected controllers to Automatic, regardless of display filter or key selection': '将选中控制器的全部关键帧设为自动手柄，不受显示过滤或关键帧选择影响。', 'Select and Drag Real Key': '选择并拖动关键帧', 'Show Channel': '显示通道', 'Restore Visibility': '恢复显示', 'Frame Curves': '聚焦曲线', 'Expand Controller': '展开控制器', 'Box Select Keyframe Points': '框选关键帧', 'Apply Boundary Percentages': '应用边界比例', 'R: Show Region Transform': 'R：显示区域编辑框', 'Maya Region Move and Scale': 'Maya 区域移动与缩放', 'Set Loop Boundary': '设置循环首尾帧', 'Transform Selected Keyframes': '移动与缩放关键帧', 'Stable Rotate': '稳定旋转球', 'Version 1.9 · ROTATION ONLY': '版本 1.9 · 仅旋转', 'Use Maya Rotate 1.9': '启用 Maya 旋转球 1.9', 'Sphere Size': '旋转球大小', 'Appearance': '外观', 'Opacity': '透明度', 'Color Saturation': '颜色饱和度', 'Line Width': '线条粗细', 'Reset Appearance': '恢复默认外观', '+ / -: resize sphere': '+ / -：调整旋转球大小', 'Edge-on rings: continuous dragging': '侧对视角的圆环：连续旋转', 'Inside sphere: free 3D rotation': '球内拖动：自由三维旋转', 'Yellow ring: rotate around view': '黄色外圈：绕视线旋转', 'Shift: precision · Esc: cancel': 'Shift：精细调整 · Esc：取消', 'Global / Local / View orientation': '全局 / 局部 / 视图坐标方向', 'Stable Rotate %s: %.2f° · Shift: precision · Esc: cancel': '稳定旋转 %s：%.2f° · Shift：精细调整 · Esc：取消', 'Free Rotate · Shift: precision · Esc: cancel': '自由旋转 · Shift：精细调整 · Esc：取消', 'Drag an axis ring continuously; Shift gives precision, Esc cancels': '拖动轴圆环连续旋转；Shift 精细调整，Esc 取消。', 'Rotation rings with continuous edge-on dragging': '即使侧对圆环也能连续旋转。', 'Stable rotation rings for pose bones': '用于姿态骨骼的稳定旋转圆环。', 'Stable Axis Rotation': '稳定轴向旋转', 'Free Sphere Rotation': '自由球形旋转', 'View Ring Rotation': '视图外圈旋转', 'Stable Rotation Rings': '稳定旋转圆环', 'Resize Rotation Sphere': '调整旋转球大小', 'Precision Axes': '精确控制器轴向', 'Version 1.3 · Ctrl+Alt+R': '版本 1.3 · Ctrl+Alt+R', 'Edit Axes: Ctrl+Alt+R': '编辑轴向：Ctrl+Alt+R', 'Axes': '轴向', 'Use These Axes': '应用此轴向', 'Start from Selected Bone/Object': '从选中骨骼或物体获取轴向', 'Load Saved': '载入保存的轴向', 'Load Saved Axes': '载入保存的轴向', 'World XYZ': '世界 XYZ 轴向', 'Tool axes only; rest pose unchanged': '只调整工具轴向，静置姿势保持不变', 'Saved per bone/object after Apply': '应用后分别保存在当前骨骼或物体上', 'Tool axes only — rotation channels keep their original axes': '只调整工具轴向，旋转通道仍使用原来的轴向', 'XYZ Axes': 'XYZ 轴向', 'Angles update the tool rings immediately': '修改角度后旋转圆环立即更新', 'Could not create a tool orientation': '无法创建工具坐标方向。', 'No custom axes saved for this controller yet': '此控制器尚未保存自定义轴向。', 'Use these XYZ angles as the tool coordinate system; bone rest axes and animation remain unchanged': '将这些 XYZ 角度用作工具坐标方向，骨骼静置轴向与动画保持不变。', 'Copy the current bone/object world orientation into the XYZ tool angles': '将当前骨骼或物体的世界轴向复制到工具 XYZ 角度。', 'Ctrl+Alt+R: edit the selected controller rotation-tool axes in a popup': 'Ctrl+Alt+R：在弹窗里编辑选中控制器的旋转工具轴向。', 'Edit Controller Tool Axes': '编辑控制器工具轴向', 'Focus Selected': '聚焦选中', 'Frame the selected objects, bones, keys, nodes, strips or Outliner active item': '聚焦选中的物体、骨骼、关键帧、节点、片段或大纲活动物体。', 'Nothing available to focus in this editor: ': '此编辑器中没有可聚焦的内容：', 'Version 1.24 · Press R for Region Box': '版本 1.24 · 按 R 调出编辑框', 'Channel list loading...': '正在加载通道列表…', 'Generate Loop: Selected Keys': '一键生成循环：所选关键帧', 'Scale Around Selection Center (100%: unchanged)': '按选区中心缩放（100% 保持原样）', 'Help': '功能说明', 'Controllers / Channels': '控制器 / 通道', 'Use the earliest and latest selected key times as loop boundaries; playback range is ignored': '用选中关键帧中最早和最晚的时间作为循环首尾，不使用播放区间。', 'Select keys at two or more different frame times': '请至少选择两个不同时间的关键帧。', 'End must be after Start': '尾帧必须在首帧之后。', 'Overlapping boundary keys found; resolve them before generating': '首尾位置存在重合关键帧，请先处理重合。', 'A selected curve is missing a key at one of the selected boundary times': '有选中曲线缺少对应的首帧或尾帧，操作已取消。', 'No matching Start/End key pairs found in the selected controllers': '选中控制器中没有找到对应的首尾关键帧。', 'Loop generated from selection: %g to %g, %d curves': '已根据选择生成循环：%g 至 %g，共 %d 条曲线'}
_JAPANESE = {'Shared language for all Maya tools': 'すべての Maya ツールで共通の言語設定', 'Maya Channels': 'Maya チャンネル', 'Enable Left Channel List': '左側チャンネル一覧を有効化', 'Version 1.24 · Press R for Region Box': 'バージョン 1.24 · R：編集ボックス', 'R: Show Editing Box': 'R：編集ボックスを表示', 'B: Box Select Keys': 'B：キーを矩形選択', 'Show All': 'すべて表示', 'Restore': '元に戻す', 'Frame': 'カーブを表示範囲に収める', 'Box Zoom': '矩形ズーム', 'Auto Frame': '自動フレーム', 'Frame Range': '表示時間範囲', 'Current Time Range': '現在の表示時間範囲', 'Playback Range': '再生範囲', 'All Frames': '全フレーム', 'Show All Rig Bones': '全ボーンのチャンネルを表示', 'Select an animated object or rig.': 'アニメーション付きオブジェクトかリグを選択してください。', 'Shift/Ctrl-click: multiple curves': 'Shift/Ctrl クリック：複数カーブ選択', 'Box: keys only · Click: edit handles': '矩形選択はキーのみ · クリックでハンドル編集', 'Drag Keys Vertically · Shift: Free': '通常は上下移動 · Shift：自由移動', 'Thin Curves': '細いカーブ', 'Handles: selected keys only': '選択キーのハンドルのみ表示', 'Generate Loop: Selected Keys': 'ループ生成：選択キー', 'Diamond Keys / Triangle Handles': 'ひし形キー / 三角ハンドル', 'Key Size': 'キーの大きさ', 'Handle Size': 'ハンドルの大きさ', 'Edit Selected Region': '選択領域を編集', 'Inside: move · Shift: vertical only': '内側：移動 · Shift：上下のみ', 'Drag edges/corners to scale': '辺や角をドラッグして拡縮', 'Scale Around Selection Center (100%: unchanged)': '選択中心を基準に拡縮（100%：変更なし）', 'Lower Boundary %': '下端の比率 %', 'Upper Boundary %': '上端の比率 %', 'Time Width %': '時間幅の比率 %', 'Apply Percentages': '比率を適用', 'Move Values': '値を上下に移動', 'Move Time': '時間を左右に移動', 'Scale Values': '値の振幅を拡縮', 'Scale Time': '時間間隔を拡縮', 'Automatic: ALL Channels': '全チャンネル：自動ハンドル', 'G: move · S: scale · X/Y: axis': 'G：移動 · S：拡縮 · X/Y：軸を制限', 'Channel list loading...': 'チャンネルを読み込み中…', 'Help': '機能の説明', 'Controllers / Channels': 'コントローラー / チャンネル', 'Stable Rotate': '安定回転球', 'Version 1.9 · ROTATION ONLY': 'バージョン 1.9 · 回転のみ', 'Use Maya Rotate 1.9': 'Maya 回転球 1.9 を有効化', 'Sphere Size': '回転球の大きさ', 'Appearance': '外観', 'Opacity': '不透明度', 'Color Saturation': '彩度', 'Line Width': '線の太さ', 'Reset Appearance': '外観を初期化', '+ / -: resize sphere': '+ / -：回転球の大きさを変更', 'Edge-on rings: continuous dragging': '真横から見たリングも連続回転', 'Inside sphere: free 3D rotation': '球の内側：自由な3D回転', 'Yellow ring: rotate around view': '黄色の外周：視線方向を軸に回転', 'Shift: precision · Esc: cancel': 'Shift：微調整 · Esc：キャンセル', 'Global / Local / View orientation': 'グローバル / ローカル / ビュー座標', 'Precision Axes': 'コントローラーの軸方向', 'Version 1.3 · Ctrl+Alt+R': 'バージョン 1.3 · Ctrl+Alt+R', 'Edit Axes: Ctrl+Alt+R': '軸を編集：Ctrl+Alt+R', 'Axes': '軸方向', 'Use These Axes': 'この軸方向を適用', 'Start from Selected Bone/Object': '選択ボーンまたは物体から取得', 'Load Saved': '保存した軸方向を読み込む', 'Load Saved Axes': '保存した軸方向を読み込む', 'World XYZ': 'ワールド XYZ', 'Tool axes only; rest pose unchanged': 'ツールの軸のみ変更、レストポーズは維持', 'Saved per bone/object after Apply': '適用後、各ボーンまたは物体に保存', 'Tool axes only — rotation channels keep their original axes': 'ツールの軸のみ変更、回転チャンネルの軸は維持', 'XYZ Axes': 'XYZ 軸方向', 'Angles update the tool rings immediately': '角度の変更は回転リングに即時反映', 'Focus Selected': '選択にフォーカス'}
_HELP = {'mgt_lower_percent': ('下边界相对选区中心的距离比例。100% 保持原样，60% 将下边界距离缩至原来的六成。上边界由另一个数值单独控制。输入后点“应用比例”。', 'Scale the lower boundary distance from the selection center. 100% keeps it unchanged; 60% keeps 60% of that distance. Set the upper boundary separately, then Apply Percentages.', '選択中心から下端までの距離の比率。100% は変更なし、60% は元の距離の60%。上端は別に指定し、比率を適用してください。'), 'mgt_upper_percent': ('上边界相对选区中心的距离比例。100% 保持原样，80% 将上边界距离缩至原来的八成。不会改变时间间距。', 'Scale the upper boundary distance from the selection center. 100% keeps it unchanged; 80% keeps 80% of that distance. This does not change timing.', '選択中心から上端までの距離の比率。100% は変更なし、80% は元の距離の80%。時間間隔は変わりません。'), 'mgt_time_percent': ('所选关键帧的时间宽度比例，以选区中心为基准。100% 保持原样，50% 将时间间距减半，不改变关键帧数值。', 'Scale the selected time width about its center. 100% is unchanged; 50% halves the timing intervals without changing key values.', '選択中心を基準に時間幅を拡縮します。100% は変更なし、50% は時間間隔を半分にします。キーの値は維持します。'), 'BOUNDS': ('这是你要求的上下边界独立缩放。以选区中心为基准，分别设置下边界、上边界和时间宽度的比例，再点应用。100% 代表保持原样。', 'Independently scale the lower and upper boundaries about the selection center. Set the lower, upper and time percentages, then apply. 100% means unchanged.', '選択中心を基準に上下の境界を個別に拡縮します。下端、上端、時間幅の比率を指定し適用します。100% は変更なしです。'), 'mgt.generate_loop': ('以所选关键帧中最早和最晚的时间为循环首尾，不使用播放区间。只比较循环内相邻关键帧的高低：波峰或波谷拉平，两侧一高一低匹配 Free 切线。首尾姿势需要你先匹配。', 'Use the earliest and latest selected key times as loop boundaries, ignoring playback range. Neighbor key heights determine flat extrema or matched Free tangents. Match endpoint poses yourself first.', '選択キーの最初と最後の時刻をループ境界にします。再生範囲は使いません。内側の隣接キーの値で山谷を水平にするか Free 接線を一致させます。端点のポーズは先に合わせてください。'), 'mgt_frame_mode': ('这里只控制曲线的显示范围，不决定循环首尾。当前视图保留横向范围；播放区间显示播放范围；全部帧显示整条曲线。', 'Controls only the display range, not loop boundaries. Current keeps the visible time range; Playback uses playback range; All shows the whole curve.', 'カーブの表示範囲のみを指定し、ループ境界には影響しません。現在の範囲、再生範囲、全フレームから選びます。'), 'mgt_auto_frame': ('点击通道或切换控制器时，自动将曲线调整到合适的显示范围，不会改变动画。', 'Automatically frame curves when selecting a channel or controller. Animation data is unchanged.', 'チャンネルやコントローラーの選択時に表示範囲を自動調整します。アニメーションは変更しません。'), 'mgt_all_bones': ('开启后显示整个骨架的通道；关闭时只显示选中的控制器。控制器列表可单独滚动，点击三角可展开或折叠。', 'Show all rig channels when enabled, or only selected controllers when disabled. The channel list scrolls independently; triangles expand or collapse groups.', 'オンで全リグ、オフで選択コントローラーのみ表示。リストは個別にスクロールし、三角で展開または折り畳みます。'), 'mgt_drag_keys': ('直接按住关键帧拖动：默认只上下修改数值；按住 Shift 可同时改变时间和数值。', 'Drag a key directly. Default drag changes values vertically; Shift allows both time and value movement.', 'キーを直接ドラッグします。通常は値を上下に変更し、Shift で時間と値の両方を移動します。'), 'mgt_thin_lines': ('仅调整曲线显示粗细，不改变动画数据。', 'Change curve display thickness only, without modifying animation.', '表示するカーブの太さのみ変更します。アニメーションは維持します。'), 'mgt_maya_markers': ('使用黄色菱形表示关键帧，小三角表示手柄；仅显示选中关键帧的手柄。', 'Draw yellow diamond keys and small triangular handles. Handles appear only for selected keys.', 'キーは黄色いひし形、ハンドルは小さな三角で表示し、選択キーのハンドルのみ表示します。'), 'mgt_key_size': ('调整菱形关键帧的显示大小。', 'Set the displayed diamond key size.', 'ひし形キーの表示サイズを指定します。'), 'mgt_handle_size': ('调整三角手柄的显示大小。', 'Set the displayed triangular handle size.', '三角ハンドルの表示サイズを指定します。'), 'sr_gizmo_scale': ('调整旋转球显示大小，不缩放物体。也可在旋转球工具中按加减号。', 'Resize the rotation sphere without scaling the object. Plus/minus also works in the sphere tool.', '物体を拡縮せず回転球の表示サイズを変更します。球ツールでは +/- でも変更できます。'), 'sr_opacity': ('调整旋转圆环的不透明度：越低越透明。', 'Set ring opacity; lower values are more transparent.', '回転リングの不透明度を設定します。低いほど透明です。'), 'sr_color_depth': ('调整颜色饱和度，使红绿蓝黄更鲜艳或更柔和，不会将颜色变白或变黑。', 'Adjust color saturation for vivid or softer rings, preserving hue and brightness.', '色相と明るさを維持し、彩度を鮮やかまたは柔らかく調整します。'), 'sr_line_width': ('调整旋转圆环线条粗细。', 'Set rotation ring line thickness.', '回転リングの線の太さを設定します。'), 'mca_angles': ('修改当前控制器的旋转工具 XYZ 轴向。只改变工具方向，不改骨骼静置轴向或动画通道。', 'Edit XYZ orientation of the controller rotation tool. Bone rest axes and animation channels are unchanged.', '回転ツールの XYZ 軸方向を編集します。ボーンのレスト軸とアニメーションチャンネルは変更しません。')}

_TRANSLATIONS.update({
    'Version 1.26 · Press R for Region Box': '版本 1.26 · 按 R 调出编辑框',
    'Smooth Inside Loop (Auto Clamped)': '循环内部自动平滑（Auto Clamped）',
})
_JAPANESE.update({
    'Version 1.26 · Press R for Region Box': 'バージョン 1.26 · R：編集ボックス',
    'Smooth Inside Loop (Auto Clamped)': 'ループ内を自動平滑化（Auto Clamped）',
    'Loop generated from selection: %g to %g, %d curves': '選択からループを生成：%g ～ %g、%d カーブ',
})
_HELP['mgt_loop_smooth_inside'] = (
    '生成循环时，先匹配首尾，再将严格位于首尾之间的关键帧手柄设为 Auto Clamped，重算后再次匹配首尾。关键帧数值和选择保持不变。会替换内部手调的切线；需要保留它们时关闭此项。',
    'Match endpoints, set interior key handles to Auto Clamped, recalculate, then match endpoints again. Values and selection stay unchanged. Turn off to preserve hand-edited interior tangents.',
    '端点を合わせ、内側のキーハンドルを Auto Clamped にして再計算し、端点をもう一度合わせます。値と選択は維持します。手動の接線を残す場合はオフにしてください。')

def tr(text):
    chosen = language()
    if not isinstance(text, str) or chosen == 'EN':return text
    translations = _TRANSLATIONS if chosen == 'ZH' else _JAPANESE
    if text in translations:return translations[text]
    prefixes = [('Rotate Quaternion ', '四元数旋转 ', 'クォータニオン回転 '),
                ('Translate ', '位移 ', '移動 '), ('Rotate ', '旋转 ', '回転 '),
                ('Scale ', '缩放 ', 'スケール '), ('Selected: ', '已选：', '選択：')]
    for english, chinese, japanese in prefixes:
        if text.startswith(english):return (chinese if chosen == 'ZH' else japanese)+text[len(english):]
    return text

class LocalizedLayout:
    def __init__(self, layout, help=True):
        object.__setattr__(self, '_layout', layout)
        object.__setattr__(self, '_help', help)
    def __setattr__(self, name, value):
        setattr(self._layout, name, value)
    def __getattr__(self, name):
        attribute = getattr(self._layout, name)
        if name in {'row', 'column', 'box', 'split', 'grid_flow', 'column_flow'}:
            def container(*args, **kwargs):
                return LocalizedLayout(attribute(*args, **kwargs), self._help)
            return container
        if name in {'label', 'operator', 'prop'}:
            def draw(*args, **kwargs):
                if 'text' not in kwargs and name == 'operator':
                    try:
                        category, operator = args[0].split('.')
                        kwargs['text'] = getattr(getattr(bpy.ops, category), operator).get_rna_type().name
                    except (AttributeError, RuntimeError, ValueError):
                        pass
                if 'text' not in kwargs and name == 'prop':
                    kwargs['text'] = args[0].bl_rna.properties[args[1]].name
                if 'text' in kwargs:
                    kwargs['text'] = tr(kwargs['text'])
                    kwargs['translate'] = False
                topic = args[1] if name == 'prop' else args[0] if name == 'operator' else None
                if self._help and topic in _HELP:
                    row = self._layout.row(align=True)
                    result = getattr(row, name)(*args, **kwargs)
                    add_help(row, topic)
                    return result
                return attribute(*args, **kwargs)
            return draw
        return attribute

def ui(layout, help=True):
    return LocalizedLayout(layout, help)

def draw_language(layout, context):
    label = {'EN': 'Language: English', 'ZH': '语言：中文', 'JA': '言語：日本語'}.get(language(), 'Language: English')
    layout.operator(_CYCLE_ID, text=label, icon='WORLD', translate=False)

def preferences_draw(self, context):
    draw_language(self.layout, context)
    ui(self.layout).label(text='Shared language for all Maya tools')

LanguagePreferences = type(_MODULE.replace('.', '_') + '_LanguagePreferences',
    (bpy.types.AddonPreferences,), {
        'bl_idname': _MODULE,
        '__annotations__': {'language': EnumProperty(name='中文 / English / 日本語',
            items=[('ZH', '中文', '中文界面'), ('EN', 'English', 'English interface'), ('JA', '日本語', '日本語の画面')],
            get=get_language, set=set_language)},
        'draw': preferences_draw,
    })

def operator_description(cls, context, properties):
    return tr(getattr(cls, 'bl_description', cls.bl_label))

_HELP_ID = {'MayaGraphTools':'mgt.ui_help', 'StableRotate':'sr.ui_help',
            'PrecisionAxes':'mca.ui_help', 'UniversalFocus':'uf.ui_help'}[_MODULE.split('.')[-1]]

def help_text(topic):
    return _HELP.get(topic, ('', '', ''))[get_language(None)]

def add_help(layout, topic):
    layout.operator(_HELP_ID, text='', icon='QUESTION', emboss=False).topic = topic

def help_label(layout, text, topic):
    row = layout.row(align=True)
    row.label(text=tr(text), translate=False)
    add_help(row, topic)

def help_description(cls, context, properties):
    return help_text(properties.topic)

def help_execute(self, context):
    text = help_text(self.topic)
    def draw(popup, context):
        # Wrap Chinese/Japanese by characters, and English at word boundaries.
        import textwrap
        if language() == 'EN':
            lines = textwrap.wrap(text, width=58)
        else:
            lines = [text[i:i+28] for i in range(0, len(text), 28)]
        for line in lines:popup.layout.label(text=line, translate=False)
    context.window_manager.popup_menu(draw, title=tr('Help'), icon='INFO')
    return {'FINISHED'}

HelpOperator = type(_MODULE.replace('.', '_') + '_Help', (bpy.types.Operator,), {
    'bl_idname': _HELP_ID, 'bl_label': 'Help',
    '__annotations__': {'topic': StringProperty()},
    'description': classmethod(help_description), 'execute': help_execute,
})

_CYCLE_ID = _HELP_ID.replace('ui_help', 'cycle_language')

def cycle_execute(self, context):
    # EN -> ZH -> JA -> EN; enum preference numeric order remains unchanged.
    set_language(None, {'EN': 0, 'ZH': 2, 'JA': 1}.get(language(), 1))
    return {'FINISHED'}

def cycle_description(cls, context, properties):
    return {'EN': 'Switch language: English → 中文 → 日本語 → English',
            'ZH': '点击切换语言：English → 中文 → 日本語 → English',
            'JA': 'クリックで言語切替：English → 中文 → 日本語 → English'}.get(language(), '')

CycleLanguageOperator = type(_MODULE.replace('.', '_') + '_CycleLanguage', (bpy.types.Operator,), {
    'bl_idname': _CYCLE_ID, 'bl_label': 'Switch Language',
    'description': classmethod(cycle_description), 'execute': cycle_execute,
})

def register_language(classes=()):
    # Upgrade the previous Chinese default once; later user choices persist.
    try:
        settings = json.loads(_settings_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        settings = {}
    if settings.get('default_revision', 0) < 2:
        set_language(None, 1)
    bpy.utils.register_class(LanguagePreferences)
    bpy.utils.register_class(HelpOperator)
    bpy.utils.register_class(CycleLanguageOperator)
    for cls in classes:
        if issubclass(cls, bpy.types.Operator):
            cls.description = classmethod(operator_description)
        elif issubclass(cls, bpy.types.Panel):
            title = getattr(cls, '_localized_title', cls.bl_label)
            cls._localized_title = title
            cls.bl_label = ''
            def make_header(title):
                def draw_header(self, context):
                    self.layout.label(text=tr(title), translate=False)
                return draw_header
            cls.draw_header = make_header(title)

def unregister_language():
    bpy.utils.unregister_class(CycleLanguageOperator)
    bpy.utils.unregister_class(HelpOperator)
    bpy.utils.unregister_class(LanguagePreferences)
