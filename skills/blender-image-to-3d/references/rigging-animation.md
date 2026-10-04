# Rigging, sockets, animation and secondary motion

Read this before Phase 6 (articulation) and again before Phases 7 and 8. Applies to any asset that
moves: characters and creatures fully, vehicles and hinged props for the pivot and socket rules.

Not every rig needs every rule here. Section 0 says which rules follow from what the asset has;
the brief's NEEDS line (SKILL.md Phase 0) records the rows that apply, and the gates come from
those rows only.

Contents
0. What the asset needs
1. Skeleton families and hierarchy (1.1 rigid armour on helper bones, 1.2 helper bones in glTF)
2. Binding and weights
3. Extreme-pose sheet and test poses
4. Sockets and functional parts
5. Animation library and event contract (5.1 clips from motion libraries, 5.2 checks on the
   exported clips, 5.3 data for runtime retargeting)
6. Secondary motion (6.1 spring bakes, 6.2 skirts over legs that lift, 6.3 garment pieces sewn
   together)

## 0. What the asset needs

Every rigged asset gets the core:
- a skeleton from its family (section 1);
- clean weights (section 2);
- an extreme-pose sheet made with pose helpers that set values from the rest (section 3);
- sockets tested with their real attachments (section 4);
- an export whose round trip measures the bind pose (delivery-and-acceptance.md section 5).

The rest depends on what the asset has. Write the rows that apply into the brief's NEEDS line and
leave the others out:
- a robed caster whose hands never show needs no hand rows;
- a dog needs no garment rows;
- a chest with a lid needs only the core's pivot and socket rules.

| The asset has | Read | The gates add |
| --- | --- | --- |
| Hands that grip a weapon, tool or prop | 4 (hand sockets and grips) | every phalanx on the handle (`segment_gaps`); the prop clear of the body in every pose (`pose_overlap.py`) |
| Hands that show open or resting in held poses | 3 (resting hands) | finger joints by anatomy in every frame of the exported file; hand close-ups beside the reference's hands |
| Rigid armour over joints (pauldrons, cops, tassets) | 1.1; 2 (gloves, plates and hanging gear) | where each shell sits and which way it faces per pose, not only crossing counts |
| Spine, girdle or neck joints placed by hand | 1 (joint places) | each joint against mesh landmarks, beside the motion library's rig |
| Face shape keys or a face rig | 2 (shape keys) | every key scanned for vertices that move unlike their neighbours; the eye region by rays from the front |
| A cloak, cape or loose garment on bone chains | 6 | the cloth against the posed body and gear in every test pose |
| Chains baked by a spring solver (skirt panels, hair, curls, tails) | 6.1 | the largest turn of a chain bone per frame; depth in the skin; pictures of the fastest frames |
| A skirt or dress over legs that lift (kicks, sits, climbs, leaps) | 6.2 | cloth through the legs per frame, and the air between the cloth and a raised thigh per frame |
| Garment pieces built as separate meshes and joined (bodice and skirt, sleeve and cuff, collar and cloak) | 6.3; 2 (garments on the layer under them) | each seam's opening per frame; captures from above and below as well as level |
| Clips retargeted from motion capture or a library | 5.1, 5.2 | held poses beside a posed reference; clip ends that chain; triangle tests in every frame of the exported file; clips that start at time 0 |
| A quadruped or other non-biped body | 1 (joint places); 2 (weights against the library's rig); 5.1 | the held poses (sit, lie, eat) in profile beside a photo of the animal |
| Data for an engine or runtime retargeter | 5.3 | the data applied to the exported file's nodes, the way a consumer will |

## 1. Skeleton families and hierarchy

Keep the authoring rig and the delivery rig apart: RIG_CTRL holds animator controls, IK, pole
targets and constraints; RIG_DEF holds the deformation skeleton that ships. Export evaluated
deformation, never an expectation that the engine understands Blender constraints.

Rig families, so compatible assets share animation: humanoid biped, heavy or giant biped,
quadruped, winged, serpentine, wheeled vehicle, tracked vehicle, aircraft, hinged prop. One
family per asset; note it in the brief. A shared family saves animation work but does not
justify identical walk, reach or timing across roles.

Humanoid deformation hierarchy (names are a proposed convention, keep them stable across the
family):

```text
root                       ground origin, optional root motion
  pelvis
    spine_01 -> spine_02 -> chest -> neck -> head -> jaw
    clavicle.L -> upper_arm.L -> forearm.L -> hand.L -> fingers
    clavicle.R -> upper_arm.R -> forearm.R -> hand.R -> fingers
    thigh.L -> shin.L -> foot.L -> toe.L
    thigh.R -> shin.R -> foot.R -> toe.R
    garment and accessory bones where needed
```

Twist bones (upper arm, forearm, thigh), eye bones, jaw, breast or belly bones for heavy
builds, and cloth, wing, tail or antenna chains supplement this. Quadruped: spine chain from
pelvis through neck and head, four limbs with scapula, shoulder, elbow, carpus and hip, stifle,
hock, plus tail chain. Winged: humerus, radius, metacarpal, digit chains per wing with membrane
helper bones. Vehicles: body root, one bone or empty per wheel at the axle centre (child of a
steer pivot for steered wheels), per door at the hinge line, turret at the ring, barrel at the
trunnion, suspension bones if animated. Hinged props: base plus one bone per moving part at its
real pivot.

Rules: one root at the ground origin, a stable rest pose (A-pose or relaxed T-pose recorded in
the manifest), no negative or mirrored scale anywhere in the hierarchy, bone names without
numeric suffixes, DEF- prefix on deformation bones so export filters are trivial, object scale
applied before binding.

**Joint places.** When a skeleton is fitted, tabulate each spine, girdle and neck joint against
mesh landmarks: its height above the nearest landmark joint, its distance behind the front
surface, and its distance under the top line. Compare these with the motion library's rig scaled
to the asset, not only bone lengths. Skin on the far side of a bend swings by its distance from the
joint times the angle. On a dog, the neck's base joint sat level with the tops of the shoulder
blades, 11 cm above the shoulder joints and 3 cm behind them; the library's rig has it over the
shoulder joints. In a sit the breast and the points of the shoulders swung 64 mm ahead of the
throat. Four rounds of weights, retargeting and posture changes did not fix it. Moving the joint
did, and it left the standing poses as they were. When a part juts out in a held pose and it lies
beyond a joint that bends a lot in that pose, check that joint's place before weights, posture or
the mesh.

**Rules written as data.** `Bone.x_axis` and `Bone.z_axis` are in the parent bone's space; for
armature-space axes read the columns of `bone.matrix_local`. Reading the wrong one put a hand's
finger curl axes on the back of the hand. A Copy Rotation limited to one local axis (Y only,
AUTO order, influence k) turns by k times the Euler XYZ angle of that axis, not by a swing-twist
split. The two differ by up to 126 degrees in large turns. Check any rule written for an engine
or a retargeter against Blender's own evaluation over random turns.

### 1.1 Rigid armour on helper bones

Only for plates that span a joint (couters, knee cops, pauldrons, tassets). Joint armour gets a
helper bone at the elbow and knee:
- a short copy of the forearm's or shin's first quarter, parented to the upper bone;
- turned half the joint's bend by Copy Rotation (local to local, influence 0.5);
- carrying the couter or knee cop, with the upper lame on the upper bone and the lower lame on the
  lower bone.

A cop on one bone either stays behind the joint or swings into the limb.

Shoulder armour (a pauldron or spaulder: a cap and lames) is one rigid shell on its own helper:
- parented to the clavicle, aimed at the upper arm's tip;
- turned by a Damped Track to that tip at about 0.9 influence: the arm's swing, none of its twist;
- pivoting about a third of the way from the shoulder joint up to the cap's crown.

Weighted like the padding under it (clavicle to upper arm by distance down the arm), the plates
bent through their middles with the arm raised, and a review called them "extremely bent and
crushed as if there isn't even anything inside of the armor". Linear blend skinning bends any
rigid shell that spans two bones.

Copying the arm's whole rotation instead spun the shell round the arm with the humerus. Retargeted
arms twist a long way about their own length (130 degrees in an overhead strike, measured as the
twist left after the swing), and the review found "the pauldron completely turned where the armor
is facing away from the camera". With the pivot off the arm's axis, the twist also swung the shell
down the arm, so "the arm appear[ed] to be almost removed from the body via the shoulder only
connected by a thin piece of flesh". A strap over the shoulder carries the swing; the arm turns
inside the shell.

The pivot trades two faults:
- at the joint, the cap's inner edge dives into the neck and breastplate as the arm rises;
- at the crown, the shell slides off the shoulder (8.9 cm with an arm raised 138 degrees);
- a third of the way up kept both small.

One fraction for every direction still pressed the cap's inner edge into the collar (the padding and
breastplate by the neck) with the arm raised high or swung back, 20 to 40 intersecting triangle pairs
per pose. If the poses reach that, limit the helper's swing there, and have the engine apply the same
limit.

