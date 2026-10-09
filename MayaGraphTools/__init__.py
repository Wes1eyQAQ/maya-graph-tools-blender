# SPDX-License-Identifier: GPL-3.0-or-later
bl_info = {
    'name': 'Maya Graph Tools', 'author': 'Codex', 'version': (1, 26, 0),
    'blender': (4, 4, 0), 'location': 'Graph Editor > Maya',
    'description': 'Single-click channel isolation, automatic framing and box zoom',
    'category': 'Animation',
}

import bpy
from .i18n import tr, ui, draw_language, register_language, unregister_language, help_label, language
import re
import math
import ctypes
from bpy.props import BoolProperty, StringProperty, EnumProperty, FloatProperty, IntProperty, CollectionProperty
from bpy.app.handlers import persistent

_visibility = {}
_collapsed = set()
_controller_groups = {}
_keymaps = []
_layouts = {}
_chosen = {}
_scope = {}
_curve_objects = {}
_object_selection = {}
_selection_signatures = {}
_box_bounds = {}
_marker_handler = None
_normalization_cache = {}
_thin_handlers = []
_render_active = {}
_dragging_areas = set()
_loop_starts = {}


def live_object(obj):
    try:
        return obj is not None and bpy.data.objects.get(obj.name) == obj
    except ReferenceError:
        return False


def scoped_objects(context):
    key = area_key(context)
    cached = _scope.get(key)
    if cached is None:
        return list(context.selected_objects)
    if all(live_object(obj) for obj in cached):
        return list(cached)
    # Deletion/undo can invalidate Python RNA wrappers between timer ticks.
    objects = list(context.selected_objects)
    _scope[key] = objects
    _selection_signatures.pop(key, None)
    return objects


def curve_owner(token):
    obj = _curve_objects.get(token)
    if live_object(obj):
        return obj
    _curve_objects.pop(token, None)
    return None


@persistent
def reset_data_caches(*_args):
    # Data can be replaced by file loading or undo. Never retain RNA pointers.
    for cache in (_scope, _curve_objects, _object_selection, _selection_signatures, _controller_groups,
                  _visibility, _chosen, _box_bounds, _normalization_cache, _loop_starts):
        cache.clear()


@persistent
def reset_file_caches(*_args):
    reset_data_caches()
    _layouts.clear()
    _dragging_areas.clear()
    _render_active.clear()


class _NativeFCurve44(ctypes.Structure):
    # Read-only Blender 4.4 DNA_anim_types.h prefix, through its display cache.
    _fields_ = [(name,ctypes.c_void_p) for name in
                ('next','prev','group','driver','mod_first','mod_last','bezt','fpt')] + [
        ('totvert',ctypes.c_uint),('active_index',ctypes.c_int),
        ('curval',ctypes.c_float),('flag',ctypes.c_short),('extend',ctypes.c_short),
        ('smoothing',ctypes.c_char),('padding',ctypes.c_char*3),
        ('array_index',ctypes.c_int),('rna_path',ctypes.c_void_p),
        ('color_mode',ctypes.c_int),('color',ctypes.c_float*3),
        ('factor',ctypes.c_float),('offset',ctypes.c_float)]


def native_normalization(fc):
    # Never guess coordinates on other DNA versions. Native points stay visible.
    if bpy.app.version[:2] != (4,4) or ctypes.sizeof(ctypes.c_void_p) != 8:
        return None
    cache = _NativeFCurve44.from_buffer_copy(ctypes.string_at(fc.as_pointer(),ctypes.sizeof(_NativeFCurve44)))
    if cache.totvert != len(fc.keyframe_points) or cache.array_index != fc.array_index or cache.color_mode not in (0,1,2,3):
        return None
    if not math.isfinite(cache.factor) or not math.isfinite(cache.offset):
        return None
    return (cache.factor or 1.0),cache.offset


def restore_curve_render():
    # Restore only the active display bit; selection, locks and data are untouched.
    for fc,pointer in list(_render_active.values()):
        try:
            if fc.as_pointer()==pointer:
                flag=ctypes.c_short.from_address(pointer+_NativeFCurve44.flag.offset)
                flag.value |= 4
        except ReferenceError:
            pass
    _render_active.clear()


def begin_curve_render():
    restore_curve_render()
    context=bpy.context
    if not context.area or context.area.type!='GRAPH_EDITOR' or area_key(context) not in _layouts or not context.window_manager.mgt_thin_lines or bpy.app.version[:2]!=(4,4):
        return
    for fc in context.visible_fcurves or []:
        if native_normalization(fc) is None:continue
        pointer=fc.as_pointer()
        flag=ctypes.c_short.from_address(pointer+_NativeFCurve44.flag.offset)
        if flag.value & 4:
            _render_active[pointer]=(fc,pointer)
            # Native Blender draws active curves at 2.5px; others at 1px.
            # Limit this change to the synchronous native render pass, without
            # RNA notifications or editing state changes between input events.
            flag.value &= ~4


def marker_mapping(context, fc):
    """Match Blender 4.4's Graph Editor display units, not raw key values."""
    if not context.space_data.use_normalization:
        path = fc.data_path.rsplit('.', 1)[-1]
        factor = math.degrees(1) if path in {'rotation_euler', 'rotation_axis_angle'} and context.scene.unit_settings.system_rotation != 'RADIANS' else 1
        return factor, 0
    return native_normalization(fc)


def marker_geometry(context, with_keys=False):
    """Coordinates from real editable FCurves; never creates animation data."""
    result = []
    for fc in context.visible_fcurves or []:
        if not fc.keyframe_points:
            continue
        mapping = marker_mapping(context, fc)
        if mapping is None:
            continue
        factor, offset = mapping
        owner = curve_owner(str(fc.as_pointer()))
        ad = getattr(owner, 'animation_data', None)
        def pixel(co):
            x = ad.nla_tweak_strip_time_to_scene(co.x) if ad and ad.use_tweak_mode else co.x
            return context.region.view2d.view_to_region(x, (co.y+offset)*factor, clip=False)
        for i, key in enumerate(fc.keyframe_points):
            co = pixel(key.co)
            handles = []
            if context.space_data.show_handles and not fc.lock:
                show = not context.space_data.use_only_selected_keyframe_handles or key.select_control_point or key.select_left_handle or key.select_right_handle
                if show:
                    if (i == 0 and key.interpolation == 'BEZIER') or (i > 0 and fc.keyframe_points[i-1].interpolation == 'BEZIER'):
                        handles.append((pixel(key.handle_left), key.select_left_handle))
                    if key.interpolation == 'BEZIER':
                        handles.append((pixel(key.handle_right), key.select_right_handle))
            item=(co, key.select_control_point, handles)
            result.append((*item,(fc,i)) if with_keys else item)
    return result


def draw_maya_markers():
    context = bpy.context
    if not context.area or context.area.type != 'GRAPH_EDITOR' or area_key(context) not in _layouts or context.space_data.mode != 'FCURVES' or not context.window_manager.mgt_maya_markers:
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    geometry = marker_geometry(context)
    scale = max(1.0, context.preferences.system.ui_scale)
    radius = context.window_manager.mgt_key_size * scale
    handle_radius = max(3.3, context.preferences.themes[0].graph_editor.handle_vertex_size * .7 + .5) * scale
    def draw(verts, primitive, color):
        if verts:
            shader.bind(); shader.uniform_float('color', color)
            batch_for_shader(shader, primitive, {'pos': verts}).draw(shader)
    def shape(center, size, diamond):
        x,y = center
        return [(x-size,y),(x,y+size),(x+size,y),(x,y-size)] if diamond else [(x-size,y-size),(x-size,y+size),(x+size,y+size),(x+size,y-size)]
    fills, outlines, tangents = {}, {}, {}
    def fill(vertices, color):
        for i in range(1,len(vertices)-1):
            fills.setdefault(color,[]).extend((vertices[0],vertices[i],vertices[i+1]))
    def outline(vertices, color):
        for i in range(len(vertices)):
            outlines.setdefault(color,[]).extend((vertices[i],vertices[(i+1)%len(vertices)]))
    gpu.state.blend_set('ALPHA')
    try:
        # Quiet triangular tangent tips; native hit testing stays at the real tip.
        for co, selected, handles in geometry:
            for tip, tip_selected in handles:
                if max(co[0],tip[0]) < 0 or min(co[0],tip[0]) > context.region.width or max(co[1],tip[1]) < 0 or min(co[1],tip[1]) > context.region.height:
                    continue
                tangents.setdefault((.7,.7,.7,1) if selected else (.42,.42,.42,1),[]).extend((co,tip))
                # Cover the native circular tip before drawing a smaller triangle.
                fill(shape(tip,handle_radius,False),(*context.preferences.themes[0].graph_editor.space.back,1))
                vertices = tangent_triangle(co,tip,context.window_manager.mgt_handle_size*scale)
                outline(vertices,(.95,.95,.95,1) if tip_selected else (.55,.55,.55,1))
        for color, vertices in tangents.items(): draw(vertices,'LINES',color)
        for color, vertices in fills.items(): draw(vertices,'TRIS',color)
        for color, vertices in outlines.items(): draw(vertices,'LINES',color)
        fills.clear(); outlines.clear()
        for selected_pass in (False,True):
            for co, selected, handles in geometry:
                if selected != selected_pass or not (-radius < co[0] < context.region.width+radius and -radius < co[1] < context.region.height+radius):
                    continue
                vertices = shape(co,radius,True)
                fill(vertices,(1,.82,.15,1) if selected else (.22,.22,.22,1))
                outline(vertices,(1,.95,.5,1) if selected else (1,.75,.05,1))
            for color, vertices in fills.items(): draw(vertices,'TRIS',color)
            for color, vertices in outlines.items(): draw(vertices,'LINES',color)
            fills.clear(); outlines.clear()
    finally:
        gpu.state.blend_set('NONE')


