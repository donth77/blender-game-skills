"""
RETARGET TOOLS
Real poses from reference motion for the extreme-pose sheet (and a start for animation): sample
frames of a reference clip (Mixamo or motion-capture FBX, BVH) in their own Blender process, then
retarget each frame onto the delivery skeleton in the pose-test process. Copy next to the build
scripts and import it (it needs bpy, mathutils and numpy):

  # 1. a clean Blender process: sample the frames into JSON (import_scene.fbx or .bvh first)
  import retarget_tools as RT
  rec = RT.sample_frame(RT.load_clip("Sword And Shield Slash.fbx"), 0.6, RT.MIXAMO_BONES,
                        props={"blade": "Sword_joint", "shield": "Shield_joint"})
  # 2. the pose test, per frame (after resetting the pose)
  RT.retarget(arm, rec, bone_map, palms=palm_bones, hinges=hinges, feet=("DEF-foot.L", ...))
  RT.ground(arm, sole_points)                          # the lower sole on z = 0

What each step does and why:
- Test poses built from a few whole-bone rotations about world axes (both arms 105 degrees
  sideways, thighs -95 with nothing else moving) read as "cartoonishly unrealistic". Real frames
  from reference clips give the whole body's balance: weight shift, spine, head and both arms. Keep
  each old test's purpose (shoulders up, reach, deep elbow, crouch, stride) and pick a real frame
  that loads the same joints: an overhead strike's wind-up, a lunge, a block, a crouch, a walk.
- Rest poses differ (their T-pose against an A-pose). Align each bone's rest frame with the
  reference bone's on two anatomical axes, not only its length: forward for the trunk, arms and
  legs (elbows and knees flex the same way in both rigs, so the hinges line up), up for the feet,
  the palm's normal for the hands. Aligning the length alone left the hands rolled 52 degrees, and
  a sword came out 52 degrees off the clip's in every frame. A constant offset across frames is a
  convention mismatch: measure its axis in the bone's own frame to find which axis disagrees.
- Transfer the reference's change from rest onto the aligned rest:
      R_pose = R_ref_pose @ R_ref_rest^-1 @ Q @ R_rest       (Q: our rest frame onto theirs)
  It reproduces the reference's bone directions exactly and carries their twist.
- Hinges: roll the upper limb about its own length so the child's direction lies in the child's
  hinge plane, then bend the child about its hinge only. Do not bend past the rest pose, and move
  the forearm's roll to the wrist (the hand's rotation is set from the clip). Helper bones that
  follow half a joint's rotation (couters, knee cops) otherwise swing sideways and roll their
  plates into the lames.
- Root: move the pelvis by the reference hips' height change, scaled to our hip height, and drop
  the horizontal travel. Then raise or lower the pose until the lower sole touches the ground.
- Held props: a reference can hold its prop differently (a kite shield strapped to the forearm
  against a centre grip in the fist). Take the reference prop's placement and facing as a target
  for our own aim search, not a copy of the hand, and score that search with an exact mesh test
  as well as sampled clearance (grasp_tools.prop_hits).
- Bone-chain cloth (cloaks): hang each chain under gravity, tilted back for the movement's drag,
  until its cloth comes within 1 cm of capsule proxies of the legs, skirt and back and of the gear
  hung on the body (a scabbard, its straps), measured against rest (never deeper than it lay at
  rest). A fixed swing added to a clip whose torso already leans forward flies the cloak out like
  a flag. Once the arms are final, let plates the arm raised (pauldrons) lift the cloth lying over
  them, then hang the segments below again.
- Name each pose after what its frame shows in a render of the clip, not after the clip's title:
  "Attack" at 60 percent was the follow-through of a sweeping cut, not a thrust.
- Expect realistic motion to find deformation limits the synthetic poses hid (hip skirts and
  tassets at 90+ degrees of hip flexion, rigid cuffs at bent wrists, a scabbard rigid on the
  pelvis against the raised thigh): record them, and fix what the weights can (belts sharing the
  waist padding's weights, cloth kept off the body).
"""
import json
import math
from mathutils import Matrix, Quaternion, Vector

MIXAMO_BONES = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
                "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
                "RightShoulder", "RightArm", "RightForeArm", "RightHand",
                "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase",
                "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase",
                "LeftHandIndex1", "LeftHandPinky1", "RightHandIndex1", "RightHandPinky1"]
FORWARD, UP = Vector((0.0, -1.0, 0.0)), Vector((0.0, 0.0, 1.0))      # Blender: the subject faces -Y


# SAMPLING (a clean Blender process)