Give each plate its own helper only if the plates are built to slide: shells about one centre with
room between them. Lames nested 2.5 mm apart as bands round the arm crossed each other under any
difference in turn, even in the idle pose.

The twist the shell leaves out has to reach the elbow in steps. Put it in one row of faces and 130
degrees wrung the sleeve above the elbow like a towel: the middle of a row twisted by an angle
narrows to the cosine of half of it. Give the limb twist bones (the arm's full swing plus 1/3 and
2/3 of its twist: a Damped Track, then a Copy Rotation of the arm in pose space at 1/3 or 2/3
influence) and a ring of vertices on each. Rows of about 40 degrees narrow by 7 percent.

### 1.2 Helper bones in glTF

glTF carries no constraints:
- The exporter samples each helper's turn into exported actions.
- A pose made at runtime must drive each helper from its target's change from rest,
  `d = targetRest^-1 * target.quaternion`, with the rest (bind) local rotations stored at load:
  - a joint helper sharing its target's parent and rest orientation, as Blender's local Copy
    Rotation assumes: `helper.quaternion = helperRest * slerp(identity, d, f)`;
  - a swing helper (Damped Track): the from-to rotation between the rest and current directions
    toward the target's tip, in the parent's frame, slerped by f;
  - a twist step: split d about the bone's own Y into `twist = normalize(0, d.y, 0, d.w)` and
    `swing = d * twist^-1`, then `helperRest * swing * slerp(identity, twist, k)`.

  `identity.slerp(target.quaternion, f)` is only right when the rest rotation is the identity.
  A helper made by a one-axis Copy Rotation follows the Euler angle instead (section 1): write the
  rule the rig really evaluates.
- Write that note into the manifest.

## 2. Binding and weights

Bind every deforming costume piece to the same skeleton. Normalise weights, remove tiny
influences, inspect unweighted vertices (validate.py fails on these). Start with four influences
per vertex as the delivery target and raise it only if the engine and a measured budget allow.
Rigid armour follows one bone or a controlled small set; flesh around shoulders and hips needs
smooth transitions and twist management. Blender's Armature modifier has a Preserve Volume
option that changes the result; verify deformation in the target engine rather than trusting a
viewport setting (Armature modifier reference:
https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html).

Do not apply an Armature modifier as a cleanup step on a bound character; that bakes a pose into
the mesh and breaks the rig relationship. Apply only the modifiers meant for the delivery copy
(Mirror, Bevel, Subdivision, Solidify) and only on that copy.

Fix deformation problems in this order: joint placement, topology, weights. Corrective shape
keys are a targeted tool for a specific pose, not a substitute for a viable bind.

