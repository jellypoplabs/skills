# 白模自检：在 Blender 里检查一条白模动画，再拿去给 AI 渲染。
# 用法：
#   blender -b 你的白模.blend --python check_blend.py -- [选项]
# 选项：
#   --camera NAME        要检查的相机（默认用场景当前相机）
#   --small A,B          小物体（纸飞机、鸟、球……），检查它们会不会侧过来变成一条线、或者跑出画面
#   --ignore A,B         检查穿模时忽略的物体（比如水面、天空球、雾）
#   --min-clear 0.8      镜头离任何表面的最小距离（米），低于它算「贴得太近」
#   --max-turn 3.0       镜头每帧最多转多少度，超过算「转太快」
#   --keyframes 5        自动挑几张关键帧并渲染出来（挑镜头转得慢、构图稳的时刻）
#   --out DIR            报告和关键帧存在哪（默认 blend 文件旁边的 whitebox_check/）
# 输出：DIR/report.md（人看）、DIR/report.json（程序看）、DIR/keyframes/*.png
import bpy, bmesh, json, math, os, sys
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def opt(name, default=None, cast=str):
    if name in argv:
        return cast(argv[argv.index(name) + 1])
    return default

scene = bpy.context.scene
cam = bpy.data.objects[opt("--camera")] if opt("--camera") else scene.camera
assert cam is not None, "场景里没有相机，用 --camera 指定"
small = [s for s in (opt("--small", "") or "").split(",") if s]
ignore = set(s for s in (opt("--ignore", "") or "").split(",") if s)
MIN_CLEAR = opt("--min-clear", 0.8, float)
MAX_TURN = opt("--max-turn", 3.0, float)
N_KEY = opt("--keyframes", 0, int)
blend_dir = os.path.dirname(bpy.data.filepath) or os.getcwd()
OUT = opt("--out", os.path.join(blend_dir, "whitebox_check"))
os.makedirs(OUT, exist_ok=True)

fps = scene.render.fps / scene.render.fps_base
frames = list(range(scene.frame_start, scene.frame_end + 1))
dg = bpy.context.evaluated_depsgraph_get()

# 26 个方向，用来量镜头周围最近的表面
DIRS = [Vector((x, y, z)).normalized() for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)]

def ray(origin, direction, dist=1e4):
    hit, loc, nrm, idx, ob, _ = scene.ray_cast(dg, origin, direction, distance=dist)
    return (hit, loc, nrm, ob)

def inside_object(pos):
    """往上打一条射线，一路数穿过同一个物体的次数；奇数次 = 镜头在这个物体里面（穿模）。"""
    counts, origin, d = {}, pos.copy(), Vector((0, 0, 1))
    for _ in range(64):
        hit, loc, nrm, ob = ray(origin, d)
        if not hit:
            break
        if ob.name not in ignore:
            counts[ob.name] = counts.get(ob.name, 0) + 1
        origin = loc + d * 1e-3
    return [name for name, c in counts.items() if c % 2 == 1]

cam_pos, cam_dir, problems = [], [], []
clear_min = []
for f in frames:
    scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    m = cam.matrix_world
    p = m.translation.copy()
    fwd = (m.to_3x3() @ Vector((0, 0, -1))).normalized()
    cam_pos.append(p)
    cam_dir.append(fwd)
    ins = inside_object(p)
    if ins:
        problems.append({"frame": f, "time": round((f - scene.frame_start) / fps, 2), "type": "穿模", "detail": "镜头在物体里面：" + ", ".join(ins)})
    nearest, near_ob = 1e9, None
    for d in DIRS:
        hit, loc, nrm, ob = ray(p, d, 50)
        if hit and ob.name not in ignore and (loc - p).length < nearest:
            nearest, near_ob = (loc - p).length, ob.name
    clear_min.append((nearest, near_ob))
    if nearest < MIN_CLEAR and not ins:
        problems.append({"frame": f, "time": round((f - scene.frame_start) / fps, 2), "type": "贴太近", "detail": f"离 {near_ob} 只有 {nearest:.2f} 米"})

# 速度和转弯：每秒最快速度、每帧转了多少度
turn = [0.0] + [math.degrees(cam_dir[i].angle(cam_dir[i - 1])) for i in range(1, len(frames))]
speed = [0.0] + [(cam_pos[i] - cam_pos[i - 1]).length * fps for i in range(1, len(frames))]
per_second = []
for s in range(int(math.ceil(len(frames) / fps))):
    idx = range(int(s * fps), min(len(frames), int((s + 1) * fps)))
    if not idx:
        continue
    per_second.append({"second": s, "max_speed_mps": round(max(speed[i] for i in idx), 1), "max_turn_deg_per_frame": round(max(turn[i] for i in idx), 2)})
for i, t in enumerate(turn):
    if t > MAX_TURN:
        problems.append({"frame": frames[i], "time": round(i / fps, 2), "type": "转太快", "detail": f"这一帧转了 {t:.1f} 度，AI 容易在这里停住再跳；这附近别放参考图，或者把转弯拉长"})

