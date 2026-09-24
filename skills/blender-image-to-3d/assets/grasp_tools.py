"""
GRASP TOOLS
Hands that hold things, for the rig (Phase 6) and the extreme-pose test. Copy next to the build
scripts and import it (it only needs bpy and mathutils):

  import grasp_tools as G
  # 06_rig: seat the weapon's handle in the open hand, then build the socket frame from it
  origin, axis, towards_palm = G.grip_seat(body, "part:Hand_R", G.hand_frame_from_bone(arm, "DEF-hand.R"),
                                           wrist, index_mcp, middle_mcp, half=(0.012, 0.0135))
  # pose test, per frame, after the arm pose and the weapon aim (the grip axis is the socket's
  # handle direction in this pose):
  G.grasp(arm, "R", weapon_ob, body, "part:Hand_R", socket.matrix_world.col[1].xyz)

What each piece does and why:
- grip_seat: where the handle lies when the open hand holds it: an axis diagonal across the palm
  (index end distal: a power grip), crossing the index finger's line about 8 mm below its knuckle
  (at the base of the fingers: a sword is held in the fingers, not deep in the palm), lowered onto
  the glove (palm and straight fingers) until it rests there. 20 mm down, even a knuckle bent to
  its limit left the proximal phalanges 10 to 24 mm off the grip; a socket placed by eye (a point
  "in front of the fist") puts the handle under the finger bases, and every finger hooks.
- grasp: each finger wraps the handle with every phalanx on it (wrap_finger: the MCP and PIP
  searched together, the DIP following the PIP, least sum of the three segments' gaps with none
  inside the weapon); the thumb then closes over the curled index finger. Closing all joints in
  one fixed proportion until the first contact stops at the fingertip and leaves the base segments
  standing off the handle in a loop ("fingers smashed against the handle"). segment_gaps reports
  the result: a natural grip has the palm and every segment within about 6 mm. Forward kinematics
  from the pose bones' rest matrices, so no depsgraph update per candidate.
- Surface.depth tests thin shells too: a glove point is inside when the line from its bone's axis
  out to it crosses the surface. A finger pushed through a 2 mm shell (a basket hilt, a
  shield boss) ends up on its outer side, where the nearest-surface sign alone reads it as clear.
- turn_hand / search / posed_body_tree / body_clearance: aim a held weapon by turning the hand
  about the forearm (pronation, supination), deviating and flexing the wrist, and rotating the
  humerus, scoring each candidate against the posed body's surface. A blade that is not aimed
  cuts through the legs, the scabbard or the cloak in half the poses.
- settle_chain: a stowed shield or pack holds the cloth under it: turn each cape segment forward
  until its vertices clear the item, passing the given-up swing to the segment below.

Bone naming follows references/rigging-animation.md: DEF-<finger>_01..03.<side> for index,
middle, ring, pinky and thumb, parented to DEF-hand.<side>, each bone's local X its flexion axis.
Finger bones rolled with +Z to the back of the hand make flexion a negative X rotation; the code
tests the sign instead of assuming it.
"""
import math
import bpy
from mathutils import Matrix, Vector, Quaternion
from mathutils.bvhtree import BVHTree

FINGERS = ("index", "middle", "ring", "pinky")
GRIP_GAP = 0.0008                    # the glove stops this far off the weapon
FINGER_LIMIT = (90.0, 105.0, 80.0)   # MCP, PIP, DIP flexion (degrees)
DIP_PER_PIP = 0.75                   # the DIP follows the PIP (the tendons couple them)
FIST = (75.0, 90.0)                  # a finger that meets nothing closes towards this loose fist
WRAP_DIP = 0.6                       # DIP : PIP of a finger wrapped round a handle
WRAP_REWARD = 1e-4                   # m of summed gap worth one degree more wrap (a tie-breaker)
SNUG = 0.03                          # a segment farther than this off the handle counts as this far
FINGER_R = 0.0085                    # a finger as a capsule, for the thumb's clearance
RELAX = {"index": (8, 14, 8), "middle": (12, 20, 10), "ring": (16, 26, 12), "pinky": (20, 30, 14),
         "thumb": (6, 10, 8)}        # a free hand at rest, more curled towards the little finger


def bone_name(fmt, finger, k, side):
    return fmt.format(f=finger, k=k, s=side)


# GRIP SEAT (rig time)