def tangent_triangle(key, tip, size):
    dx,dy=tip[0]-key[0],tip[1]-key[1]
    length=math.hypot(dx,dy)
    ux,uy=(dx/length,dy/length) if length>1e-8 else (1,0)
    return [(tip[0]+ux*size,tip[1]+uy*size),
            (tip[0]-ux*size*.7-uy*size*.8,tip[1]-uy*size*.7+ux*size*.8),
            (tip[0]-ux*size*.7+uy*size*.8,tip[1]-uy*size*.7-ux*size*.8)]


def selection_signature(context):
    objects = list(context.selected_objects)
    return (getattr(context.active_object, 'name', None),
            tuple(sorted((obj.as_pointer(), obj.mode,
                          tuple(sorted(b.name for b in obj.data.bones if b.select and not b.hide))
                          if obj.type == 'ARMATURE' and obj.mode == 'POSE' else ())
                         for obj in objects)), context.window_manager.mgt_all_bones)


def sync_selection(context, force=False):
    key = area_key(context)
    signature = selection_signature(context)
    if not force and _selection_signatures.get(key) == signature:
        return False
    _scope[key] = list(context.selected_objects)
    # The old controller name in the native search field otherwise keeps the
    # new controller's real curves invisible even when its list has changed.
    _chosen.pop(key, None)
    _box_bounds.pop(key, None)
    context.space_data.dopesheet.filter_fcurve_name = ''
    rows = entries(context)
    remember(context, rows)
    for _, _, _, fc in rows:
        fc.hide = False
        fc.select = True
    _selection_signatures[key] = signature
    context.area.tag_redraw()
    return True


def watch_selection():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'GRAPH_EDITOR' or str(area.as_pointer()) not in _layouts:
                continue
            if str(area.as_pointer()) in _dragging_areas:
                continue
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if not region:
                continue
            try:
                with bpy.context.temp_override(window=window, area=area, region=region):
                    if sync_selection(bpy.context) and bpy.context.window_manager.mgt_auto_frame:
                        frame_visible(bpy.context)
                    refresh_channel_list(bpy.context)
            except (ReferenceError, RuntimeError):
                pass
    return .15


def curve_filter(fc):
    path = fc.data_path.rsplit('.', 1)[-1]
    names = {'location': 'Location', 'rotation_euler': 'Euler Rotation',
             'rotation_quaternion': 'Quaternion Rotation', 'scale': 'Scale'}
    if path in names:
        axes = 'WXYZ' if path == 'rotation_quaternion' else 'XYZ'
        label = axes[fc.array_index] + ' ' + names[path]
        bone = re.match(r'pose\.bones\["((?:\\.|[^"\\])*)"\]', fc.data_path)
        if bone:
            label += ' (' + bone.group(1) + ')'
        return label
    return path


def action_curves(owner):
    """Resolve only the owner's slot, including Blender 4.4 layered actions."""
    ad = getattr(owner, 'animation_data', None)
    if not ad or not ad.action:
        return []
    action = ad.action
    if getattr(action, 'is_action_layered', False):
        slot = getattr(ad, 'action_slot', None)
        if slot is None:
            return []
        result = []
        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, 'channelbag'):
                    bag = strip.channelbag(slot)
                    if bag:
                        result.extend(bag.fcurves)
        return result
    return list(action.fcurves)


def default_controller_folds(context, rows):
    key = area_key(context)
    current = list(dict.fromkeys(row[0] for row in rows))
    previous = _controller_groups.get(key, ())
    # Retain the first selected controller when additional ones are added.
    ordered = tuple([name for name in previous if name in current] +
                    [name for name in current if name not in previous])
    if ordered != previous:
        if ordered:
            _collapsed.discard(ordered[0])
            _collapsed.update(ordered[1:])
        _controller_groups[key] = ordered
    order = {name: index for index, name in enumerate(ordered)}
    return sorted(rows, key=lambda row: order[row[0]])


def entries(context):
    result, seen = [], set()
    objects = scoped_objects(context)
    if not objects and context.active_object:
        objects = [context.active_object]
    for obj in objects:
        selected_bones = None
        if obj.type == 'ARMATURE' and obj.mode == 'POSE' and not getattr(context.window_manager, 'mgt_all_bones', False):
            selected_bones = {b.name for b in obj.data.bones if b.select and not b.hide}
        owners = [obj]
        if obj.data:
            owners.append(obj.data)
            keys = getattr(obj.data, 'shape_keys', None)
            if keys:
                owners.append(keys)
        for owner in owners:
            for fc in action_curves(owner):
                token = str(fc.as_pointer())
                if token in seen:
                    continue
                seen.add(token)
                _curve_objects[token] = obj
                bone = re.match(r'pose\.bones\["((?:\\.|[^"\\])*)"\](.*)', fc.data_path)
                if selected_bones is not None and (not bone or bone.group(1) not in selected_bones):
                    continue
                controller = obj.name
                path = fc.data_path
                if bone:
                    controller += ' / ' + bone.group(1)
                    path = bone.group(2).lstrip('.')
                elif owner != obj:
                    controller += ' / ' + owner.name
                names = {'location': 'Translate', 'rotation_euler': 'Rotate',
                         'rotation_quaternion': 'Rotate Quaternion',
                         'rotation_axis_angle': 'Rotate Axis Angle', 'scale': 'Scale'}
                if path in names:
                    axes = 'WXYZ' if path in ('rotation_quaternion', 'rotation_axis_angle') else 'XYZ'
                    axis = axes[fc.array_index] if fc.array_index < len(axes) else str(fc.array_index)
                    label = names[path] + ' ' + axis
                else:
                    label = path + (' [' + str(fc.array_index) + ']' if fc.array_index else '')
                result.append((controller, label, token, fc))
    return default_controller_folds(context, result)


def area_key(context):
    return str(context.area.as_pointer())


def remember(context, rows):
    saved = _visibility.setdefault(area_key(context), {})
    for _, _, token, fc in rows:
        if token not in saved:
            saved[token] = (fc, fc.select)


def restore(context):
    for fc, selected in _visibility.pop(area_key(context), {}).values():
        try:
            fc.select = selected
        except (ReferenceError, RuntimeError):
            pass
    _chosen.pop(area_key(context), None)
    context.space_data.dopesheet.filter_fcurve_name = ''


def fit_view_bounds(context, bounds):
    region = next(r for r in context.area.regions if r.type == 'WINDOW')
    xmin, xmax, ymin, ymax = bounds
    # Unclipped region coordinates allow exact ranges even beyond the old view.
    x0, y0 = region.view2d.view_to_region(xmin, ymin, clip=False)
    x1, y1 = region.view2d.view_to_region(xmax, ymax, clip=False)
    with context.temp_override(region=region):
        bpy.ops.view2d.zoom_border('EXEC_DEFAULT', xmin=x0, xmax=x1, ymin=y0, ymax=y1,
                                  wait_for_input=False)


