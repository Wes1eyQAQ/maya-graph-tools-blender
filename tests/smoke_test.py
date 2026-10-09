import os, tempfile
os.environ['BLENDER_USER_CONFIG'] = tempfile.mkdtemp(prefix='maya-graph-tools-test-')
import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import MayaGraphTools as m
m.register()
obj=bpy.context.object
for t,v in ((0,20),(120,0),(123,1),(130,2),(134,0),(200,-30)):
    obj.location.x=v;obj.keyframe_insert('location',index=0,frame=t)
fc=m.action_curves(obj)[0]
for k in fc.keyframe_points:
    k.handle_left_type=k.handle_right_type='FREE'
    k.select_control_point=k.co.x in (120,134)
fc.keyframe_points[2].handle_right=(125,90)
fc.keyframe_points[3].handle_left=(128,-90)
m.update_curve_preserve_keys(fc)
assert max(abs(fc.evaluate(123+i*.1)) for i in range(71))>10
area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D');area.type='GRAPH_EDITOR'
region=next(r for r in area.regions if r.type=='WINDOW')
with bpy.context.temp_override(area=area,region=region):
    before=[(tuple(k.co),k.select_control_point,k.select_left_handle,k.select_right_handle) for k in fc.keyframe_points]
    outside=[(tuple(k.handle_left),tuple(k.handle_right),k.handle_left_type,k.handle_right_type) for k in (fc.keyframe_points[0],fc.keyframe_points[5])]
    assert bpy.context.window_manager.mgt_loop_smooth_inside
    assert bpy.ops.mgt.generate_loop()=={'FINISHED'}
    assert before==[(tuple(k.co),k.select_control_point,k.select_left_handle,k.select_right_handle) for k in fc.keyframe_points]
    for k in fc.keyframe_points[2:4]:assert k.handle_left_type==k.handle_right_type=='AUTO_CLAMPED'
    a,b=fc.keyframe_points[1],fc.keyframe_points[4]
    assert a.handle_left_type==a.handle_right_type==b.handle_left_type==b.handle_right_type=='FREE'
    assert a.handle_left.y==a.handle_right.y==b.handle_left.y==b.handle_right.y==0
    for i in range(71):assert 1-1e-5<=fc.evaluate(123+i*.1)<=2+1e-5
    assert outside==[(tuple(k.handle_left),tuple(k.handle_right),k.handle_left_type,k.handle_right_type) for k in (fc.keyframe_points[0],fc.keyframe_points[5])]
    # Optional off retains deliberately manual interior handles.
    for k in fc.keyframe_points[2:4]:k.handle_left_type=k.handle_right_type='FREE'
    fc.keyframe_points[2].handle_right=(125,7)
    snapshot=[(tuple(k.handle_left),tuple(k.handle_right)) for k in fc.keyframe_points[2:4]]
    bpy.context.window_manager.mgt_loop_smooth_inside=False
    assert bpy.ops.mgt.generate_loop()=={'FINISHED'}
    assert snapshot==[(tuple(k.handle_left),tuple(k.handle_right)) for k in fc.keyframe_points[2:4]]
m.unregister()
print('LOOP_SMOOTH_PASS: extreme internal handle overshoot removed, only interior keys AutoClamped, endpoints Free and horizontal, selection/values/outside keys preserved, optional off retains manual tangents')