Rules that apply when the asset has the part:
- **Garments on the layer under them.** A tight garment that pokes or gapes when the trunk turns
  takes its tight bands' weights from the layer right under them (the nearest points facing the
  same way, from beneath). A bodice mostly on the chest bone let skin and slip through it in a
  48-degree twist at 1754 sample points; weighted from the layers under it, 425, none deeper than
  3.5 mm. Rules that held:
  - loose parts (cups, back, straps) keep the skin's own weights with a tenth of the arm bones, so
    armholes stay whole when an arm rises;
  - both sides of every seam take the same weights, welded to the single nearest other part
    (welding an edge to every nearby panel pulled the welds against each other);
  - each LOD is computed against its own body and under-layers: LOD0's weights copied to coarser
    levels by surface opened their seams to 20 mm.

  Judge each variant with renders that give each layer its own flat colour, in the test poses,
  beside the numbers: the counts alone hid where the gaps were.
- **A band sewn into another piece** (a skirt's top under a bodice's edge) takes the weights of the
  piece it is sewn into for its first rows, easing into its own bones below. On the trunk's bones
  alone, a skirt's sewn band parted 2 to 3 cm from a bodice edge that followed the thigh
  (section 6.3).
- **Weights against the motion library's rig.** When a held pose shows a ledge, popping shoulders
  or a dragged chest, tabulate who holds that skin before tuning blends or the retarget: the mean
  weight per bone over bands of the surface (the chest's front by height and by distance from the
  mid-plane, the top line every few centimetres), beside the library's own rig. Then take the pose
  apart: the same pose with one group of bones held rigid with its parent at a time. On one dog
  the neck's bones held 0.98 of the forechest's skin at the shoulder joints' height, where the
  library's rig has 0.62 on the chest, so the chest swung with every head turn. The cause was the
  cage's neck rings: oblique to the bones, with their fronts 13 to 15 cm below where they cut
  their bone, and a ring counted as one unit. Never let rings oblique to the bones choose the home
  bone where they reach far past it. Give skin that lies on rigid structure (breastbone, skull,
  pelvis) to that structure. Try weights in a fast loop (weights file, posed arrays, clay shots)
  before binding, and rerun the exported clips' checks after any weight change: a change at the
  throat let a hidden tongue root show through the skin.
- **Shape keys.** Scan every key for vertices that move unlike their neighbours, and fail the
  build above a few millimetres. Measure the eye region by rays from the front: lining or eyeball
  seen where skin should cover is a fault. Stock face units (ARKit-style cheekSquint, eyeSquint,
  the smiles) push the lower lid through the eyeball and the socket lining, and they add up: mixes
  bring the socket's lining through the lid. Make a hero expression one finished shape (the mix
  folded, then the lids cleared off the eyeball and the lips off the teeth), not a set of weights.
  Cards and lashes fitted at rest lag behind in keys unless each card follows its root as one
  piece. An edit made to the keys alone leaves the mesh's own vertex positions stale
  (blender-5-notes.md section 1).