def hand_frame_from_bone(arm, hand_bone, palm_sign=-1.0):
    """(across towards the little finger, palm normal, along to the fingertips) from the rest hand
    bone: along its Y, palm its Z times palm_sign (-1 when +Z points out of the back of the hand).
    `across` is only used as a direction; the seat measures on the mesh."""
    B = arm.matrix_world @ arm.data.bones[hand_bone].matrix_local
    along = B.col[1].xyz.normalized()
    palm = (B.col[2].xyz * palm_sign).normalized()
    across = along.cross(palm)                       # flip the sign per side if it points at the thumb
    return across, palm, along


def grip_seat(body, group, frame, wrist, index_mcp, middle_mcp, half, box=False, diag=6.0, below=0.008,
              shift=0.008, gap=0.001, half_len=0.055, tilt=6):
    """Rest-pose handle axis in the open hand. frame = (across towards the little finger, palm
    normal, along) as unit Vectors; wrist, index_mcp, middle_mcp world points; half = the handle's
    half extents (towards the palm, towards the fingertips); box for a rectangular handle, else an
    oval. diag: degrees across the palm (index end distal; 5 to 15 read as natural); below: how far
    under the index knuckle the axis crosses the index finger's line (sweep it with segment_gaps:
    the grip that leaves every phalanx on the handle wins); shift: the handle's centre moved from the middle
    finger towards the index end (the curled fingers lean that way). Returns (origin, unit axis
    towards the index end, unit palm direction orthogonal to it)."""
    c, p, a = frame
    gi = body.vertex_groups[group].index
    pts = [body.matrix_world @ v.co for v in body.data.vertices if any(g.group == gi for g in v.groups)]
    ci = (index_mcp - wrist).dot(c)
    ai = (index_mcp - wrist).dot(a) - below
    cm = (middle_mcp - wrist).dot(c)
    dl = math.radians(diag)
    d = (-c * math.cos(dl) + a * math.sin(dl)).normalized()
    base = wrist + c * ci + a * ai + d * ((ci - cm) / math.cos(dl) + shift)
    hx, hz = half[0] + gap, half[1] + gap

    def inside(O, ax, P):
        N = ax.cross(P)
        for q in pts:
            w = q - O
            if abs(w.dot(ax)) > half_len:
                continue
            x, z = w.dot(P), w.dot(N)
            if (abs(x) < hx and abs(z) < hz) if box else ((x / hx) ** 2 + (z / hz) ** 2 < 1.0):
                return True
        return False
    best = None
    for t in range(-tilt, tilt + 1):
        ax = (d + p * math.tan(math.radians(t))).normalized()
        P = (p - ax * p.dot(ax)).normalized()
        lo, hi = -0.02, 0.06
        for _ in range(30):
            mid = (lo + hi) / 2
            if inside(base + p * mid, ax, P):
                lo = mid
            else:
                hi = mid
        if best is None or hi < best[0] - 1e-5:
            best = (hi, ax, P)
    h, ax, P = best
    return base + p * h, ax, P


# GRASP (pose time)

