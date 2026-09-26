# Rigging, sockets, animation and secondary motion

Read this before Phase 6 (articulation) and again before Phases 7 and 8. Applies to any asset that
moves: characters and creatures fully, vehicles and hinged props for the pivot and socket rules.

Contents
1. Skeleton families and hierarchy
2. Binding and weights
3. Extreme-pose sheet
4. Sockets and functional parts
5. Animation library and event contract
6. Secondary motion (cloth, chains, wings, antennae)

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
builds, and cloth, wing, tail or antenna chains supplement this. Joint armour gets a helper bone
at the elbow and knee:
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
- Write that note into the manifest. Quadruped: spine chain from
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

Rules that kept a one-piece glove, its plates and hanging gear clean:
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

## 3. Extreme-pose sheet

Before accepting a rig, render (review_render.py with `--action` and `--frame`) a sheet of the
worst poses the asset will actually hit and inspect every separate part together:

Bipeds: arms overhead, forward reach, crossed-arm cast, deep elbow and knee bend, hip flexion,
full stride, wide stance, bow draw or two-handed grip, torso twist, crouch, death pose.
Quadrupeds: full stride at gallop, pounce crouch, rear, head turn, bite gape, tail curl.
Winged: full fold, full spread, downstroke, banked turn.
Vehicles: full steering lock, full suspension compression and rebound, doors and hatches at max,
turret and barrel at limits.
Props: hinge at both limits.

The sheet also holds:
- the stance the concept shows (an idle holding what the concept holds);
- every weapon state the game shows, in hand and stowed. A test file can key a stowed item
  between two sockets with two Copy Transforms constraints, the second's influence keyed per
  frame with constant interpolation.

Bend hinges (elbows, knees, fingers) about the bone's own axis, a local rotation. A world-axis
turn applied after the parent has turned twists the joint.

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
- the weapon stays in the hand, clear of the body.

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

Hand sockets and grips (`assets/grasp_tools.py`):
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

Gear stowed over a garment holds the cloth under it. A shield, pack or quiver strapped over a
cloak pins the cloak's top segments, so a pose that swings the cape back off the legs must not
carry it through the item. `grasp_tools.settle_chain` turns each chain bone forward until its
vertices clear the item, and passes the turn it gave up to the bone below. The cloth then folds
under the item's edge and still clears the legs. Test against everything that stands off the
item's back (rims, buckles, straps), not only its board or body.

A plate the arm raises lifts the cloth lying over it: a rigid pauldron rose through the cloak
when the sword arm swung out. Test the cloth against the posed plates once the arm is final (after
any aim search that turns the humerus). Turn the chain's top bone back until its cloth clears, then
hang the bones below again (`grasp_tools.settle_chain` with a lifting axis and step).

A bone chain cannot keep a cloak that hangs over the shoulders off an arm swung back into it, and
with gear stowed over the cloak there is often nowhere for the chain to go. List those contacts
for the runtime cloth or spring solver's arm capsules instead of bending the chain through
something else.

Draped garments at rest come from the cloth solver, not modelled tubes:
- a pleated start shape above the collision copies, pinned where the garment is held;
- a fixed frame rate and frame count;
- the settled mesh kept as the rest shape.

Cloth that starts inside a collider stays inside it.