- **The binding a measurement depends on.** A tool that adds a rig can repoint the body's
  Armature modifier at the new rig (MPFB's `add_builtin_rig` does), and every posed copy and
  posed measurement after it silently uses the rest pose. Make helpers that pose-copy a body assert
  which armature it follows, and when a posed number looks implausible, print one skin vertex at
  rest and posed first.

When the character wears gloves, plates or hanging gear, these rules kept a one-piece glove, its
plates and hanging gear clean:
- **Glove webs.** The web between two fingers takes both nearest finger chains, blended by how
  near each is. Nearest-chain-only weights tear the web into a sliver when neighbouring fingers
  close by different amounts.
- **Under plates.** Glove vertices under a rigid plate (the back of a gauntlet) follow the plate's
  bone. Otherwise a thumb chain that happens to lie nearest drags them through the plate.
- **The glove's cuff.** Its end blends into the forearm inside the leather cuff, so a wrist turn
  twists it out of sight.
- **Hanging gear.** A pouch rides the tasset or skirt it hangs on, taking that part's rule, so the
  two move together when the thigh lifts.
- **Cloaks.** Keep them on their own chains. Blending a cloak into the shoulder bones where it
  rests on a pauldron dragged its edge into the backplate whenever an arm moved forward.
- **Cloth under a collar's roll.** Where a cloak runs up under a collar, that part takes the
  collar's own weights, blended in below the collar's hem, so a hem tucked into the cloak stays in
  it. With the cloak's top on the chest alone, it slid through the roll whenever the neck or a
  shoulder moved: 2713 intersecting pairs over the test poses, against 298 with the collar's weights.
- **Padding under a rigid shell.** The sleeve under a helper-driven pauldron rides the same helper
  where the plates cover it, and hands over to the limb in the bare gap between two plates (the
  lowest lame and the elbow cop). The gap needs an edge loop at each end. With a single ring in it,
  some face under one plate or the other had to shear, and showed through that plate. From the gap
  down to the elbow, each ring rides one twist step. The gap's first row also takes the shell's lag
  behind the limb (its top ring sat up to 4.4 cm off the arm's swing with the arm raised 138
  degrees), so it needs its length: measure that offset before moving rings up to fit more steps.
  Blend the ring nearest a bent joint a little into the next bone too (a wider blend about the
  elbow), or its full width meets the forearm plate's rim in the crook.
- **Collars under a neighbouring plate.** Padding tucked under a plate on another bone (a
  sleeve's collar under the gorget ring) keeps the blend it had. Moved onto the pauldron's helper,
  it rode into the ring even in the idle pose.

## 3. Extreme-pose sheet and test poses

Before accepting a rig, render (review_render.py with `--action` and `--frame`) a sheet of the
worst poses the asset will actually hit and inspect every separate part together:

Bipeds: arms overhead, forward reach, crossed-arm cast, deep elbow and knee bend, hip flexion,
full stride, wide stance, bow draw or two-handed grip, torso twist, crouch, death pose. In a
skirt or dress, add the high kick, leap, side kick, kick behind and deep squat.
Quadrupeds: full stride at gallop, pounce crouch, rear, head turn, bite gape, tail curl, and the
held poses (sit, lie down, eat).
Winged: full fold, full spread, downstroke, banked turn.
Vehicles: full steering lock, full suspension compression and rebound, doors and hatches at max,
turret and barrel at limits.
Props: hinge at both limits.

The sheet also holds:
- the stance the concept shows, holding what the concept holds;
- for a character that carries a weapon, every weapon state the game shows, in hand and stowed. A
  test file can key a stowed item between two sockets with two Copy Transforms constraints, the
  second's influence keyed per frame with constant interpolation.

Bend hinges (elbows, knees, fingers) about the bone's own axis, a local rotation. A world-axis
turn applied after the parent has turned twists the joint.

**Pose helpers set values from the rest.** Every helper that poses a bone resets it and sets the
final value from the skeleton's rest on every call; it never adds to the pose the bone already
has. A helper called twice is the usual trap, and one called inside a search loop is called many
times:
- A hand helper added a finger curl each call and ran inside a loop that opened the arms a degree
  at a time until the hands cleared a skirt. The curls summed to knuckles bent 73 to 85 degrees
  backwards and fingers twisted 120 to 170 degrees about their length: "broken and dislocated".
  The one pose that called it once looked like a fine loose fist, and whole-figure renders hid it.
- A foot helper aimed "flat" with the ankle-to-ball line level. On that skeleton the line falls 28
  degrees at rest, so every flat foot stood on its heel.
- A leg posed twice added its turnout twice.

Measure what the helper produced (heel and ball heights, joint angles), and render one pose per
sign convention before trusting a helper: a spine helper turned by the negative angle made every
forward bend go backwards, and its numbers did not show it.

**Resting hands.** For hands that show open, relaxed or in loose fists:
- Set the fingers in absolute joint angles about each finger's own hinge, never as a curl added to
  the bind pose. Base meshes often bind with curled, fanned fingers and the thumb out (MakeHuman's
  hands: about 20 degrees per knuckle, fanned 35), so a "flat" hand stands on its fingertips and
  every added curl ends as a fan.
- A loose fist (dancers, soldiers at attention, runners): knuckles 40 to 55 degrees from the index
  to the little finger, middle joints 70 to 82, end joints 30 to 35, the fan closed so the curled
  fingers touch.
- The thumb bends about 20 and 30 degrees at its two joints, with its pad resting on the curled
  index finger's last bone. It never reaches past the curled fingers. A nearly straight thumb
  hanging below them read as "awkward", like a thumbs-down, while every number passed.
- Gate the fingers in every frame of the exported file by anatomy:
  - each joint's bend about the hinge square to the finger and its nail;
  - sideways bend and twist measured against the rest;
  - neighbouring fingers' skin not overlapping;
  - the fingertips under the palm.

  Make the gate fail on a known-bad build before trusting it to pass a good one. A passing gate
  does not judge the look: compare hand close-ups with the reference's hands.

Take the poses from reference motion wherever a clip exists for the asset's kind of movement: the
user's clips, a Mixamo library, motion capture. Poses built from a few whole-bone rotations (both
arms 105 degrees sideways, the thighs turned -95 with nothing else moving) keep none of a real
body's balance, and a review called them "cartoonishly and hilariously unrealistic". Keep each test's
purpose (shoulders up, reach, deep elbow bend, crouch, stride) and pick a real frame that loads the
same joints: an overhead strike's wind-up, a lunge, a block, a crouch, a walk. Name each pose after
what its frame shows in a render of the clip, not after the clip's title: a clip called Attack,
sampled at 60 percent, was the follow-through of a sweeping cut, not the thrust its first name
promised. `assets/retarget_tools.py` samples frames in their own Blender process and retargets
them. Its docstring gives the method:
- rest frames aligned on two anatomical axes, the palm's normal for the hands;
- limbs rolled into their hinge planes, no bending past rest, the forearm's roll at the wrist;
- the root scaled to our hips, and the lower sole on the ground;
- props aimed at the reference prop's placement rather than copying its hand;
- cloth chains hung under gravity against capsule proxies of the body and of the gear hung on it
  (a scabbard and its straps: without them a cloak hung through the scabbard in a crouch).

Real motion finds deformation limits that the synthetic poses hid, such as hip skirts and tassets at
90+ degrees of hip flexion, rigid cuffs at bent wrists, pauldrons against the breastplate when an
arm swings across, and a scabbard rigid on the pelvis meeting the raised thigh at its throat in a
crouch. Record them with their counts. Fix what the weights can: belts on the waist padding's own
rule, and cloth kept off the body. A plate that must hinge at its straps (a tasset) needs a helper
bone, not a blended weight: pinning its top to the pelvis moved the collision into the thigh
plates. Gear that rides on straps (a scabbard) needs a swing bone driven by the thigh for the same
reason.

Measure the sheet with `scripts/pose_overlap.py`:
- **Body and garment pairs** are compared with the bind position (the armature at REST). Never
  compare with a test frame used as a baseline: a weapon clipping in that frame vanishes from
  every count.
- **Weapons and carried gear** are counted absolutely, allowing only a glove on its own grip.
- **Claims** such as "no weapon crosses the body in any pose" are read back from the report, pose
  by pose, before they are written. One summary said so while its own file listed a shield through
  the scabbard in one pose.
- **What shows.** A pair count says that two parts cross, not whether it shows. Before fixing a
  contact seen in a close-up, cast rays:
  - from the limb's axis out through the cloth: cloth past a plate's outer surface is a visible
    poke-through, with its depth;
  - from the review camera through the plate the cloth hides: one cloth crossing before the plate
    means the plate is under the cloth, two mean it is behind the limb.

  An elbow strap half hidden by a twisted sleeve's outline looked like a poke-through at close
  zoom. The rays put it behind the arm.
- **Where rigid parts sit.** A shell spun round the limb or slid off its seat crosses nothing. For
  each part on a helper, read per pose the twist it took (a shoulder plate takes none), how far it
  moved from its seat (the cap's crown from the top of the shoulder), and whether the layer it
  covered now shows. The first fix for crushed pauldrons cut their contacts from 1582 to 320 while
  one faced backwards and another hung down the arm, baring a slim sleeve that had only ever been
  seen under the cap.

Pass criteria:
- no collapsed volume at joints;
- no interpenetration between armour or garment pieces;
- no exposed holes;
- feet or wheels stay on their contact plane;
- anything held stays in the hand, clear of the body.

## 4. Sockets and functional parts

Sockets are semantic attachment points: `SOCKET_hand.R`, `SOCKET_hand.L`, `SOCKET_weapon_tip`,
`SOCKET_back`, `SOCKET_head`, `SOCKET_chest`, `SOCKET_foot.L`, `SOCKET_mouth`, `SOCKET_muzzle`,
`SOCKET_exhaust`, `SOCKET_seat_driver`, `SOCKET_hinge_door.L`, `SOCKET_summon_origin`. Each is an
empty with an arrows display, parented to the bone or part it follows, with local +Y as the
forward of whatever attaches and +Z as its up. Record the convention and any custom properties in
the manifest (export_delivery.py does this).

Test a socket with its real attachment and animation: a weapon in the hand through the whole
attack, a rider in the seat through the gallop, a muzzle flash at the muzzle during recoil. An
empty at the hand origin proves nothing.

With `--split-lods`, export_delivery.py puts the sockets in the LOD0 file and the combined file
only (the manifest's `sockets_in_files`). If the engine loads LOD files on their own, export the
sockets with every level, and count them in each file before saying they are there.

Hand sockets and grips, for characters that hold things (`assets/grasp_tools.py`):
- **The seat.** Place the hand socket where the handle rests in the open hand (`grip_seat`):
  - diagonally across the palm, index end distal (a power grip; 5 to 15 degrees);
  - crossing the index finger's line about 8 mm below its knuckle, at the base of the fingers (a
    sword is held in the fingers, not deep in the palm);
  - lowered onto the glove (palm and straight fingers) until it touches.

  A socket placed at a point in front of a fist puts the handle under the finger bases, and every
  finger hooks instead of wrapping. With the handle 20 mm down in the palm, even a knuckle bent to
  its limit left the proximal phalanges 10 to 24 mm off the grip. Sweep the seat's depth and
  diagonal with `segment_gaps` and keep the one that puts every phalanx on the handle.
- **The grasp.** Close the fingers on the weapon's own mesh (`grasp`), each with every phalanx on
  the handle (`wrap_finger`):
  - Search the MCP and PIP together (the DIP follows the PIP) for the least sum of the three
    segments' gaps, with no glove point inside the weapon.
  - The thumb then closes over the curled index finger.
  - Do not close every joint in one fixed proportion until the first contact: that stops at the
    fingertip and leaves the base segments standing off the handle in a loop, which reads as
    "fingers curled, smashed against the handle, not around it".
  - Measure the result with `segment_gaps`: a natural grip has the palm and every segment within
    about 6 mm of the handle.
  - Test thin shells as well as solids: a glove point is inside when the line from its bone's axis
    out to it crosses the weapon's surface. A finger pushed right through a 2 mm shell (a basket
    hilt, a knuckle guard, a shield boss) sits on its outer side, where the nearest-surface sign
    alone reads it as clear, and the search happily accepts it.
  - The weapon rides the hand socket, so the grip is the same in every pose: solve it once per
    hand and reuse the digit rotations.
- **Aiming.** Aim each held weapon: turn the hand about the forearm (pronation and supination),
  deviate and flex the wrist, and rotate the humerus. Score each candidate against the posed body
  (`posed_body_tree`, `body_clearance`), not capsules. The hips, belt and pouches reach 0.20 m in
  front of the pelvis, and a fat capsule forbids the pose the concept shows. Points sampled on the
  prop miss a thin part that passes between them: a scabbard went through a shield's board between
  two sample rings 8 cm apart while the samples read 13 mm clear. Add the exact test: place the
  prop's mesh at each candidate and count its triangles crossing the body (`prop_hits`), and let
  any hit lose to every clear candidate.
- **Held props with a fixed grip** (a shield's handle, a lantern's bail, a torch, a staff): take
  the socket's axes from how the object is used, not from the palm. A centre-grip shield, for
  example, is held as a punch with the knuckles into the boss, so its face axis runs along the
  hand's length (a palm facing the board read as "the wrong way" in a review). Anything that
  encloses the hand (a boss, a basket hilt, a knuckle guard) must hold the closed fist: measure the
  fist's envelope in the object's frame and keep its inner surface about 5 mm beyond it
  (categories.md has the shield numbers).
- **The arm that holds it.** When the concept shows only a pose, take the arm from a reference
  clip of the same action (Mixamo, motion capture, video): with a fixed grip the forearm's
  direction decides where the object sits and which way it faces. Keep the hand near its neutral
  roll. Pronation or supination applied at the hand alone turns the wrist inside rigid forearm
  armour (a 70-degree roll pushed a wrist through its vambrace); bend the elbow and shoulder
  instead, or add a forearm twist bone that carries about half the roll. Then compare the held
  object's height and facing with the concept.
- **Stowed gear.** Place the back or hip socket by ray casts: the stowed item's back must clear
  the cloak and body everywhere by about 10 mm, not at one point.

Hinged parts pivot at the hinge. Bows need real string and nock motion. Shields need a grip
orientation that works through every animation. A breath or projectile origin must agree with
the effect cone and the gameplay aim. Gameplay hit shapes stay separate from decorative teeth,
fingers and spikes.

## 5. Animation library and event contract

Author animations as individually named Actions with deliberate start and end frames and a loop
flag (custom property `loop` on the action, or a `_loop` suffix). Use one authoring frame rate
(30 fps default) but express gameplay events in seconds or normalised time; never assume a frame
count equals a cooldown.

Starting library by family (adapt to the actual game):

| Family | Minimum library |
| --- | --- |
| Player character | idle variants, forward/back/left/right locomotion, starts and stops, turns, basic attack, ability gestures, dash or dodge, hit reactions, stun, downed loop, revive, death |
| Melee enemy | idle, move, attack anticipation, active, recovery, hit variants, stagger, death |
| Ranged or caster enemy | idle, move, aim, cast or fire, recoil, interruption, death |
| Quadruped | idle, walk, run, turn, bite or lunge, recoil, death, with correct foot contacts and spine timing |
| Flying or floating | hover loop, flight loop, banking turns, attack, interruption, fall or dissolve |
| Boss | locomotion, each move family, phase transition, telegraph poses, stagger, death |
| Vehicle | idle, wheels spin (driven by code), suspension bounce, doors open and close, turret traverse, destroyed state |
| Interactable | open, close, locked, active, hit, break, channel states |

Per attack record: anticipation, authoritative active window, recovery, allowed cancels,
locomotion permission and interruption behaviour. Keep a clear silhouette change on major
attacks, and start any telegraph early enough for the intended escape window. Put these as pose
markers on the Action (`action.pose_markers`, shown with Show Pose Markers in the Action Editor)
named `active_start`, `active_end`, `hit`, `release`, `cancel_ok`, `footstep.L`; export_delivery.py
writes them to animation-contract.json in seconds.

Locomotion: in-place clips for an initial engine port, each tagged with its authored speed
(action custom property `speed_mps`) and blend direction; preserve root displacement separately if
root motion is adopted later, and let the engine validate that displacement. Layer upper-body
attacks over lower-body locomotion with an explicit reference pose and mask; keep pelvis and root
out of the additive layer unless deliberate. Test attacks while moving backward and sideways.
Foot IK corrects presentation to the floor without moving the authoritative position.

Delivery: bake IK and constraint results to the deformation skeleton, check interpolation between
samples, check loop seams for root drift and pops, keep the unbaked Action master. Ship the
neutral pose, event metadata and clip lengths with the animations.

### 5.1 Clips from motion libraries

Source the motion from the user's libraries (Mixamo, motion capture, purchased packs) and
retarget it. Hand-keyed and procedural sine-wave clips were called "janky" as soon as a user saw
them. Use the library's rig as a measured reference for joint places and weights as well
(sections 1 and 2), and record each pack's licence with the asset's sources.

- **Bone axes.** A bone's Y is not the limb in every imported skeleton: Unreal mannequin and 3ds
  Max Biped files keep it on X, Mixamo on Y. Poses copied by axis came out a quarter turn off.
  Rebuild each sampled bone's frame from the joints' positions. A Biped clip's rest may lean, so
  the trunk bones need an upright reference. Render the first sampled poses before trusting them.
- **The first frame.** Motion capture files can start with a calibration T-pose (CMU's BVH files
  do). Start the clip at the first real frame; baked from the T-pose, a spring solver swung every
  chain through the body as the arms dropped. Leave out frames where the retarget itself snaps a
  limb, and say which.
- **Bind poses that cannot reach the source.** A bind pose with bent elbows (MakeHuman's game rig:
  about 40 degrees) and a hinge that never straightens past rest make a straight arm unreachable,
  and a solver bends the trunk instead. Parametrise the elbow as its total bend about the true
  hinge.
- **Feet.** Pin a foot to the floor only while it is planted, found from the source's foot height
  and speed. Grounding every frame flattens hops and leaps. Re-solve contacts for the target's own
  soles and heels.
- **Rig devices are not motion.** A library rig's sliding shoulder-blade bones (moved 6 cm up the
  chest in a sit, 12 in a lunge) and bends inside the ribcage made lumps beside the neck and a
  ledge across the brisket on a mesh whose skin rides the blade. Aim the target's joints at the
  source's joints. Find by a slide test how far a bone can move before the skin lumps (about 20 mm
  on a dog), and limit it to that. Keep the ribcage one piece, and let the legs' IK and the neck
  take up the rest.