def frame_visible(context, mode=None):
    region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
    if not region:
        return
    mode = mode or context.window_manager.mgt_frame_mode
    with context.temp_override(region=region):
        if mode == 'ALL':
            bpy.ops.graph.view_all(include_handles=False)
            return
        if mode == 'PLAYBACK':
            scene = context.scene
            xmin, xmax = ((scene.frame_preview_start, scene.frame_preview_end)
                          if scene.use_preview_range else (scene.frame_start, scene.frame_end))
        else:
            xmin = region.view2d.region_to_view(0, 0)[0]
            xmax = region.view2d.region_to_view(region.width, 0)[0]
        if xmax <= xmin:
            xmax = xmin + 1
        curves = list(context.visible_fcurves or [])
        if not curves:
            return
        # Ask Blender for display-space bounds: normalization, rotation units and
        # NLA display transforms do not share the raw FCurve.evaluate units.
        saved = []
        has_points = False
        try:
            for fc in curves:
                points = list(fc.keyframe_points)
                in_range = [i for i, kp in enumerate(points) if xmin <= kp.co.x <= xmax]
                if not in_range and points:
                    before = [i for i, kp in enumerate(points) if kp.co.x < xmin]
                    after = [i for i, kp in enumerate(points) if kp.co.x > xmax]
                    in_range = ([before[-1]] if before else []) + ([after[0]] if after else [])
                selected_indices = set(in_range)
                for i, kp in enumerate(points):
                    saved.append((kp, kp.select_control_point, kp.select_left_handle, kp.select_right_handle))
                    kp.select_control_point = i in selected_indices
                    kp.select_left_handle = kp.select_right_handle = False
                has_points |= bool(in_range)
            if has_points:
                bpy.ops.graph.view_selected(include_handles=False)
            else:
                bpy.ops.graph.view_all(include_handles=False)
            ymin = region.view2d.region_to_view(0, 0)[1]
            ymax = region.view2d.region_to_view(0, region.height)[1]
            fit_view_bounds(context, (xmin, xmax, ymin, ymax))
        finally:
            for kp, control, left, right in saved:
                kp.select_control_point, kp.select_left_handle, kp.select_right_handle = control, left, right


class MGT_OT_marker_click(bpy.types.Operator):
    bl_idname = 'mgt.marker_click'
    bl_label = 'Select and Drag Real Key'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls,context):
        return context.area and context.area.type=='GRAPH_EDITOR' and area_key(context) in _layouts and context.window_manager.mgt_maya_markers

    def invoke(self,context,event):
        if event.alt or event.ctrl or context.region.type!='WINDOW':
            return {'PASS_THROUGH'}
        start=(event.mouse_region_x,event.mouse_region_y)
        if event.value=='CLICK_DRAG':
            start=(event.mouse_prev_press_x-context.region.x,event.mouse_prev_press_y-context.region.y)
        radius=max(7,context.window_manager.mgt_key_size+2)*max(1.0,context.preferences.system.ui_scale)
        best=None
        nearest_handle=None
        for co,selected,handles,key_ref in marker_geometry(context,with_keys=True):
            distance=math.hypot(co[0]-start[0],co[1]-start[1])
            if distance<=radius and (best is None or distance<best[0]):best=(distance,co,selected,key_ref)
            for tip,_ in handles:
                handle_distance=math.hypot(tip[0]-start[0],tip[1]-start[1])
                if nearest_handle is None or handle_distance<nearest_handle:nearest_handle=handle_distance
        if best is None:return {'PASS_THROUGH'}
        # A small tangent beside a dense key must remain individually editable.
        handle_radius=max(3,context.window_manager.mgt_handle_size+1)*max(1.0,context.preferences.system.ui_scale)
        if nearest_handle is not None and nearest_handle<=handle_radius and nearest_handle+.2<best[0]:return {'PASS_THROUGH'}
        # Snap the click to the genuine native key center, preserving native selection.
        if not best[2]:
            bpy.ops.graph.clickselect('EXEC_DEFAULT',mouse_x=best[1][0],mouse_y=best[1][1],extend=event.shift)
            # Dense curves may make native selection prefer a nearby tangent.
            # The diamond hit identifies the actual point, so explicitly select it.
            best[3][0].keyframe_points[best[3][1]].select_control_point=True
            best[3][0].select=True
        context.space_data.show_handles=True
        context.space_data.use_only_selected_keyframe_handles=True
        context.area.tag_redraw()
        if not context.window_manager.mgt_drag_keys:
            return {'FINISHED'}
        for fc in context.visible_fcurves or []:
            for kp in fc.keyframe_points:
                kp.select_left_handle=kp.select_right_handle=False
        self.snapshot=selected_snapshot(context)
        if not self.snapshot:return {'FINISHED'}
        self.area,self.region,self.space=context.area,context.region,context.space_data
        self.start=start
        self.previous=self.start
        self.total_x=self.total_y=0.0
        self.dragging=False
        self.auto_normalization=self.space.use_auto_normalization
        self.auto_merge=self.space.use_auto_merge_keyframes
        self.space.use_auto_merge_keyframes=False
        self.work=[]
        for fc,records in self.snapshot:
            mapping=marker_mapping(context,fc)
            if mapping is None:continue
            owner=curve_owner(str(fc.as_pointer()))
            ad=getattr(owner,'animation_data',None)
            time_scale=ad.nla_tweak_strip_time_to_scene(1)-ad.nla_tweak_strip_time_to_scene(0) if ad and ad.use_tweak_mode else 1.0
            self.work.append((fc,[r for r in records if r[3]],mapping[0],time_scale,owner))
        # Use the native display cache unchanged for the whole drag.
        self.space.use_auto_normalization=False
        _dragging_areas.add(area_key(context))
        context.window_manager.modal_handler_add(self)
        self.area.header_text_set(tr('Drag: vertical only · Shift: free movement · Release: confirm · Esc: cancel'))
        if event.value=='CLICK_DRAG':self.move(context,event)
        return {'RUNNING_MODAL'}

    def finish(self):
        _dragging_areas.discard(str(self.area.as_pointer()))
        self.space.use_auto_normalization=self.auto_normalization
        self.space.use_auto_merge_keyframes=self.auto_merge
        self.area.header_text_set(None)
        self.area.tag_redraw()

    def modal(self,context,event):
        if event.type in {'ESC','RIGHTMOUSE'} and event.value=='PRESS':
            restore_snapshot(self.snapshot)
            self.finish()
            return {'CANCELLED'}
        if event.type=='LEFTMOUSE' and event.value=='RELEASE':
            self.finish()
            return {'FINISHED'}
        if event.type=='MOUSEMOVE':self.move(context,event)
        return {'RUNNING_MODAL'}

    def move(self,context,event):
        current=(event.mouse_x-self.region.x,event.mouse_y-self.region.y)
        if not self.dragging and math.hypot(current[0]-self.start[0],current[1]-self.start[1])<3:return
        self.dragging=True
        old=self.region.view2d.region_to_view(*self.previous)
        new=self.region.view2d.region_to_view(*current)
        if event.shift:self.total_x+=new[0]-old[0]
        self.total_y+=new[1]-old[1]
        self.previous=current
        apply_key_drag(self.work,self.total_x,self.total_y)
        self.area.tag_redraw()


def update_curve_preserve_keys(fc):
    # FCurve.update() also deduplicates overlapping times. Sorting and handle
    # recalculation are separate operations, so crossing another key is safe.
    fc.keyframe_points.sort()
    fc.keyframe_points.handles_recalc()


def apply_key_drag(work,dx,dy):
    # Update only selected keys directly. No new transform operator, full snapshot
    # restoration, or extra undo entry on every mouse sample.
    for fc,records,value_scale,time_scale,owner in work:
        keys=[k for k in fc.keyframe_points if k.select_control_point]
        if len(keys)!=len(records):continue
        offset=(dx/time_scale,dy/value_scale)
        for k,record in zip(keys,records):
            for name,original in zip(('co','handle_left','handle_right'),record[:3]):
                setattr(k,name,(original.x+offset[0],original.y+offset[1]))
        update_curve_preserve_keys(fc)
        if owner:owner.update_tag(refresh={'TIME'})