def digit_samples(arm, body, group, per_bone=70):
    """Rest glove vertices (armature space) per bone: the vertices each deform bone carries most."""
    names = {vg.index: vg.name for vg in body.vertex_groups}
    gi = body.vertex_groups[group].index
    to_arm = arm.matrix_world.inverted() @ body.matrix_world
    out = {}
    for v in body.data.vertices:
        if not any(g.group == gi for g in v.groups):
            continue
        top = max(((g.weight, names[g.group]) for g in v.groups if names[g.group] in arm.data.bones), default=None)
        if top:
            out.setdefault(top[1], []).append(to_arm @ v.co)
    return {k: pts[::max(1, len(pts) // per_bone)] for k, pts in out.items()}


def chain_mats(arm, names, rots):
    """Pose-space matrices of a chain with each joint given a 4x4 rotation in its own frame."""
    bones = arm.data.bones
    par = arm.pose.bones[bones[names[0]].parent.name]
    M, B = par.matrix.copy(), par.bone.matrix_local
    out = []
    for n, R in zip(names, rots):
        Bn = bones[n].matrix_local
        M = M @ (B.inverted() @ Bn) @ R
        B = Bn
        out.append(M)
    return out


def rx(deg):
    return Matrix.Rotation(math.radians(deg), 4, "X")


class Surface:
    """Signed distance to a mesh object's evaluated surface (negative inside)."""

    def __init__(self, ob, reach=0.03):
        dg = bpy.context.evaluated_depsgraph_get()
        eo = ob.evaluated_get(dg)
        me = eo.to_mesh()
        self.tree = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(q.vertices) for q in me.polygons])
        eo.to_mesh_clear()
        self.inv = ob.matrix_world.inverted()
        self.reach = reach

    def depth(self, pts, axis=None):
        """Smallest signed distance of pts to the surface. With axis (a posed bone's head and tail,
        world space) a point also counts as inside when the line from the bone's axis out to it
        crosses the surface: past a thin shell, the nearest-surface sign reads it as clear."""
        best = 1.0
        if axis is not None:
            a0, a1 = self.inv @ axis[0], self.inv @ axis[1]
            da = a1 - a0
        for q in pts:
            q = self.inv @ q
            loc, n, i, d = self.tree.find_nearest(q, self.reach)
            if loc is not None:
                best = min(best, d if (q - loc).dot(n) >= 0 else -d)
            if axis is not None:
                c = a0 + da * max(0.0, min(1.0, (q - a0).dot(da) / max(da.length_squared, 1e-12)))
                v = q - c
                L = v.length
                if L > 1e-6:
                    hit = self.tree.ray_cast(c, v / L, L)
                    if hit[0] is not None:
                        best = min(best, -(L - hit[3]))
        return best


def seg_dist(q, a, b):
    d = b - a
    t = max(0.0, min(1.0, (q - a).dot(d) / max(d.length_squared, 1e-12)))
    return (q - (a + d * t)).length


def seg_depths(arm, names, mats, samples, surface, capsules=()):
    """Per segment of a posed chain: the smallest signed distance of its glove samples to the weapon
    (thin shells included) and to the capsules (a, b, radius) of fingers already placed."""
    M0 = arm.matrix_world
    out = []
    for n, m in zip(names, mats):
        b = arm.data.bones[n]
        T = M0 @ m @ b.matrix_local.inverted()
        pts = [T @ v for v in samples.get(n, ())]
        d = surface.depth(pts, (T @ b.head_local, T @ b.tail_local))
        for a, b, r in capsules:
            d = min(d, min(seg_dist(q, a, b) for q in pts) - r)
        out.append(d)
    return out


def flex_sign(arm, names, towards):
    """+1 or -1: the X rotation that moves the digit's tip towards a world point."""
    M0 = arm.matrix_world
    best = None
    for sg in (1, -1):
        mats = chain_mats(arm, names, [rx(sg * 10.0)] + [rx(0)] * (len(names) - 1))
        tip = M0 @ mats[-1] @ Vector((0, arm.data.bones[names[-1]].length, 0))
        d = (tip - towards).length
        if best is None or d < best[0]:
            best = (d, sg)
    return best[1]


def best_of(cands, evaluate):
    """Lowest cost among candidates with no penetration (the least penetrating if all penetrate)."""
    best, least = None, None
    for c in cands:
        pen, cost = evaluate(c)
        if pen >= 0.0 and (best is None or cost < best[0]):
            best = (cost, c)
        if least is None or pen > least[0]:
            least = (pen, c)
    return best[1] if best else least[1]


def wrap_finger(arm, names, sg, surface, samples):
    """(MCP, PIP, DIP) of a finger wrapped round the handle: each of its three segments as close to
    the handle as it gets with none inside it (least sum of the segments' gaps), the DIP following
    the PIP, a little more wrap preferred on a tie."""
    L1, L2, L3 = FINGER_LIMIT

    def angles(c):
        return (c[0], c[1], min(L3, c[1] * WRAP_DIP))

    def evaluate(c):
        d = seg_depths(arm, names, chain_mats(arm, names, [rx(sg * a) for a in angles(c)]), samples, surface)
        return min(d) - GRIP_GAP, sum(min(SNUG, max(0.0, x - GRIP_GAP)) for x in d) - WRAP_REWARD * (c[0] + c[1])
    c = best_of([(a, b) for a in range(0, int(L1) + 1, 5) for b in range(0, int(L2) + 1, 5)], evaluate)
    c = best_of([(min(L1, max(0, c[0] + i)), min(L2, max(0, c[1] + j))) for i in range(-4, 5)
                 for j in range(-4, 5)], evaluate)
    return angles(c)


def segment_gaps(arm, weapon, body, group, side, fmt="DEF-{f}_{k:02d}.{s}", fingers=FINGERS, thumb="thumb",
                 hand_fmt="DEF-hand.{s}"):
    """How the posed hand sits on the weapon: {bone: gap in m} for the palm and every phalanx (the
    closest glove sample of each). A natural grip has all of them within about 6 mm; a base
    segment 10 to 25 mm off means the fingers loop round empty space."""
    bpy.context.view_layer.update()
    surface = Surface(weapon)
    samples = digit_samples(arm, body, group)
    M0 = arm.matrix_world
    out = {}
    for n in [hand_fmt.format(s=side)] + [bone_name(fmt, f, k, side) for f in list(fingers) + [thumb] for k in (1, 2, 3)]:
        if n not in samples:
            continue
        pb = arm.pose.bones[n]
        T = M0 @ pb.matrix @ arm.data.bones[n].matrix_local.inverted()
        out[n] = surface.depth([T @ v for v in samples[n]])
    return out


def solve_thumb(arm, names, surface, samples, caps, target):
    s2 = flex_sign(arm, names[1:], target)
    tip_len = arm.data.bones[names[2]].length
    M0 = arm.matrix_world

    def rots(c):
        return [rx(c[0]) @ Matrix.Rotation(math.radians(c[1]), 4, "Z"), rx(s2 * c[2]), rx(s2 * c[2] * 1.2)]

    def evaluate(c):
        mats = chain_mats(arm, names, rots(c))
        d = seg_depths(arm, names, mats, samples, surface, caps)
        tip = M0 @ mats[2] @ Vector((0, tip_len, 0))
        return min(d) - GRIP_GAP, (tip - target).length
    c = best_of([(x, z, t) for x in range(-60, 61, 10) for z in range(-50, 51, 10) for t in range(0, 61, 10)], evaluate)
    c = best_of([(c[0] + i, c[1] + j, max(0, c[2] + k)) for i in (-5, 0, 5) for j in (-5, 0, 5)
                 for k in (-6, -3, 0, 3, 6)], evaluate)
    return rots(c), c


def set_chain(arm, names, rots):
    for n, R in zip(names, rots):
        pb = arm.pose.bones[n]
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = R.to_quaternion()
    bpy.context.view_layer.update()


def grasp(arm, side, weapon, body, group, grip_axis, fmt="DEF-{f}_{k:02d}.{s}", fingers=FINGERS, thumb="thumb"):
    """Close the hand on the weapon: every finger wraps it (wrap_finger), then the thumb closes
    over the curled index finger. grip_axis: the handle's world direction in this pose (the hand
    socket's axis). The weapon rides the hand socket, so the result is the same in every pose:
    solve once per hand and reuse the digit rotations. Returns the flexion per digit."""
    bpy.context.view_layer.update()
    surface = Surface(weapon)
    samples = digit_samples(arm, body, group)
    centre = weapon.matrix_world.translation.copy()             # weapons keep their origin at the grip
    report = {}
    for f in fingers:
        names = [bone_name(fmt, f, k, side) for k in (1, 2, 3)]
        sg = flex_sign(arm, names, centre)
        c = wrap_finger(arm, names, sg, surface, samples)
        set_chain(arm, names, [rx(sg * t) for t in c])
        report[f] = c
    M0 = arm.matrix_world
    caps = [(M0 @ arm.pose.bones[bone_name(fmt, f, k, side)].head, M0 @ arm.pose.bones[bone_name(fmt, f, k, side)].tail,
             FINGER_R) for f in fingers[:2] for k in (1, 2, 3)]
    mid = arm.pose.bones[bone_name(fmt, fingers[0], 2, side)]
    m = M0 @ ((mid.head + mid.tail) / 2)
    ax = grip_axis.normalized()
    out = (m - centre) - ax * (m - centre).dot(ax)
    target = m + out.normalized() * (FINGER_R + 0.009)          # on the index finger's middle phalanx
    names = [bone_name(fmt, thumb, k, side) for k in (1, 2, 3)]
    rots, c = solve_thumb(arm, names, surface, samples, caps, target)
    set_chain(arm, names, rots)
    report[thumb] = c
    return report


def relax(arm, side, fmt="DEF-{f}_{k:02d}.{s}", hand_fmt="DEF-hand.{s}"):
    """A free hand at rest: fingers slightly curled."""
    bpy.context.view_layer.update()
    F = arm.pose.bones[hand_fmt.format(s=side)].matrix
    palm = arm.matrix_world @ (F.translation - F.col[2].xyz * 0.08 + F.col[1].xyz * 0.06)
    for f, angs in RELAX.items():
        names = [bone_name(fmt, f, k, side) for k in (1, 2, 3)]
        sg = flex_sign(arm, names, palm)
        set_chain(arm, names, [rx(sg * x) for x in angs])


# AIMING A HELD WEAPON (pose time)

def rot_about(arm, bone, axis, deg):
    """Rotate a pose bone about a world axis through its head."""
    pb = arm.pose.bones[bone]
    bpy.context.view_layer.update()
    M = pb.matrix.copy()
    R = Matrix.Rotation(math.radians(deg), 4, axis.normalized())
    h = M.translation.copy()
    pb.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M
    bpy.context.view_layer.update()


def turn_hand(arm, side, twist=0.0, dev=0.0, humerus=0.0, flex=0.0, fmt="DEF-{b}.{s}"):
    """Pronation / supination (the hand about the forearm's axis; the vambrace does not twist),
    radial / ulnar deviation (about the palm normal), wrist flexion (about the hand's X) and
    humeral rotation (the whole arm about the upper arm)."""
    ua, fo, hd = (fmt.format(b=b, s=side) for b in ("upper_arm", "forearm", "hand"))
    if humerus:
        rot_about(arm, ua, arm.pose.bones[ua].matrix.col[1].xyz, humerus)
    if twist:
        rot_about(arm, hd, arm.pose.bones[fo].matrix.col[1].xyz, twist)
    if dev:
        rot_about(arm, hd, -arm.pose.bones[hd].matrix.col[2].xyz, dev)
    if flex:
        rot_about(arm, hd, arm.pose.bones[hd].matrix.col[0].xyz, flex)


def search(arm, bones, apply, score, candidates):
    """Try each candidate (apply(*c) poses it from the current pose); keep the best (score(c)[0])."""
    saved = {n: (arm.pose.bones[n].location.copy(), arm.pose.bones[n].rotation_quaternion.copy()) for n in bones}

    def restore():
        for n, (l, q) in saved.items():
            arm.pose.bones[n].location, arm.pose.bones[n].rotation_quaternion = l, q
        bpy.context.view_layer.update()
    best = None
    for c in candidates:
        apply(*c)
        bpy.context.view_layer.update()
        sc = score(c)
        restore()
        if best is None or sc[0] > best[0][0]:
            best = (sc, c)
    apply(*best[1])
    bpy.context.view_layer.update()
    return best


def posed_body_tree(objects, skip_group_prefixes=(), part_prefix="part:"):
    """BVH of the posed meshes (skinning on for the evaluation), leaving out faces whose part group
    starts with any of skip_group_prefixes (the arm being aimed)."""
    verts, polys = [], []
    for ob in objects:
        mods = [m for m in ob.modifiers if m.type == "ARMATURE"]
        was = [m.show_viewport for m in mods]
        for m in mods:
            m.show_viewport = True
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        eo = ob.evaluated_get(dg)
        me = eo.to_mesh()
        names = {g.index: g.name for g in ob.vertex_groups}
        part = {}
        for v in ob.data.vertices:
            for g in v.groups:
                n = names.get(g.group, "")
                if n.startswith(part_prefix):
                    part[v.index] = n[len(part_prefix):]
                    break
        off = len(verts)
        verts += [eo.matrix_world @ v.co for v in me.vertices]
        polys += [[off + i for i in q.vertices] for q in me.polygons
                  if not part.get(q.vertices[0], "").startswith(tuple(skip_group_prefixes))]
        eo.to_mesh_clear()
        for m, w in zip(mods, was):
            m.show_viewport = w
    return BVHTree.FromPolygons(verts, polys)


def body_clearance(points, tree, ground=0.04):
    """Smallest signed distance of the points outside the posed body (negative inside), and above
    the ground by `ground`."""
    worst = 1e9
    for q in points:
        worst = min(worst, q.z - ground)
        loc, n, i, d = tree.find_nearest(q, 0.25)
        if loc is not None:
            worst = min(worst, d if (q - loc).dot(n) >= 0 else -d)
    return worst


# CLOTH UNDER A STOWED ITEM (pose time)

def settle_chain(arm, names, samples, blocked, axis=Vector((1, 0, 0)), step=-1.0, limit=40):
    """Turn each bone of a cloth chain (top first) about `axis` by `step` degrees until blocked(pts)
    is False for the vertices it and the bones below carry; the turn it gives up is handed to the
    next bone, so the cloth folds under the item instead of swinging through it. samples: rest
    vertices (armature space) per bone (digit_samples works for cloth too). Returns turns per bone."""
    moved, carry = {}, 0.0
    M0 = arm.matrix_world

    def pts(from_k):
        out = []
        for n in names[from_k:]:
            pb = arm.pose.bones[n]
            T = M0 @ pb.matrix @ pb.bone.matrix_local.inverted()
            out += [T @ v for v in samples.get(n, ())]
        return out
    for k, n in enumerate(names):
        if carry:
            rot_about(arm, n, axis, -carry)
        turned = 0
        while turned < limit and blocked(pts(k)):
            rot_about(arm, n, axis, step)
            turned += 1
        carry = turned * step
        if turned:
            moved[n] = turned
    return moved