- **The source's pose is not the target's.** A faithful copy of a library's tall sit put a
  shorter-bodied dog's chest ahead of its forepaws and its head behind them. A photo of the
  real animal showed the forelegs slanting back as props. A photo of the target is the reference for
  posture. Compare a handful of relations in profile with bones: shoulder against wrist, head
  against wrist, the neck's lean, the back's slope.
- **Rules keyed to the body's state.** Condition a correction on the character's physical state
  ("in the air": hips well above standing height), not on what the source happens to do ("the
  library's tail is higher than in its stand" also fired in sits and death falls).
- **One change at a time.** Compare a rule on and off only on a build with no other open fault,
  and re-test a rejected rule once a confound is fixed. A rule thrown out for 30 to 185 mm pops was
  clean once a wider weight blend, which had made a clearance cloud count the tail's own root as
  body, was fixed. Keep a script that runs every take through the solver and prints what changed
  against the last build's records, and run it after every solver or weight change.

### 5.2 Checks on the exported clips

Test the exported file, not the master, in every frame of every clip:
- **Triangle tests** for whatever can collide:
  - mouth parts against each other and the lining;
  - tail and ears against the body;
  - legs against each other;
  - garments against the legs and the layers under them;
  - the body against the floor.

  A model of the skin is not the skin. A solver's capsules (a percentile of the limb's radius)
  reported paws clear while one paw sat in the other leg in every frame of a sit. On one dog, the
  test written after a user found the tongue through the teeth found four more faults nobody had
  seen. On a sibling dog it found the tail through the body in 68 of 111 clips.