class MGT_OT_toggle(bpy.types.Operator):
    bl_idname = 'mgt.toggle'
    bl_label = 'Maya Channels'
    bl_description = 'Enable a Maya-style channel list on the left; restore editor layout when disabled'

    def execute(self, context):
        space = context.space_data
        key = area_key(context)
        if key in _layouts:
            restore(context)
            channels, ui, flipped, selected_filter, curve_name, handles, selected_handles = _layouts.pop(key)
            if flipped:
                region = next((r for r in context.area.regions if r.type == 'UI'), None)
                if region:
                    with context.temp_override(region=region):
                        bpy.ops.screen.region_flip()
            space.show_region_channels, space.show_region_ui = channels, ui
            space.dopesheet.show_only_selected = selected_filter
            space.dopesheet.filter_fcurve_name = curve_name
            space.show_handles = handles
            space.use_only_selected_keyframe_handles = selected_handles
            original_objects, original_active = _object_selection.pop(key, ([], None))
            for obj in context.view_layer.objects:
                obj.select_set(obj in original_objects)
            if live_object(original_active) and original_active.name in context.view_layer.objects:
                context.view_layer.objects.active = original_active
            _scope.pop(key, None)
            _selection_signatures.pop(key, None)
        else:
            _scope[key] = list(context.selected_objects)
            _object_selection[key] = (list(context.selected_objects), context.view_layer.objects.active)
            region = next((r for r in context.area.regions if r.type == 'UI'), None)
            flipped = bool(region and region.alignment == 'RIGHT')
            _layouts[key] = (space.show_region_channels, space.show_region_ui,
                             flipped, space.dopesheet.show_only_selected,
                             space.dopesheet.filter_fcurve_name, space.show_handles,
                             space.use_only_selected_keyframe_handles)
            space.show_region_channels = False
            space.show_region_ui = True
            # Keep the editor scoped to selected objects, matching the channel list.
            space.dopesheet.show_only_selected = True
            space.show_handles = True
            space.use_only_selected_keyframe_handles = True
            if flipped:
                with context.temp_override(region=region):
                    bpy.ops.screen.region_flip()
            sync_selection(context, force=True)
        context.area.tag_redraw()
        return {'FINISHED'}


class MGT_OT_channel(bpy.types.Operator):
    bl_idname = 'mgt.channel'
    bl_label = 'Show Channel'
    bl_description = 'Click to isolate and frame; Shift/Ctrl-click to add or remove a curve'
    token: StringProperty()
    additive: BoolProperty(default=False, options={'SKIP_SAVE'})

    def invoke(self, context, event):
        self.additive = event.shift or event.ctrl
        return self.execute(context)

    def execute(self, context):
        if area_key(context) not in _layouts:
            bpy.ops.mgt.toggle()
        sync_selection(context)
        rows = entries(context)
        chosen = next((fc for _, _, token, fc in rows if token == self.token), None)
        if chosen is None:
            self.report({'WARNING'}, tr('Channel changed; choose it again'))
            return {'CANCELLED'}
        key = area_key(context)
        was_isolated = key in _visibility
        remember(context, rows)
        selected = _chosen.setdefault(key, set())
        if not self.additive or not was_isolated:
            selected.clear()
            selected.add(self.token)
        elif self.token in selected:
            selected.remove(self.token)
        else:
            selected.add(self.token)
        for _, _, token, fc in rows:
            # Migrate earlier native/manual hiding. Display isolation never sets
            # hide=True, and every listed channel stays available to bulk edits.
            fc.hide = False
            fc.select = token in selected
        context.space_data.dopesheet.filter_fcurve_name = curve_filter(chosen) if len(selected) == 1 else ''
        target_objects = {owner for t in selected if (owner := curve_owner(t)) is not None}
        for obj in context.view_layer.objects:
            obj.select_set(obj in target_objects)
        target_obj = curve_owner(self.token)
        if target_obj:
            context.view_layer.objects.active = target_obj
        # Selected-object filtering also checks pose-bone selection.
        bone = re.match(r'pose\.bones\["((?:\\.|[^"\\])*)"\]', chosen.data_path)
        if bone:
            for obj in target_objects:
                if obj.type == 'ARMATURE' and bone.group(1) in obj.data.bones:
                    obj.data.bones[bone.group(1)].select = True
        # Our own channel click can narrow object selection. It must not be
        # mistaken for the user choosing a different controller in another view.
        _selection_signatures[key] = selection_signature(context)
        if context.window_manager.mgt_auto_frame:
            frame_visible(context)
        context.area.tag_redraw()
        return {'FINISHED'}


class MGT_OT_all(bpy.types.Operator):
    bl_idname = 'mgt.show_all'
    bl_label = 'Show All'
    bl_description = 'Show all channels belonging to the selected controllers'

    def execute(self, context):
        rows = entries(context)
        remember(context, rows)
        for _, _, _, fc in rows:
            fc.hide = False
            fc.select = True
        _chosen[area_key(context)] = {r[2] for r in rows}
        context.space_data.dopesheet.filter_fcurve_name = ''
        for obj in scoped_objects(context):
            obj.select_set(True)
        if context.window_manager.mgt_auto_frame:
            frame_visible(context)
        context.area.tag_redraw()
        return {'FINISHED'}


class MGT_OT_restore(bpy.types.Operator):
    bl_idname = 'mgt.restore'
    bl_label = 'Restore Visibility'
    bl_description = 'Restore channel visibility and selection from before isolation'

    def execute(self, context):
        restore(context)
        context.area.tag_redraw()
        return {'FINISHED'}


class MGT_OT_frame(bpy.types.Operator):
    bl_idname = 'mgt.frame'
    bl_label = 'Frame Curves'
    bl_description = 'Fit all currently visible curves in the editor'

    def execute(self, context):
        frame_visible(context)
        return {'FINISHED'}


class MGT_OT_zoom(bpy.types.Operator):
    bl_idname = 'mgt.box_zoom'
    bl_label = 'Box Zoom'
    bl_description = 'Drag a rectangle in the graph to zoom into it (also Ctrl+B)'

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'GRAPH_EDITOR'

    def invoke(self, context, event):
        region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        if region:
            with context.temp_override(region=region):
                bpy.ops.view2d.zoom_border('INVOKE_DEFAULT', wait_for_input=True)
            return {'FINISHED'}
        return {'CANCELLED'}


class MGT_OT_fold(bpy.types.Operator):
    bl_idname = 'mgt.fold'
    bl_label = 'Expand Controller'
    controller: StringProperty()

    def execute(self, context):
        if self.controller in _collapsed:
            _collapsed.remove(self.controller)
        else:
            _collapsed.add(self.controller)
        context.area.tag_redraw()
        return {'FINISHED'}


def select_key_rectangle(curves, bounds, extend=False, subtract=False):
    xmin, xmax, ymin, ymax = bounds
    for fc in curves:
        for kp in fc.keyframe_points:
            inside = xmin <= kp.co.x <= xmax and ymin <= kp.co.y <= ymax
            if inside:
                kp.select_control_point = not subtract
            elif not extend and not subtract:
                kp.select_control_point = False
            # Never select a tangent handle on its own.
            kp.select_left_handle = False
            kp.select_right_handle = False