def load_clip(path):
    """Import a clip into an empty scene; returns its armature object."""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.lower().endswith(".bvh"):
        bpy.ops.import_anim.bvh(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


def _rigid_mesh_on(joint):
    import bpy
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        names = {g.index: g.name for g in o.vertex_groups}
        tops = {names[max(v.groups, key=lambda g: g.weight).group] for v in o.data.vertices if v.groups}
        if tops == {joint}:
            return o
    return None


def sample_frame(arm, frac, bones, props=None, prefix=None):
    """World rotations at rest and at the frame (a fraction of the clip), heads and tails of `bones`;
    for props (name -> the joint a rigid prop mesh is skinned to): "blade" gives the grip and the
    direction to the farthest vertex, anything else the mesh's centre and plane normal (away from
    the chest)."""
    import bpy
    import numpy as np
    act = arm.animation_data.action
    f0, f1 = act.frame_range
    frame = int(round(f0 + (f1 - f0) * frac))
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    pre = prefix if prefix is not None else next(
        (p for p in ("mixamorig:", "mixamorig1:", "") if p + bones[0] in arm.pose.bones), "")
    mw = arm.matrix_world
    rows = lambda m: [list(r) for r in m.to_3x3().normalized()]
    rec = {"frame": frame, "range": [f0, f1], "bones": {}}
    for b in bones:
        pb = arm.pose.bones[pre + b]
        rec["bones"][b] = {"rest": rows(mw @ pb.bone.matrix_local), "pose": rows(mw @ pb.matrix),
                           "head_rest": list(mw @ pb.bone.head_local), "head": list(mw @ pb.head),
                           "tail": list(mw @ pb.tail)}
    chest = mw @ arm.pose.bones[pre + bones[3]].head if len(bones) > 3 else Vector()
    dg = bpy.context.evaluated_depsgraph_get()
    for name, joint in (props or {}).items():
        ob = _rigid_mesh_on(pre + joint)
        if ob is None:
            continue
        eo = ob.evaluated_get(dg)
        me = eo.to_mesh()
        pts = [eo.matrix_world @ v.co for v in me.vertices]
        eo.to_mesh_clear()
        if name == "blade":
            grip = mw @ arm.pose.bones[pre + joint].head
            tip = max(pts, key=lambda p: (p - grip).length)
            rec[name] = {"grip": list(grip), "dir": list((tip - grip).normalized())}
        else:
            c = sum(pts, Vector()) / len(pts)
            n = Vector(tuple(np.linalg.svd(np.array([tuple(p - c) for p in pts]), full_matrices=False)[2][-1]))
            rec[name] = {"centre": list(c), "face": list(n if (c - chest).dot(n) >= 0 else -n)}
    return rec


def save(recs, path):
    json.dump(recs, open(path, "w"), indent=1)


# RETARGETING (the pose-test process)

def m3(rows):
    return Matrix([Vector(r) for r in rows])


def frame_of(along, ref):
    """Orthonormal frame (columns x, y, z): y along the bone, z the reference made perpendicular."""
    y = along.normalized()
    z = ref - y * ref.dot(y)
    z = z.normalized() if z.length > 1e-6 else y.orthogonal().normalized()
    return Matrix((y.cross(z), y, z)).transposed()


def palm_normal(wrist, index1, pinky1):
    return ((index1 + pinky1) / 2 - wrist).cross(index1 - pinky1).normalized()


def rot_about(arm, bone, axis, angle):
    """Rotate a pose bone about a world axis through its head (the armature at the origin)."""
    import bpy
    pb = arm.pose.bones[bone]
    bpy.context.view_layer.update()
    M = pb.matrix.copy()
    head = M.translation.copy()
    pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(angle, 4, Vector(axis)) @ Matrix.Translation(-head) @ M
    bpy.context.view_layer.update()


def roll_into_hinge(arm, bone, child, target, sign):
    """Roll `bone` about its length so `target` (the child's wanted direction) lies in the child's
    hinge plane (its local X rotation), bending the right way (sign +1 or -1 by the rig's X sense)."""
    import bpy
    pb = arm.pose.bones[bone]
    mw = arm.matrix_world
    bpy.context.view_layer.update()
    u = ((mw @ pb.tail) - (mw @ pb.head)).normalized()
    if u.angle(target) < math.radians(10):
        return 0.0
    cb = arm.data.bones[child]
    R_rel = pb.bone.matrix_local.to_3x3().inverted() @ cb.matrix_local.to_3x3()
    h0 = ((mw @ pb.matrix).to_3x3().normalized() @ R_rel).col[0].normalized()
    A = h0.dot(target) - h0.dot(u) * u.dot(target)
    B = u.cross(h0).dot(target)
    C = h0.dot(u) * u.dot(target)
    R = math.hypot(A, B)
    if R < 1e-6:
        return 0.0
    p0, dphi = math.atan2(B, A), math.acos(max(-1.0, min(1.0, -C / R)))
    best = None
    for phi in (p0 + dphi, p0 - dphi):
        phi = math.atan2(math.sin(phi), math.cos(phi))
        if sign * u.cross(target).dot(Matrix.Rotation(phi, 3, u) @ h0) > 0 and (best is None or abs(phi) < abs(best)):
            best = phi
    if best is not None:
        rot_about(arm, bone, u, best)
    return best or 0.0


def retarget(arm, rec, bone_map, palms=None, hinges=None, feet=(), pelvis=None, flex_sign=None):
    """Pose `arm` like the sampled reference frame `rec`.
    bone_map: [(reference bone, our bone)], parents first.
    palms: {our hand: (their hand, their index1, their pinky1, our index1, our pinky1)} for the palm axis.
    hinges: {our upper limb: (our child, their child, sign)}: the roll into the hinge plane; the child
            keeps only its bend about X, never past rest (sign > 0: positive X bends, as for elbows).
    feet: our bones aligned on the up axis (feet, toes); everything else on forward.
    pelvis: our root-most mapped bone, moved by the reference hips' height change scaled to ours."""
    import bpy
    B = rec["bones"]
    mw, inv = arm.matrix_world, arm.matrix_world.inverted()
    bones = arm.data.bones
    palms, hinges = palms or {}, hinges or {}
    children = {c: (s, u) for u, (c, _, s) in hinges.items()}
    src_root = bone_map[0][0]
    scale = bones[pelvis].head_local.z / B[src_root]["head_rest"][2] if pelvis else 1.0
    for src, dst in bone_map:
        bpy.context.view_layer.update()
        pb = arm.pose.bones[dst]
        R_rest = (mw @ pb.bone.matrix_local).to_3x3().normalized()
        Rs_rest, Rs_pose = m3(B[src]["rest"]), m3(B[src]["pose"])
        if dst in palms:
            th, ti, tp, oi, op = palms[dst]
            v_s = palm_normal(*(Vector(B[k]["head_rest"]) for k in (th, ti, tp)))
            v_t = palm_normal(*(mw @ bones[k].head_local for k in (dst, oi, op)))
        elif dst in feet:
            v_s = v_t = UP
        else:
            v_s = v_t = FORWARD
        Q = frame_of(Rs_rest.col[1], v_s) @ frame_of(R_rest.col[1], v_t).transposed()
        R = Rs_pose @ Rs_rest.inverted() @ Q @ R_rest
        if dst == pelvis:
            dz = (B[src]["head"][2] - B[src]["head_rest"][2]) * scale
            head = mw @ pb.bone.head_local + Vector((0, 0, dz))
        else:
            head = mw @ pb.head
        pb.matrix = inv @ (Matrix.Translation(head) @ R.to_4x4())
        if dst in hinges:
            child, csrc, sign = hinges[dst]
            roll_into_hinge(arm, dst, child, m3(B[csrc]["pose"]).col[1].normalized(), sign)
        if dst in children:
            sign = children[dst][0]
            bpy.context.view_layer.update()
            q = pb.matrix_basis.to_quaternion()
            e = (q @ Quaternion((q.w, 0.0, q.y, 0.0)).normalized().inverted()).to_euler("XZY")
            bend = max(0.0, e.x) if sign > 0 else min(0.0, e.x)
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0), bend)
    bpy.context.view_layer.update()


