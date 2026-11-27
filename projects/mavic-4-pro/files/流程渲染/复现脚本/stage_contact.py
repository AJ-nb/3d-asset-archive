"""Find the studio floor through the front rubber pads and the lower rear airframe."""
import bpy
import numpy as np


def contact_plane(root):
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get()
    parts={}
    for obj in root.children_recursive:
        if obj.type not in {"MESH","CURVE","FONT","SURFACE"} or obj.hide_render:
            continue
        evaluated=obj.evaluated_get(deps)
        data=evaluated.to_mesh()
        try:
            if not data or not data.vertices:
                continue
            xyz=np.empty(3*len(data.vertices),dtype=np.float32)
            data.vertices.foreach_get("co",xyz)
            matrix=np.asarray(evaluated.matrix_world)
            world=(xyz.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3])*1000
            parts[obj.name]=world[:,1:]
        finally:
            evaluated.to_mesh_clear()
    front_names=[n for n in parts if "swept front landing foot" in n]
    rear_names=[n for n in parts if "ventral runner and rear heel" in n]
    if len(front_names)!=2 or len(rear_names)!=2:
        raise ValueError("Expected two front pads and two rear supports")
    feet=np.vstack([parts[n] for n in front_names])
    rear=np.vstack([parts[n][parts[n][:,0]>0] for n in rear_names])
    def intercept(pts,slope):
        return np.min(pts[:,1]-slope*pts[:,0])
    lo,hi=-.5,.5
    for _ in range(45):
        slope=(lo+hi)/2
        if intercept(feet,slope)>intercept(rear,slope):
            hi=slope
        else:
            lo=slope
    slope=(lo+hi)/2
    lows={n:float(intercept(p,slope)) for n,p in parts.items()}
    floor=min(lows.values())
    gaps={n:round(z-floor,4) for n,z in lows.items() if z-floor<.5}
    supports={n:float(lows[n]-floor) for n in front_names+rear_names}
    other=sorted(((z-floor,n) for n,z in lows.items() if n not in supports))
    return {"slope_dz_dy":float(slope),"z_at_origin_mm":float(floor),"parts_within_0p5_mm":gaps,
            "support_gaps_mm":supports,"all_four_supports_on_floor":all(gap<.03 for gap in supports.values()),
            "nearest_other_parts_vertical_gap_mm":{n:round(g,4) for g,n in other[:5]},
            "front_pad_clearance_mm":float(intercept(feet,slope)-floor)}

