"""
POSE OVERLAP
Measures interpenetration on the extreme-pose sheet (Phase 6 and 7 gates). For every frame of the
pose action, evaluate the deformed LOD0 meshes and the attached weapons, split them into parts,
and count intersecting triangle pairs for every pair of parts.

Two rules keep the count honest:
- Body and garment pairs are compared with the bind position (the armature switched to REST), not
  with a test frame, so designed nesting (trims set into plates, padding under armour) is the
  baseline and a pose cannot hide its own clipping. A pair is reported when a pose adds more than
  --tol pairs to it.
- Weapons and held or stowed gear (--absolute, default every object whose name starts with WP_)
  have no baseline: any intersection is reported, except an allowance where a hand closes on its
  own grip (--allow "Hand_R x WP_Sword:8"). A clipping weapon at rest is still a clipping weapon.

Parts are objects, or, inside a joined mesh, its vertex groups named with --part-prefix (the
builder's bookkeeping groups; each face goes to the group of its first vertex); objects matching
--whole (default WP_*) stay one part, named without their _LOD suffix. --layer lists
parts whose pairs among themselves are ignored (padding layers designed to interleave).

  blender --background CH_Knight/CH_Knight_posetest.blend --python scripts/pose_overlap.py -- \
      --collections LOW,WP_Sword_LOW --action POSE_extremes --allow "Hand_R x WP_Sword:8" \
      --out CH_Knight/review/06_rig/pose_overlap.json
"""
import bpy, sys, os, re, json, argparse, itertools, fnmatch
from mathutils.bvhtree import BVHTree


def parse(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--blend", default=None, help="open this file (or pass the .blend before --python)")
    p.add_argument("--collections", default="LOW", help="collections holding the meshes and attached weapons")
    p.add_argument("--lod", type=int, default=0, help="LOD level to test (objects named *_LOD<n>, or unsuffixed)")
    p.add_argument("--part-prefix", default="part:")
    p.add_argument("--whole", default="WP_*", help="comma list of object patterns never split into parts")
    p.add_argument("--absolute", default="WP_*", help="comma list of part patterns counted with no baseline")
    p.add_argument("--allow", action="append", default=[], metavar="'A x B:N'",
                   help="intersections allowed on an absolute pair (patterns; a glove on its own grip)")
    p.add_argument("--layer", default="", help="comma list of part patterns whose mutual pairs are ignored")
    p.add_argument("--tol", type=int, default=12, help="new intersecting pairs tolerated on a body pair")
    p.add_argument("--action", default=None, help="assign this action to the armature first")
    p.add_argument("--frames", default=None, help="comma list (default: the scene range)")
    p.add_argument("--out", default=None)
    return p.parse_args(argv)


def lod_of(name):
    m = re.search(r"_LOD(\d+)$", name)
    return int(m.group(1)) if m else 0


def part_name(ob):
    return re.sub(r"_LOD\d+$", "", ob.name)


def gather(a):
    objs = []
    for n in [x for x in a.collections.split(",") if x]:
        c = bpy.data.collections.get(n)
        if c:
            objs += [o for o in c.all_objects if o.type == "MESH" and not o.name.startswith("COL_")
                     and lod_of(o.name) == a.lod and not o.hide_render]
    return list({o.name: o for o in objs}.values())


def part_trees(objs, prefix, whole=()):
    dg = bpy.context.evaluated_depsgraph_get()
    groups = {}
    for ob in objs:
        eo = ob.evaluated_get(dg)
        me = eo.to_mesh()
        mw = eo.matrix_world
        verts = [mw @ v.co for v in me.vertices]
        names = {g.index: g.name for g in ob.vertex_groups}
        vpart = {}
        split = not any(fnmatch.fnmatch(ob.name, w) for w in whole)
        if split and any(n.startswith(prefix) for n in names.values()) and len(me.vertices) == len(ob.data.vertices):
            for v in ob.data.vertices:
                for g in v.groups:
                    n = names.get(g.group, "")
                    if n.startswith(prefix):
                        vpart[v.index] = n[len(prefix):]
                        break
        own = part_name(ob)
        for p in me.polygons:
            groups.setdefault(vpart.get(p.vertices[0], own), []).append([verts[i] for i in p.vertices])
        eo.to_mesh_clear()
    trees = {}
    for k, polys in groups.items():
        vs, ps = [], []
        for poly in polys:
            ps.append(list(range(len(vs), len(vs) + len(poly))))
            vs += poly
        trees[k] = BVHTree.FromPolygons(vs, ps)
    return trees


def matches(name, patterns):
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def overlaps(trees, layer):
    out = {}
    for x, y in itertools.combinations(sorted(trees), 2):
        if layer and matches(x, layer) and matches(y, layer):
            continue
        n = len(trees[x].overlap(trees[y]))
        if n:
            out[x + " x " + y] = n
    return out


def main(a):
    if a.blend:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    sc = bpy.context.scene
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if a.action:
        act = bpy.data.actions[a.action]
        for arm in arms:
            arm.animation_data_create()
            arm.animation_data.action = act
    absolute = [x for x in a.absolute.split(",") if x]
    layer = [x for x in a.layer.split(",") if x]
    allow = []
    for s in a.allow:
        pair, n = s.rsplit(":", 1)
        pa, pb = [x.strip() for x in pair.split(" x ")]
        allow.append((pa, pb, int(n)))

    def is_abs(key):
        return any(matches(p, absolute) for p in key.split(" x "))

    def allowance(key):
        x, y = key.split(" x ")
        return max([n for pa, pb, n in allow if (fnmatch.fnmatch(x, pa) and fnmatch.fnmatch(y, pb)) or
                    (fnmatch.fnmatch(x, pb) and fnmatch.fnmatch(y, pa))], default=0)

    objs = gather(a)
    frames = [int(f) for f in a.frames.split(",")] if a.frames else list(range(sc.frame_start, sc.frame_end + 1))
    sc.frame_set(frames[0])
    for arm in arms:
        arm.data.pose_position = "REST"
    whole = [x for x in a.whole.split(",") if x]
    base = {k: v for k, v in overlaps(part_trees(objs, a.part_prefix, whole), layer).items() if not is_abs(k)}
    for arm in arms:
        arm.data.pose_position = "POSE"
    report, worst = {}, 0
    for f in frames:
        sc.frame_set(f)
        new = {}
        for k, v in overlaps(part_trees(objs, a.part_prefix, whole), layer).items():
            if is_abs(k):
                if v > allowance(k):
                    new[k] = v
            elif v - base.get(k, 0) > a.tol:
                new[k] = v - base.get(k, 0)
        report[f] = dict(sorted(new.items(), key=lambda kv: -kv[1]))
        worst = max([worst] + list(new.values()))
        weapons = {k: v for k, v in new.items() if is_abs(k)}
        print("FRAME %d: %d pairs over tolerance%s" % (f, len(new), (", weapon pairs: " + ", ".join(
            "%s %d" % kv for kv in weapons.items())) if weapons else ""))
        for k, v in list(report[f].items())[:12]:
            print("   %s%4d  %s" % ("" if is_abs(k) else "+", v, k))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        json.dump({"tolerance": a.tol, "baseline": "bind position (armature at REST), body and garment pairs",
                   "absolute": absolute, "allow": a.allow, "layer": layer, "baseline_pairs": len(base),
                   "objects": [o.name for o in objs], "frames": report}, open(a.out, "w"), indent=1)
        print("report", a.out)


if __name__ == "__main__":
    main(parse(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []))