# 小物体：屏幕上的可见面积，侧过来只剩一条线时 AI 会把它画没
def screen_area(ob):
    me = ob.evaluated_get(dg).to_mesh()
    bm = bmesh.new(); bm.from_mesh(me); bm.transform(ob.matrix_world)
    area, inframe = 0.0, False
    for face in bm.faces:
        pts = [world_to_camera_view(scene, cam, v.co) for v in face.verts]
        if any(0 <= q.x <= 1 and 0 <= q.y <= 1 and q.z > 0 for q in pts):
            inframe = True
        if all(q.z > 0 for q in pts) and len(pts) >= 3:
            a = 0.0
            for k in range(len(pts)):
                x1, y1 = pts[k].x, pts[k].y
                x2, y2 = pts[(k + 1) % len(pts)].x, pts[(k + 1) % len(pts)].y
                a += x1 * y2 - x2 * y1
            area += abs(a) / 2
    bm.free(); ob.evaluated_get(dg).to_mesh_clear()
    return area, inframe

small_report = {}
for name in small:
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        small_report[name] = "找不到这个网格物体"
        continue
    areas = []
    for f in frames:
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        areas.append(screen_area(ob))
    vis = sorted(a for a, inf in areas if inf and a > 0)
    med = vis[len(vis) // 2] if vis else 0
    thin = [frames[i] for i, (a, inf) in enumerate(areas) if inf and med and a < med * 0.2]
    small_report[name] = {"median_screen_area": round(med, 5), "thin_frames": thin[:50]}
    for f in thin[:1]:
        problems.append({"frame": f, "time": round((f - scene.frame_start) / fps, 2), "type": "小物体变成一条线", "detail": f"{name} 在这附近几乎是侧着对镜头（共 {len(thin)} 帧），AI 可能把它画没；让它有一点 V 形或角度"})

# 关键帧：把时间分成 N 段，每段挑镜头转得最慢的一帧
keys = []
if N_KEY > 0:
    seg = len(frames) / N_KEY
    for k in range(N_KEY):
        lo, hi = int(k * seg), int((k + 1) * seg) - 1
        if k == 0:
            i = 0
        elif k == N_KEY - 1:
            i = len(frames) - 1
        else:
            i = min(range(lo, hi + 1), key=lambda j: turn[j] + (0 if j == 0 else turn[j - 1]))
        keys.append(frames[i])
    os.makedirs(os.path.join(OUT, "keyframes"), exist_ok=True)
    old = (scene.render.filepath, scene.render.image_settings.file_format, scene.render.engine)
    scene.render.image_settings.file_format = "PNG"
    for f in keys:
        scene.frame_set(f)
        scene.render.filepath = os.path.join(OUT, "keyframes", f"kf_{f:04d}_{(f - scene.frame_start) / fps:05.2f}s.png")
        bpy.ops.render.render(write_still=True)
    scene.render.filepath, scene.render.image_settings.file_format, scene.render.engine = old

report = {"blend": bpy.data.filepath, "camera": cam.name, "fps": fps, "frames": len(frames),
          "min_clearance_m": round(min(c for c, _ in clear_min), 2),
          "per_second": per_second, "small_objects": small_report, "keyframes": keys, "problems": problems}
json.dump(report, open(os.path.join(OUT, "report.json"), "w"), ensure_ascii=False, indent=1)

kinds = {}
for p in problems:
    kinds.setdefault(p["type"], []).append(p)
lines = [f"# 白模自检报告", "", f"文件：{os.path.basename(bpy.data.filepath)}　相机：{cam.name}　{len(frames)} 帧 / {fps:g} fps", ""]
if not problems:
    lines += ["没发现问题：没有穿模，没有贴太近，没有转太快" + ("，小物体一直看得见" if small else "") + "。", ""]
for kind, items in kinds.items():
    ts = sorted(set(p["time"] for p in items))
    lines += [f"## {kind}（{len(items)} 帧）", "", f"出现在：{', '.join(str(t) + ' 秒' for t in ts[:12])}{' ……' if len(ts) > 12 else ''}", "", f"例子：{items[0]['detail']}", ""]
lines += ["## 每秒速度和转弯", "", "| 秒 | 最快速度 m/s | 每帧最多转几度 |", "|---|---|---|"]
lines += [f"| {r['second']} | {r['max_speed_mps']} | {r['max_turn_deg_per_frame']} |" for r in per_second]
lines += ["", f"镜头离表面最近 {report['min_clearance_m']} 米。"]
if keys:
    lines += ["", "## 关键帧", "", "已渲染到 keyframes/：" + ", ".join(f"{(f - scene.frame_start) / fps:.2f} 秒" for f in keys),
              "下一步：把这些截图拿去图生图出参考图（构图不动，只换材质），再用 overlay.py 叠回来检查。"]
open(os.path.join(OUT, "report.md"), "w").write("\n".join(lines) + "\n")
print("WHITEBOX_CHECK", "problems:", len(problems), "->", os.path.join(OUT, "report.md"))