- **Held poses** (sit, lie, eat or drink loops): render them lit and in clay from the front,
  three-quarters and side, beside a hand-posed version of the same pose on the control rig, and
  in a real-time viewer in motion, from behind and above as well as from the side.
- **Clip ends that chain.** Clips that share a pose (stand, sit, lie) must agree at their first and
  last frames bone by bone; takes that shared a pose differed by up to 39 mm in a paw, a pop
  whenever the clips are chained. Decide anything that depends on neighbouring frames (planted or
  not, a stance's held place) at a take's ends from all the takes that share that pose.
- **Loops.** Join a stance across a loop's seam (later frames one stride on), or a slide at the
  seam stays invisible to the check. Give the contract explicit start states (which feet are down
  at the first frame), not events alone.
- **Time 0.** Every exported clip's first key is at time 0 (export_delivery.py exports with
  `export_anim_slide_to_zero`; roundtrip.py reads the key times from the file). An action keyed
  from frame 1 otherwise exports with its first key one frame in. A player holds the first pose
  for a frame and a loop stalls once per cycle. No frame-by-frame check sees it; compare the pose
  at clip time 0 with the pose one frame later.
- **Test clips stay out of the asset's own file.** Viewers auto-play the first clip, and the round
  trip measured a raised-arms pose as the asset's height.