def ground(arm, sole_points, root):
    """Move `root` so the lowest of sole_points [(bone, point in the bone's rest space)] is at z 0."""
    import bpy
    bpy.context.view_layer.update()
    low = min((arm.matrix_world @ (arm.pose.bones[b].matrix @ p)).z for b, p in sole_points)
    pb = arm.pose.bones[root]
    M = pb.matrix.copy()
    M.translation.z -= low
    pb.matrix = M
    bpy.context.view_layer.update()
    return low


def seg_dist(q, a, b):
    d = b - a
    t = max(0.0, min(1.0, (q - a).dot(d) / max(d.length_squared, 1e-12)))
    return (q - (a + d * t)).length


def hang_chain(arm, names, samples, caps_now, rest_dist, bias_deg=8.0, limit=70, near=0.010):
    """Hang a bone chain (a cloak's, parents first) under gravity: each segment turns a degree at a
    time towards straight down tilted `bias_deg` back (+Y), about the horizontal axis across it, and
    stops where its cloth or the cloth below it comes within `near` of a capsule and deeper than it
    lay at rest. samples: {bone: [rest points in armature space]}; caps_now: [(a, b, r)] posed;
    rest_dist: {(bone, i): [distance to each capsule at rest]}."""
    import bpy
    target = Vector((0.0, math.sin(math.radians(bias_deg)), -math.cos(math.radians(bias_deg))))

    def touches(chain):
        for n in chain:
            pb = arm.pose.bones[n]
            T = pb.matrix @ pb.bone.matrix_local.inverted()
            for i, v in enumerate(samples.get(n, ())):
                q = T @ v
                for (a, b, r), d0 in zip(caps_now, rest_dist[(n, i)]):
                    d = seg_dist(q, a, b) - r
                    if d < near and d < d0 - 0.004:
                        return True
        return False
    turned = {}
    for k, n in enumerate(names):
        bpy.context.view_layer.update()
        pb = arm.pose.bones[n]
        d = (pb.tail - pb.head).normalized()
        ang = math.degrees(d.angle(target))
        if ang < 1.0:
            continue
        axis = d.cross(target).normalized()
        done = 0
        for _ in range(min(int(ang), limit)):
            rot_about(arm, n, axis, math.radians(1))
            if touches(names[k:]):
                rot_about(arm, n, axis, math.radians(-1))
                break
            done += 1
        turned[n] = done
    return turned