class MGT_OT_box_keys(bpy.types.Operator):
    bl_idname = 'mgt.box_keys'
    bl_label = 'Box Select Keyframe Points'
    bl_description = 'Drag a box over keyframe points; ignores tangent handles. Shift adds, Ctrl subtracts'

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'GRAPH_EDITOR' and area_key(context) in _layouts

    def invoke(self, context, event):
        self.region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        if not self.region:
            return {'CANCELLED'}
        self.area = context.area
        self.start = None
        self.end = None
        self.handle = bpy.types.SpaceGraphEditor.draw_handler_add(self.draw_box, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self.area.header_text_set(tr('Drag to select keyframe POINTS · Shift: add · Ctrl: subtract · Esc: cancel'))
        return {'RUNNING_MODAL'}

    def draw_box(self):
        if self.start is None or bpy.context.area != self.area:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        x, y = self.start
        ex, ey = self.end
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        vertices = [(x, y), (ex, y), (ex, ey), (x, ey), (x, y)]
        batch = batch_for_shader(shader, 'LINE_STRIP', {'pos': vertices})
        shader.bind()
        shader.uniform_float('color', (0.2, 0.7, 1.0, 1.0))
        batch.draw(shader)

    def finish(self):
        bpy.types.SpaceGraphEditor.draw_handler_remove(self.handle, 'WINDOW')
        self.area.header_text_set(None)
        self.area.tag_redraw()

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.finish()
            return {'CANCELLED'}
        x, y = event.mouse_x - self.region.x, event.mouse_y - self.region.y
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if not (0 <= x < self.region.width and 0 <= y < self.region.height):
                return {'RUNNING_MODAL'}
            self.start = self.end = (x, y)
        elif event.type == 'MOUSEMOVE' and self.start is not None:
            self.end = (x, y)
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self.start is not None:
            select_key_box_pixels(context, self.region, self.start, (x, y), event.shift, event.ctrl)
            a = self.region.view2d.region_to_view(*self.start)
            b = self.region.view2d.region_to_view(x, y)
            _box_bounds[area_key(context)] = (min(a[0],b[0]), max(a[0],b[0]), min(a[1],b[1]), max(a[1],b[1]))
            self.finish()
            with context.temp_override(region=self.region):
                if selected_snapshot(context):
                    bpy.ops.mgt.region_edit('INVOKE_DEFAULT')
            return {'FINISHED'}
        self.area.tag_redraw()
        return {'RUNNING_MODAL'}


def select_key_box_pixels(context, region, start, end, extend=False, subtract=False):
    # Blender performs the hit test in actual display coordinates, including
    # Normalize, degree units and NLA time transforms. Handles never participate.
    with context.temp_override(region=region):
        bpy.ops.graph.select_box('EXEC_DEFAULT',
            xmin=int(min(start[0], end[0])), xmax=int(max(start[0], end[0])),
            ymin=int(min(start[1], end[1])), ymax=int(max(start[1], end[1])),
            include_handles=False, use_curve_selection=False, wait_for_input=False,
            mode='SUB' if subtract else 'ADD' if extend else 'SET')
        for fc in context.visible_fcurves or []:
            for kp in fc.keyframe_points:
                kp.select_left_handle = kp.select_right_handle = False


def selected_snapshot(context):
    region = next(r for r in context.area.regions if r.type == 'WINDOW')
    result = []
    with context.temp_override(region=region):
        for fc in context.visible_fcurves or []:
            if fc.lock or not any(k.select_control_point for k in fc.keyframe_points):
                continue
            records = [(k.co.copy(), k.handle_left.copy(), k.handle_right.copy(),
                        k.select_control_point, k.select_left_handle, k.select_right_handle)
                       for k in fc.keyframe_points]
            result.append((fc, records))
    return result


def restore_snapshot(snapshot):
    for fc, records in snapshot:
        for k, (co, left, right, selected, sl, sr) in zip(fc.keyframe_points, records):
            k.co, k.handle_left, k.handle_right = co, left, right
            k.select_control_point, k.select_left_handle, k.select_right_handle = selected, sl, sr
        update_curve_preserve_keys(fc)


def apply_boundary_percent(snapshot, lower=100, upper=100, time=100):
    points = [r[0] for _, records in snapshot for r in records if r[3]]
    if not points:
        return
    xmin,xmax = min(p.x for p in points),max(p.x for p in points)
    ymin,ymax = min(p.y for p in points),max(p.y for p in points)
    cx,cy = (xmin+xmax)/2,(ymin+ymax)/2
    sx,sy = time/100,(lower+upper)/200
    dy = (upper-lower)/200 * (ymax-ymin)/2
    for fc, records in snapshot:
        for k, record in zip(fc.keyframe_points, records):
            if not record[3]:
                continue
            for attr, original in zip(('co','handle_left','handle_right'),record[:3]):
                setattr(k,attr,(cx+(original.x-cx)*sx,cy+(original.y-cy)*sy+dy))
            k.select_left_handle=k.select_right_handle=False
        update_curve_preserve_keys(fc)


class MGT_OT_boundary_scale(bpy.types.Operator):
    bl_idname = 'mgt.boundary_scale'
    bl_label = 'Apply Boundary Percentages'
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        snapshot=selected_snapshot(context)
        if not snapshot:
            self.report({'WARNING'},tr('Select keyframe points first'))
            return {'CANCELLED'}
        wm=context.window_manager
        apply_boundary_percent(snapshot,wm.mgt_lower_percent,wm.mgt_upper_percent,wm.mgt_time_percent)
        key=area_key(context)
        if key in _box_bounds:
            x0,x1,y0,y1=_box_bounds[key]
            cx,cy=(x0+x1)/2,(y0+y1)/2
            _box_bounds[key]=(cx+(x0-cx)*wm.mgt_time_percent/100,
                              cx+(x1-cx)*wm.mgt_time_percent/100,
                              cy+(y0-cy)*wm.mgt_lower_percent/100,
                              cy+(y1-cy)*wm.mgt_upper_percent/100)
        context.area.tag_redraw()
        return {'FINISHED'}


def bounds_from_selected(context, region):
    view = region.view2d
    a,b=view.region_to_view(0,0),view.region_to_view(region.width,region.height)
    old=(a[0],b[0],a[1],b[1])
    smooth=context.preferences.view.smooth_view
    try:
        context.preferences.view.smooth_view=0
        with context.temp_override(region=region):
            bpy.ops.graph.view_selected(include_handles=False)
            a,b=view.region_to_view(0,0),view.region_to_view(region.width,region.height)
            # Native display-space framing includes degrees and Normalize.
            padx,pady=(b[0]-a[0])*.02,(b[1]-a[1])*.02
            return (a[0]+padx,b[0]-padx,a[1]+pady,b[1]-pady)
    finally:
        fit_view_bounds(context,old)
        context.preferences.view.smooth_view=smooth


class MGT_OT_region_hotkey(bpy.types.Operator):
    bl_idname='mgt.region_hotkey'
    bl_label='R: Show Region Transform'
    bl_description='R: show an editing box around selected keys; without keys, start point-only box selection'

    @classmethod
    def poll(cls,context):
        return context.area and context.area.type=='GRAPH_EDITOR'

    def invoke(self,context,event):
        if area_key(context) not in _layouts:
            bpy.ops.mgt.toggle()
        region=next(r for r in context.area.regions if r.type=='WINDOW')
        with context.temp_override(region=region):
            if selected_snapshot(context):
                _box_bounds.pop(area_key(context),None)
                bpy.ops.mgt.region_edit('INVOKE_DEFAULT')
            else:
                bpy.ops.mgt.box_keys('INVOKE_DEFAULT')
        return {'FINISHED'}


class MGT_OT_region_edit(bpy.types.Operator):
    bl_idname='mgt.region_edit'
    bl_label='Maya Region Move and Scale'
    bl_options={'REGISTER','UNDO','BLOCKING'}

    @classmethod
    def poll(cls,context):
        return context.area and context.area.type=='GRAPH_EDITOR' and area_key(context) in _layouts

    def invoke(self,context,event):
        self.snapshot=selected_snapshot(context)
        if not self.snapshot:
            return {'CANCELLED'}
        self.region=next(r for r in context.area.regions if r.type=='WINDOW')
        self.area=context.area
        self.bounds=_box_bounds.get(area_key(context))
        if not self.bounds:
            self.bounds=bounds_from_selected(context,self.region)
            _box_bounds[area_key(context)]=self.bounds
        self.drag=None
        self.handle=bpy.types.SpaceGraphEditor.draw_handler_add(self.draw_region,(),'WINDOW','POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self.area.header_text_set(tr('Inside: move · Edges/corners: scale · Shift: vertical only · Enter: finish'))
        return {'RUNNING_MODAL'}

    def pixels(self):
        a=self.region.view2d.view_to_region(self.bounds[0],self.bounds[2],clip=False)
        b=self.region.view2d.view_to_region(self.bounds[1],self.bounds[3],clip=False)
        return a[0],b[0],a[1],b[1]

    def draw_region(self):
        if bpy.context.area!=self.area:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        x0,x1,y0,y1=self.pixels();cx,cy=(x0+x1)/2,(y0+y1)/2
        verts=[(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
        shader=gpu.shader.from_builtin('UNIFORM_COLOR');shader.bind()
        shader.uniform_float('color',(.2,.8,1,1))
        batch_for_shader(shader,'LINE_STRIP',{'pos':verts}).draw(shader)
        squares=[]
        for x,y in ((x0,y0),(cx,y0),(x1,y0),(x0,cy),(x1,cy),(x0,y1),(cx,y1),(x1,y1)):
            squares.extend(((x-4,y-4),(x+4,y-4),(x+4,y+4),(x-4,y-4),(x+4,y+4),(x-4,y+4)))
        batch_for_shader(shader,'TRIS',{'pos':squares}).draw(shader)

    def finish(self):
        bpy.types.SpaceGraphEditor.draw_handler_remove(self.handle,'WINDOW')
        self.area.header_text_set(None);self.area.tag_redraw()

    def modal(self,context,event):
        if self.drag is None and event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE','MIDDLEMOUSE','NDOF_MOTION'}:
            return {'RUNNING_MODAL','PASS_THROUGH'}
        if self.drag is None and event.value=='PRESS' and event.type in {'G','S','B','R','F','N'}:
            self.finish();return {'FINISHED','PASS_THROUGH'}
        if event.type in {'ESC','RIGHTMOUSE','RET','NUMPAD_ENTER'}:
            if self.drag and event.type in {'ESC','RIGHTMOUSE'}:
                restore_snapshot(self.snapshot)
                self.bounds=self.original_bounds
            _box_bounds[area_key(context)]=self.bounds
            self.finish();return {'FINISHED'}
        x,y=event.mouse_x-self.region.x,event.mouse_y-self.region.y
        if event.type=='LEFTMOUSE' and event.value=='PRESS':
            x0,x1,y0,y1=self.pixels()
            if not (x0-10<=x<=x1+10 and y0-10<=y<=y1+10):
                self.finish();return {'FINISHED','PASS_THROUGH'}
            ex=-1 if abs(x-x0)<10 else 1 if abs(x-x1)<10 else 0
            ey=-1 if abs(y-y0)<10 else 1 if abs(y-y1)<10 else 0
            self.drag=(ex,ey)
            self.start=(x,y);self.original_bounds=self.bounds
            self.snapshot=selected_snapshot(context)
        elif event.type=='LEFTMOUSE' and event.value=='RELEASE' and self.drag is not None:
            self.drag=None
            _box_bounds[area_key(context)]=self.bounds
        elif event.type=='MOUSEMOVE' and self.drag is not None:
            restore_snapshot(self.snapshot)
            a=self.region.view2d.region_to_view(*self.start)
            b=self.region.view2d.region_to_view(x,y)
            dx,dy=b[0]-a[0],b[1]-a[1]
            x0,x1,y0,y1=self.original_bounds
            ex,ey=self.drag
            with context.temp_override(region=self.region):
                if not ex and not ey:
                    if event.shift:dx=0
                    bpy.ops.transform.translate('EXEC_DEFAULT',False,value=(dx,dy,0))
                    self.bounds=(x0+dx,x1+dx,y0+dy,y1+dy)
                else:
                    nx0,nx1=(min(x0+dx,x1-.001),x1) if ex<0 else (x0,max(x1+dx,x0+.001)) if ex>0 else (x0,x1)
                    ny0,ny1=(min(y0+dy,y1-.001),y1) if ey<0 else (y0,max(y1+dy,y0+.001)) if ey>0 else (y0,y1)
                    if event.shift:nx0,nx1=x0,x1
                    sx=(nx1-nx0)/max(.001,x1-x0);sy=(ny1-ny0)/max(.001,y1-y0)
                    anchor=(x1 if ex<0 else x0,y1 if ey<0 else y0,0)
                    bpy.ops.transform.resize('EXEC_DEFAULT',False,value=(sx,sy,1),center_override=anchor)
                    self.bounds=(nx0,nx1,ny0,ny1)
            self.area.tag_redraw()
        elif event.type=='MOUSEMOVE':
            return {'RUNNING_MODAL','PASS_THROUGH'}
        return {'RUNNING_MODAL'}


def freeze_key_handles(key):
    left, right = key.handle_left.copy(), key.handle_right.copy()
    key.handle_left_type = key.handle_right_type = 'FREE'
    key.handle_left, key.handle_right = left, right


def loop_boundary_sides(fc, start, end):
    # Classify using only the nearest interior KEY values. Handle overshoot,
    # interpolation and curve shape must never change this decision.
    inside = sorted((k for k in fc.keyframe_points if start.co.x < k.co.x < end.co.x),
                    key=lambda k: k.co.x)
    following = inside[0] if inside else end
    preceding = inside[-1] if inside else start
    def side(key, other):
        delta = other.co.y - key.co.y
        tolerance = 1e-7 * max(1.0, abs(delta))
        return (1 if delta > 0 else -1) if abs(delta) > tolerance else 0
    return side(start, following), side(end, preceding)


def match_loop_end(fc, start, end):
    # Read the current start tangent so edits made after marking it are respected.
    dx = start.handle_right.x - start.co.x
    dy = start.handle_right.y - start.co.y
    previous = [k.co.x for k in fc.keyframe_points if start.co.x <= k.co.x < end.co.x]
    span = end.co.x - max(previous)
    length = span / 3.0
    outgoing, incoming = loop_boundary_sides(fc, start, end)
    freeze_key_handles(end)
    if outgoing != 0 and outgoing == incoming:
        # Same side of the seam: peak (both below) or trough (both above).
        # Mirror the local inside length onto the outside tangent as requested.
        # Flatten all four handles so a remote neighbour cannot leave a long
        # outside tangent behind. Non-extremum seams keep the old behaviour.
        freeze_key_handles(start)
        start_length = abs(start.handle_right.x - start.co.x)
        start.handle_right = (start.co.x + start_length, start.co.y)
        start.handle_left = (start.co.x - start_length, start.co.y)
        end.handle_left = (end.co.x - length, end.co.y)
        end.handle_right = (end.co.x + length, end.co.y)
    elif abs(dx) > 1e-8:
        end.handle_left = (end.co.x - length, end.co.y - length * dy / dx)
    elif abs(dy) > 1e-8:
        end.handle_left = (end.co.x, end.co.y - math.copysign(length, dy))
    else:
        end.handle_left = end.co
    update_curve_preserve_keys(fc)


def finish_loop(fc, start, end, smooth_inside=True):
    match_loop_end(fc, start, end)
    if smooth_inside:
        for key in fc.keyframe_points:
            if start.co.x < key.co.x < end.co.x:
                key.handle_left_type = key.handle_right_type = 'AUTO_CLAMPED'
        update_curve_preserve_keys(fc)
        # Leave endpoint handles Free and reapply the boundary rule after the
        # interior tangent recalculation. Neither values nor selection change.
        match_loop_end(fc, start, end)


class MGT_OT_generate_loop(bpy.types.Operator):
    bl_idname = 'mgt.generate_loop'
    bl_label = 'Generate Loop'
    bl_description = 'Use the earliest and latest selected key times as loop boundaries; playback range is ignored'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'GRAPH_EDITOR'

    def execute(self, context):
        # Resolve the two TIME boundaries first, before mutating any handles.
        # Use the selected controller scope, independent of channel isolation.
        rows = entries(context)
        curves = list(dict.fromkeys(row[3] for row in rows)) if rows else list(context.visible_fcurves or [])
        curves = [fc for fc in curves if not fc.lock]
        curves = [fc for fc in curves if any(k.select_control_point for k in fc.keyframe_points)]
        times = sorted(k.co.x for fc in curves for k in fc.keyframe_points if k.select_control_point)
        if not times or times[-1]-times[0] <= 1e-5:
            self.report({'WARNING'}, tr('Select keys at two or more different frame times'))
            return {'CANCELLED'}
        first, last = times[0], times[-1]
        if last-first <= 1e-5:
            self.report({'WARNING'}, tr('End must be after Start'))
            return {'CANCELLED'}
        work = []
        for fc in curves:
            starts = [k for k in fc.keyframe_points if abs(k.co.x-first) < 1e-4]
            ends = [k for k in fc.keyframe_points if abs(k.co.x-last) < 1e-4]
            if len(starts) > 1 or len(ends) > 1:
                self.report({'WARNING'}, tr('Overlapping boundary keys found; resolve them before generating'))
                return {'CANCELLED'}
            if not starts or not ends:
                self.report({'WARNING'}, tr('A selected curve is missing a key at one of the selected boundary times'))
                return {'CANCELLED'}
            work.append((fc, starts[0], ends[0]))
        if not work:
            self.report({'WARNING'}, tr('No matching Start/End key pairs found in the selected controllers'))
            return {'CANCELLED'}
        # Validate every curve before editing any of them.
        _loop_starts.clear()
        for fc, start, end in work:
            freeze_key_handles(start)
            update_curve_preserve_keys(fc)
            _loop_starts[fc.as_pointer()] = (fc, float(start.co.x))
            finish_loop(fc, start, end, context.window_manager.mgt_loop_smooth_inside)
            owner = curve_owner(str(fc.as_pointer()))
            if owner:
                owner.update_tag(refresh={'TIME'})
        context.area.tag_redraw()
        self.report({'INFO'}, tr('Loop generated from selection: %g to %g, %d curves') % (first, last, len(work)))
        return {'FINISHED'}


class MGT_OT_loop_boundary(bpy.types.Operator):
    bl_idname = 'mgt.loop_boundary'
    bl_label = 'Set Loop Boundary'
    bl_description = 'Start preserves the right tangent; End flattens peak/trough seams or matches the start slope. Key values are unchanged'
    bl_options = {'REGISTER', 'UNDO'}
    boundary: EnumProperty(items=[('START', 'Loop Start', ''), ('END', 'Loop End', '')])

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'GRAPH_EDITOR'

    def execute(self, context):
        if self.boundary == 'START':
            rows = entries(context)
            curves = list(dict.fromkeys(row[3] for row in rows)) if rows else list(context.visible_fcurves or [])
            times = [k.co.x for fc in curves if not fc.lock for k in fc.keyframe_points if k.select_control_point]
            if times and max(times)-min(times) > 1e-5:
                return MGT_OT_generate_loop.execute(self, context)
        selected = []
        for fc in context.visible_fcurves or []:
            if fc.lock:
                continue
            keys = [k for k in fc.keyframe_points if k.select_control_point]
            if len(keys) > 1:
                self.report({'WARNING'}, tr('Select only one boundary key per curve'))
                return {'CANCELLED'}
            if keys:
                selected.append((fc, keys[0]))
        if not selected:
            self.report({'WARNING'}, tr('Select boundary keys first'))
            return {'CANCELLED'}
        frame = selected[0][1].co.x
        if any(abs(k.co.x - frame) > 1e-4 for _, k in selected):
            self.report({'WARNING'}, tr('Boundary keys must be on the same frame'))
            return {'CANCELLED'}
        if self.boundary == 'START':
            # Replace the previous set to avoid mixing unrelated loop ranges.
            _loop_starts.clear()
            for fc, key in selected:
                freeze_key_handles(key)
                update_curve_preserve_keys(fc)
                _loop_starts[fc.as_pointer()] = (fc, float(key.co.x))
        else:
            work = []
            for fc, end in selected:
                record = _loop_starts.get(fc.as_pointer())
                if record is None or record[0] != fc:
                    self.report({'WARNING'}, tr('Mark Loop Start for every selected curve first'))
                    return {'CANCELLED'}
                starts = [k for k in fc.keyframe_points if abs(k.co.x - record[1]) < 1e-5]
                if len(starts) != 1 or starts[0].co.x >= end.co.x:
                    self.report({'WARNING'}, tr('Start is missing, ambiguous, or not before End; mark Start again'))
                    return {'CANCELLED'}
                work.append((fc, starts[0], end))
            for fc, start, end in work:
                finish_loop(fc, start, end, context.window_manager.mgt_loop_smooth_inside)
        for fc, _ in selected:
            owner = curve_owner(str(fc.as_pointer()))
            if owner:
                owner.update_tag(refresh={'TIME'})
        context.area.tag_redraw()
        self.report({'INFO'}, (tr('Loop Start saved: ') if self.boundary == tr('START') else tr('Loop End matched: ')) + str(len(selected)) + tr(' curves'))
        return {'FINISHED'}


class MGT_OT_key_transform(bpy.types.Operator):
    bl_idname = 'mgt.key_transform'
    bl_label = 'Transform Selected Keyframes'
    bl_description = 'Move or scale selected keyframes; horizontal is time, vertical is value'
    kind: EnumProperty(items=[('MOVE_VALUE', 'Move Values', ''), ('MOVE_TIME', 'Move Time', ''),
                              ('SCALE_VALUE', 'Scale Values', ''), ('SCALE_TIME', 'Scale Time', '')])

    def invoke(self, context, event):
        region = next(r for r in context.area.regions if r.type == 'WINDOW')
        horizontal = self.kind.endswith('TIME')
        with context.temp_override(region=region):
            args = {'constraint_axis': (horizontal, not horizontal, False)}
            if self.kind.startswith('MOVE'):
                bpy.ops.transform.translate('INVOKE_DEFAULT', **args)
            else:
                bpy.ops.transform.resize('INVOKE_DEFAULT', **args)
        return {'FINISHED'}


class MGT_OT_automatic_all(bpy.types.Operator):
    bl_idname = 'mgt.automatic_all'
    bl_label = 'Automatic: ALL Channels'
    bl_description = 'Set EVERY key on selected controllers to Automatic, regardless of display filter or key selection'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        for _, _, _, fc in entries(context):
            for kp in fc.keyframe_points:
                kp.handle_left_type = 'AUTO'
                kp.handle_right_type = 'AUTO'
                count += 1
            update_curve_preserve_keys(fc)
        self.report({'INFO'}, tr('Automatic applied to %d keys across ALL listed channels') % count)
        context.area.tag_redraw()
        return {'FINISHED'}


class MGT_ChannelItem(bpy.types.PropertyGroup):
    controller: StringProperty()
    label: StringProperty()
    token: StringProperty()
    is_header: BoolProperty()


class MGT_ChannelList(bpy.types.PropertyGroup):
    items: CollectionProperty(type=MGT_ChannelItem)
    active_index: IntProperty(default=0)


def channel_list_rows(context):
    search = context.window_manager.mgt_search.casefold()
    groups = {}
    for controller, label, token, fc in entries(context):
        if search and search not in (controller + ' ' + label + ' ' + tr(label)).casefold():
            continue
        groups.setdefault(controller, []).append((label, token))
    result = []
    for controller, channels in groups.items():
        result.append((controller, controller, '', True))
        if controller in _collapsed and not search:
            continue
        result.extend((controller, label, token, False) for label, token in channels)
    return result


def refresh_channel_list(context):
    lists = context.window_manager.mgt_channel_lists
    key = area_key(context)
    record = lists.get(key)
    if record is None:
        record = lists.add()
        record.name = key
    rows = channel_list_rows(context)
    current = [(item.controller, item.label, item.token, item.is_header) for item in record.items]
    if rows == current:
        return
    record.items.clear()
    for controller, label, token, is_header in rows:
        item = record.items.add()
        item.controller, item.label, item.token, item.is_header = controller, label, token, is_header
    record.active_index = min(record.active_index, max(0, len(rows)-1))
    context.area.tag_redraw()


class MGT_UL_channels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout = ui(layout, help=False)
        if item.is_header:
            collapsed = item.controller in _collapsed and not context.window_manager.mgt_search
            op = layout.operator('mgt.fold', text=item.controller, emboss=False,
                                 icon='TRIA_RIGHT' if collapsed else 'TRIA_DOWN')
            op.controller = item.controller
        else:
            layout.operator_context = 'INVOKE_DEFAULT'
            active = item.token in _chosen.get(area_key(context), set()) and area_key(context) in _visibility
            op = layout.operator('mgt.channel', text=item.label, depress=active,
                                 icon='RADIOBUT_ON' if active else 'RADIOBUT_OFF')
            op.token = item.token


class MGT_PT_channels(bpy.types.Panel):
    bl_label = 'Maya Channels'
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Maya'

    def draw(self, context):
        draw_language(self.layout, context)
        layout = ui(self.layout)
        wm = context.window_manager
        if area_key(context) not in _layouts:
            layout.operator('mgt.toggle', text='Enable Left Channel List', icon='GRAPH')
        layout.label(text='Version 1.26 · Press R for Region Box')
        layout.operator('mgt.region_hotkey',text='R: Show Editing Box')
        layout.operator('mgt.box_keys',text='B: Box Select Keys')
        row = layout.row(align=True)
        row.operator('mgt.show_all', text='Show All')
        row.operator('mgt.restore', text='Restore')
        row = layout.row(align=True)
        row.operator('mgt.frame', text='Frame')
        row.operator('mgt.box_zoom', text='Box Zoom')
        layout.prop(wm, 'mgt_auto_frame', text='Auto Frame')
        layout.prop(wm, 'mgt_frame_mode', text='Frame Range')
        layout.prop(wm, 'mgt_all_bones', text='Show All Rig Bones')
        layout.prop(wm, 'mgt_search', text='', icon='VIEWZOOM')
        rows = entries(context)
        if not rows:
            layout.label(text='Select an animated object or rig.', icon='INFO')
        if context.active_pose_bone and not wm.mgt_all_bones:
            layout.label(text='Selected: ' + context.active_pose_bone.name, icon='BONE_DATA')
        record = wm.mgt_channel_lists.get(area_key(context))
        if record:
            layout.template_list('MGT_UL_channels', area_key(context), record, 'items',
                                 record, 'active_index', rows=8, maxrows=8)
        else:
            layout.label(text='Channel list loading...', icon='INFO')
        layout.label(text='Shift/Ctrl-click: multiple curves')
        layout.separator()
        layout.label(text='Box: keys only · Click: edit handles')
        layout.prop(wm,'mgt_drag_keys',text='Drag Keys Vertically · Shift: Free')
        layout.prop(wm,'mgt_thin_lines',text='Thin Curves')
        layout.label(text='Handles: selected keys only')
        layout.prop(wm, 'mgt_loop_smooth_inside', text='Smooth Inside Loop (Auto Clamped)')
        layout.operator('mgt.generate_loop', text='Generate Loop: Selected Keys')
        layout.prop(wm, 'mgt_maya_markers', text='Diamond Keys / Triangle Handles')
        if wm.mgt_maya_markers:
            layout.prop(wm, 'mgt_key_size', text='Key Size')
            layout.prop(wm, 'mgt_handle_size', text='Handle Size')
        layout.operator('mgt.box_keys', text='B: Box Select Keys')
        layout.operator('mgt.region_edit', text='Edit Selected Region')
        layout.label(text='Inside: move · Shift: vertical only')
        layout.label(text='Drag edges/corners to scale')
        box=layout.box()
        help_label(box, 'Scale Around Selection Center (100%: unchanged)', 'BOUNDS')
        box.prop(wm,'mgt_lower_percent',text='Lower Boundary %')
        box.prop(wm,'mgt_upper_percent',text='Upper Boundary %')
        box.prop(wm,'mgt_time_percent',text='Time Width %')
        box.operator('mgt.boundary_scale',text='Apply Percentages')
        row = layout.row(align=True)
        row.operator('mgt.key_transform', text='Move Values').kind = 'MOVE_VALUE'
        row.operator('mgt.key_transform', text='Move Time').kind = 'MOVE_TIME'
        row = layout.row(align=True)
        row.operator('mgt.key_transform', text='Scale Values').kind = 'SCALE_VALUE'
        row.operator('mgt.key_transform', text='Scale Time').kind = 'SCALE_TIME'
        layout.operator('mgt.automatic_all', text='Automatic: ALL Channels')
        layout.label(text='G: move · S: scale · X/Y: axis')


def header(self, context):
    if context.space_data.mode == 'FCURVES':
        ui(self.layout).operator('mgt.toggle', text='Maya 1.26', icon='GRAPH',
                             depress=area_key(context) in _layouts)


_classes = (MGT_ChannelItem, MGT_ChannelList, MGT_UL_channels, MGT_OT_marker_click, MGT_OT_toggle, MGT_OT_channel, MGT_OT_all, MGT_OT_restore,
            MGT_OT_frame, MGT_OT_zoom, MGT_OT_fold, MGT_OT_box_keys,
            MGT_OT_region_edit,MGT_OT_region_hotkey,MGT_OT_boundary_scale,
            MGT_OT_generate_loop, MGT_OT_loop_boundary, MGT_OT_key_transform, MGT_OT_automatic_all, MGT_PT_channels)


_frame_mode_items = {
    'EN': [('CURRENT', 'Current Time Range', 'Keep the current horizontal range; fit curve values', 0),
           ('PLAYBACK', 'Playback Range', 'Use scene preview range, or playback start/end', 1),
           ('ALL', 'All Frames', 'Fit the complete visible animation', 2)],
    'JA': [('CURRENT', '現在の表示時間範囲', '現在の時間範囲でカーブの値を表示', 0),
           ('PLAYBACK', '再生範囲', 'プレビュー範囲または再生の開始終了フレーム', 1),
           ('ALL', '全フレーム', 'アニメーション全体を表示', 2)],
    'ZH': [('CURRENT', '当前视图时间范围', '保留当前横向范围，聚焦曲线数值', 0),
           ('PLAYBACK', '播放区间', '使用预览区间或播放起止帧', 1),
           ('ALL', '全部帧', '显示完整动画范围', 2)],
}

def frame_mode_items(self, context):
    return _frame_mode_items.get(language(), _frame_mode_items['EN'])


def register():
    register_language(_classes)
    global _marker_handler
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.mgt_channel_lists = CollectionProperty(type=MGT_ChannelList)
    bpy.types.WindowManager.mgt_loop_smooth_inside = BoolProperty(default=True)
    bpy.types.WindowManager.mgt_auto_frame = BoolProperty(default=True)
    bpy.types.WindowManager.mgt_all_bones = BoolProperty(default=False,
        description='List the entire rig instead of only selected pose controllers')
    bpy.types.WindowManager.mgt_maya_markers = BoolProperty(name='Maya Key Shapes', default=True)
    bpy.types.WindowManager.mgt_drag_keys = BoolProperty(name='Drag Keys Directly',default=True)
    bpy.types.WindowManager.mgt_key_size = FloatProperty(name='Key Size', default=5, min=2.5, max=12)
    bpy.types.WindowManager.mgt_handle_size = FloatProperty(name='Handle Size', default=3.2, min=1, max=6)
    bpy.types.WindowManager.mgt_thin_lines = BoolProperty(name='Thin Curves',default=False)
    _thin_handlers.append(bpy.types.SpaceGraphEditor.draw_handler_add(begin_curve_render, (), 'WINDOW', 'PRE_VIEW'))
    _thin_handlers.append(bpy.types.SpaceGraphEditor.draw_handler_add(restore_curve_render, (), 'WINDOW', 'POST_VIEW'))
    _marker_handler = bpy.types.SpaceGraphEditor.draw_handler_add(draw_maya_markers, (), 'WINDOW', 'POST_PIXEL')
    bpy.types.WindowManager.mgt_frame_mode = EnumProperty(
        name='Frame Range', default=0,
        items=frame_mode_items)
    bpy.types.WindowManager.mgt_search = StringProperty(default='')
    bpy.types.WindowManager.mgt_lower_percent=FloatProperty(default=100,min=0,max=10000,
        description='Lower boundary distance from selection center; 100 keeps its current position')
    bpy.types.WindowManager.mgt_upper_percent=FloatProperty(default=100,min=0,max=10000,
        description='Upper boundary distance from selection center; 100 keeps its current position')
    bpy.types.WindowManager.mgt_time_percent=FloatProperty(default=100,min=.01,max=10000,
        description='Time width around selection center; 100 keeps the current spacing')
    bpy.types.GRAPH_HT_header.append(header)
    bpy.app.timers.register(watch_selection, first_interval=.15, persistent=True)
    bpy.app.handlers.load_pre.append(reset_file_caches)
    bpy.app.handlers.undo_pre.append(reset_data_caches)
    bpy.app.handlers.redo_pre.append(reset_data_caches)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Graph Editor', space_type='GRAPH_EDITOR')
        kmi = km.keymap_items.new('mgt.marker_click','LEFTMOUSE','PRESS',shift=False,head=True)
        _keymaps.append((km,kmi))
        kmi = km.keymap_items.new('mgt.marker_click','LEFTMOUSE','PRESS',shift=True,head=True)
        _keymaps.append((km,kmi))
        for shift in (False,True):
            kmi=km.keymap_items.new('mgt.marker_click','LEFTMOUSE','CLICK_DRAG',shift=shift,head=True)
            _keymaps.append((km,kmi))
        kmi = km.keymap_items.new('mgt.box_zoom', 'B', 'PRESS', ctrl=True)
        _keymaps.append((km, kmi))
        kmi = km.keymap_items.new('mgt.region_hotkey', 'R', 'PRESS',head=True)
        _keymaps.append((km, kmi))
        kmi = km.keymap_items.new('mgt.box_keys','B','PRESS')
        _keymaps.append((km,kmi))


def unregister():
    unregister_language()
    global _marker_handler
    for handlers, callback in ((bpy.app.handlers.load_pre, reset_file_caches),
                               (bpy.app.handlers.undo_pre, reset_data_caches),
                               (bpy.app.handlers.redo_pre, reset_data_caches)):
        if callback in handlers:
            handlers.remove(callback)
    restore_curve_render()
    for handler in _thin_handlers:
        bpy.types.SpaceGraphEditor.draw_handler_remove(handler,'WINDOW')
    _thin_handlers.clear()
    if _marker_handler is not None:
        bpy.types.SpaceGraphEditor.draw_handler_remove(_marker_handler, 'WINDOW')
        _marker_handler = None
    _normalization_cache.clear()
    if bpy.app.timers.is_registered(watch_selection):
        bpy.app.timers.unregister(watch_selection)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'GRAPH_EDITOR' and str(area.as_pointer()) in _layouts:
                with bpy.context.temp_override(screen=screen, area=area):
                    bpy.ops.mgt.toggle()
    bpy.types.GRAPH_HT_header.remove(header)
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    del bpy.types.WindowManager.mgt_auto_frame
    del bpy.types.WindowManager.mgt_channel_lists
    del bpy.types.WindowManager.mgt_loop_smooth_inside
    del bpy.types.WindowManager.mgt_all_bones
    del bpy.types.WindowManager.mgt_maya_markers
    del bpy.types.WindowManager.mgt_drag_keys
    del bpy.types.WindowManager.mgt_key_size
    del bpy.types.WindowManager.mgt_handle_size
    del bpy.types.WindowManager.mgt_thin_lines
    del bpy.types.WindowManager.mgt_frame_mode
    del bpy.types.WindowManager.mgt_search
    del bpy.types.WindowManager.mgt_lower_percent
    del bpy.types.WindowManager.mgt_upper_percent
    del bpy.types.WindowManager.mgt_time_percent
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    _visibility.clear()
    _layouts.clear()
    _dragging_areas.clear()
    _loop_starts.clear()
    _collapsed.clear()
    _controller_groups.clear()
    _chosen.clear()
    _scope.clear()
    _curve_objects.clear()
    _object_selection.clear()
    _selection_signatures.clear()
    _box_bounds.clear()