- **A new check that disagrees** with the old ones is evidence about the asset, the new check and
  the old checks at once. Print the disputed frames from the solver's own data before changing the
  asset. A browser probe that reported 8 to 19 mm of paw slide had read a looping clip's events as
  if they did not wrap. The same look found two real blind spots in the old checks.

Report the numbers with the delivery, and run the checks from the export step so they run every
time. A defect class the user finds on one asset is a question about every asset built the same
way: run the new check on the siblings before the user looks at them.

### 5.3 Data for runtime retargeting

When an engine or a runtime retargeter consumes the rig, ship its data with the asset:
- a reference T-pose as glTF node rotations, and as each joint's turn from rest;
- each finger's curl axis, its limits, and the twist helpers' rules as data, in the form the rig
  really evaluates (section 1);
- the root's frame and the feet's contact heights.

Check it on the exported file the way a consumer will: set the file's own rotations on the
exported nodes and measure the result, not the master's bones.

## 6. Secondary motion

Three responsibilities stay explicit: the visible garment, the simulation or deformation
representation, and the collision representation. A detailed render robe is not automatically the
simulation mesh or the collision surface. The same applies to chains, tassels, antennae, wing
membranes, tank tracks and hanging cables.

Authoring process:
1. Build a low-resolution, evenly distributed simulation cage with stable panels and enough
   resolution for the intended folds. Transfer its motion to the render garment through a
   validated bind (Surface Deform or Mesh Deform in Blender, or the engine's cloth workflow).
2. Pin real attachment areas (shoulders, collar, belt, wing bones) with a graded transition. Leave
   intended hems free. Model real clearance around legs, elbows, mantle and belt before tuning
   any physics.
3. Create simple torso, pelvis, thigh and limb collision proxies aligned to the posed skeleton
   (COL_ objects). Test the render garment against the visible body and the proxies: an oversized
   capsule keeps cloth numerically outside while it visibly floats.
4. One owner per vertex's final motion. If the solver receives skinned positions, do not apply the
   armature transform a second time. Never stack two garment solvers.
5. Fixed-step updates and bounded iterations against a measured CPU budget. Test low frame rates,
   hitches, rapid reversals, backpedalling, strafing, casting, full dash distance.
6. Explicit reset or rebase on teleport, respawn, reconnect and large position corrections.
7. A distance or quality fallback: a small bone chain or an authored secondary-motion loop, with
   a clean freeze or blend into it.

Keep thickness and render subdivision from turning into self-collision noise. Separate the inner
robe from the outer cape with real space and a stated collision policy. Full simulation is for a
bounded number of nearby assets; everything else gets the bone fallback.

A garment's rest shape is designed over the body or draped by the cloth solver, never modelled as
tubes. For clean fabric at the neck (a cowl, a collar, a hood lying down), design it on a membrane
over the support (categories.md section 2). A solver's drape of a bunched cowl stayed crumpled
however it was finished. With the solver:
- a pleated start shape above the collision copies, pinned where the garment is held;
- a fixed frame rate and frame count;
- the settled mesh kept as the rest shape.

Cloth that starts inside a collider stays inside it.

Drape and groom against the pose the part will be seen in, not the bind pose. Curls draped
against the raised arms of an A-pose bind slid down them and stood 36 cm out from the head once
the arms came down; draped against the skin posed in the concept's stance, they lay on the chest
and back as the concept has them.

When gear or plates sit over the cloth:
- Gear stowed over a garment holds the cloth under it. A shield, pack or quiver strapped over a
  cloak pins the cloak's top segments, so a pose that swings the cape back off the legs must not
  carry it through the item. `grasp_tools.settle_chain` turns each chain bone forward until its
  vertices clear the item, and passes the turn it gave up to the bone below. The cloth then folds
  under the item's edge and still clears the legs. Test against everything that stands off the
  item's back (rims, buckles, straps), not only its board or body.
- A plate the arm raises lifts the cloth lying over it: a rigid pauldron rose through the cloak
  when the sword arm swung out. Test the cloth against the posed plates once the arm is final
  (after any aim search that turns the humerus). Turn the chain's top bone back until its cloth
  clears, then hang the bones below again (`grasp_tools.settle_chain` with a lifting axis and step).
- A bone chain cannot keep a cloak that hangs over the shoulders off an arm swung back into it, and
  with gear stowed over the cloak there is often nowhere for the chain to go. List those contacts
  for the runtime cloth or spring solver's arm capsules instead of bending the chain through
  something else.

### 6.1 Spring bakes

A Verlet-style spring solver tuned per fixed step (1/60 s, say) must run each step at its real
length, with its parameters converted to that length:

```text
d_h = 1 - (1 - d) ** (h / DT)     drag per step of length h, for a drag d tuned at step DT
s_h = s * d_h / d                 stiffness to match
```

One bake computed its step and never passed it, so it was right only at 30 fps with two substeps.
- More substeps is not automatically better. Position-based collision gives a kick of about the
  correction divided by the step. On a fast dance clip, 7 to 12 substeps gave larger turns per
  frame than 2, and no less depth in the skin. Pick the count by measurement, per asset.
- Colliders that the cloth gives way to on fast limbs (hands passing the hips) snapped a skirt 77
  degrees in one frame. Keep the arms clear of the cloth by posing, or limit the chain's turn per
  frame, rather than letting a fast collider shove it.
- Measure three things over the whole bake:
  - the largest world turn of any chain bone per frame (over 45 degrees is a snap);
  - the cloth's depth in the skin, with a baseline taken on the settled first frame (a whole-hair
    measure read 85 mm deep before anything moved);
  - rendered frames at the fastest turns.

### 6.2 Skirts and dresses over legs that lift

Measure two things in every frame of the exported file, the bind pose as the baseline: the
cloth's triangles that cross the legs and the layers under the skirt, and the air between the
cloth and a raised thigh (the median gap over stations along the top of the thigh). A pixel test
from level cameras passed a skirt with 926 triangles through the thigh. A skirt with no clipping
at all hung 76 to 96 mm over a kicking thigh and read as "magically floating". Some air between
leg and cloth is better than clipping, but cloth hanging on nothing looks as wrong.
- **Colliders fitted to the side the cloth rests on.** Fitted to the flesh all round, a raised
  thigh's collider is sized by the buttock and hip side and stands 25 to 35 mm over the top of the
  thigh. Fit it per pose to the flesh facing up, and taper it (two capsules along the thigh), or
  the buttock sizes it for a thigh raised behind.
- **Cloth between the chains.** A ring of bone chains cannot wrap a limb: holding the chords
  between columns off the collider held the columns 25 mm off it. Let the cloth between joints sink
  into a raised limb's collider (a soft allowance), and let a mesh-level fit put the real cloth on
  the skin.
- **Root bones.** Give each column a root bone at the seam, posed at half its column's turn,
  between the pinned top and the chain. A solver folded front columns up 150 to 178 degrees between
  thigh and belly; blending trunk weights into such a column collapsed the cloth, and the
  inverse-skin offsets of a corrective fit exploded to metres in the exported file while the
  master looked fine. Fix the rig, not the arithmetic.
- **Deep hip flexion.** Past about 70 degrees, linear skinning turns the thigh into the belly at a
  dropped waist, where trunk-weighted cloth cannot follow. Tuck the pelvis for high kicks (dancers
  do). Add a corrective shape per pose, keyed in the clip: the cloth pushed out of the legs and
  under-layers with a margin per layer. Spread the pushes with anchored smoothing (each Jacobi
  average divided by deg x (1 + 0.05)), so a 6 cm push at the hip fold fades within about three
  edges instead of moving the whole region.
- **Point-inside tests.** A plane test for "inside" misfires far from the surface (points 11 cm
  away read inside): require the offset to lie along the normal, and keep any exemption local (a
  crossing exemption read a triangle's corner off a leg triangle 9 cm away and spiked it 3 cm).
- **A fix is measured before it is shown.** Laying only the columns that face the thigh along it
  doubled the clipping: neighbours left hanging tore the cloth.
- **Standing poses** follow the concept: a dancer's rise added to fix "feet flat" went past it.

### 6.3 Garment pieces sewn together

Pieces built as separate meshes (a bodice and its skirt, a sleeve and its cuff, a collar and a
cloak) must be sewn, and the seam checked from every side a viewer can reach. A waist slot that
five rounds of level captures missed was plain to the user looking down from above in a freely
orbiting viewer. Clip and drape tests only test cloth against the body, so none of them saw it
either.
- **Build.** The seam row sits inside the outer piece's cloth, about 1 mm in and under its rolled
  edge, so the visible line is that edge. A skirt-wide rule that kept the skirt clear of the hips
  also moved its top row, and the skirt's top stood 4 to 14 mm outside the bodice's edge: an open
  slot onto what lay under it. Clearances ramp in below the seam; no rule moves the seam row.
- **Weights.** The sewn band takes the outer piece's weights (section 2).
- **Corrective fits.** Tie each seam point to the outer piece's nearest surface point, by its
  triangle's corners (a nearest-vertex tie still opened 7 mm on a coarse LOD), leave it out of the
  pushes, and taper the inner piece's margins to near zero at the seam.
- **Gate.** Measure each seam's opening in every frame of the exported file, at every LOD, and
  make the gate fail on the known-bad build first. Capture the seam from above and below as well
  as level.
- **What the overlap hid.** Closing a seam can expose an under-layer the old overlap covered: a
  waistband set up under a tight bodice showed through its last millimetres. Look at every layer
  near the seam close up, hiding each in turn to name a speck. End under-layers below a tight outer
  edge.
- **Skin trims follow.** Moving an under-layer changes what a "skin under clothes" trim counts as
  covered. With the shorts ending below the seam, the ring between them and the bodice read as
  bare skin, and 590 kept faces came through the bodice in hip-folding poses. Count the sewn band
  as cover, and compare the trim's face count with the previous build's. Tuck the game skin under
  a snug band along rays from the body's axis, trunk skin only: a selection by height also took the
  hands hanging beside the hips.
- **Fix the skin side at deep folds.** At a deep hip fold, belly and thigh overlap and nothing is
  outside both. Pushing the cloth out of the belly escalated to 7 cm and bulged the tight bodice in
  standing poses. Trim and tuck the skin instead.
