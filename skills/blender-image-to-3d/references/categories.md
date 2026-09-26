# Category reference

Read the section for the asset's category before Phase 0 of SKILL.md. Each section covers:
what to measure in the reference, how to construct it in bpy, which parts stay separate,
topology rules, UV and material policy, articulation and sockets, and what the acceptance
check looks for. The construction helpers named here live in `assets/build_template.py`.

Contents
1. Construction techniques (all categories)
2. Characters (bipeds)
3. Creatures (quadrupeds, winged, serpentine, multi-limbed)
4. Architecture (modular kits and hero buildings)
5. Vehicles (wheeled, tracked, aircraft, watercraft, hover)
6. Props and weapons
7. Environment pieces (rocks, foliage, terrain chunks)

## 1. Construction techniques

Code-driven modelling works when each part is built from a measured construction, not sculpted
free-hand. Pick the technique per part:

| Need | Technique | Helper |
| --- | --- | --- |
| Organic mass with joints (torso, limbs, neck, tail) | Skin modifier over a joint chain with radii, plus Subdivision | `skin_chain` |
| Fused organic base for sculpting | Join blockout pieces, voxel Remesh at 1/200 of height, then `push` sculpting | `join_meshes`, `remesh_voxel`, `push` |
| Hard-surface shell (car body, hull, fuselage, torso armour) | Loft cross sections read at stations from the side and top views | `loft` |
| Rotational parts (wheels, rims, columns, bolts, vases, barrels) | Lathe a 2D profile | `profile_spin` |
| Extruded profiles (arches, mouldings, beams, tracks, trims, rails) | Extrude a 2D outline | `profile_extrude` |
| Cables, horns, tails, pipes, tentacles, railings, roots | Curve with bevel depth and taper | `curve_tube` |
| Panels, plates, cloth, cladding, roofs | Grid or extracted faces plus Solidify | `grid`, `solidify` |
| Symmetry | Mirror modifier with clipping, applied only on the delivery copy | `mirror` |
| Cut-outs (windows, wheel wells, vents, panel lines) | Boolean with a hidden cutter, then Bevel for light-catching edges | `boolean`, `bevel` |
| Repetition (windows, rivets, treads, teeth, stairs) | Array, optionally along a curve | `array` |
| Tapering limbs and spires | Scale cross sections along an axis | `taper` |
| Low mesh over a sculpt | Base cage with joint loops, Shrinkwrap to HIGH, then Subdivision level 1 | `shrinkwrap` |
| Extra LODs | Duplicate, Decimate, then fix the silhouette by hand | `lod_copy` |

Measure everything from the brief. Every constant in a build script is a real dimension in
metres with a comment saying which reference view it came from. A guessed value gets the comment
`# inferred` so the manifest can list it.

Blockout budget: 15 to 60 primitives is normal for a character or vehicle. Fewer usually means
the silhouette is missing a mass; more usually means detail arrived before the silhouette passed.

## 2. Characters (bipeds)

Read the reference for: total height, head height (the proportion unit: realistic 7.5 to 8 heads,
heroic 8.5, stylised 3 to 6), shoulder width in heads, hip width, arm length (wrist at mid-thigh
when relaxed), leg length (crotch at roughly half height), stance width, posture line, costume
layers in overlap order, weapon and its grip.

Scale cues when no height is given: adult male 1.75 to 1.85 m, adult female 1.62 to 1.72 m,
a sword grip 0.1 m per hand, a doorway 2.1 m, a standard step 0.17 m.

Construct: `skin_chain` for pelvis, spine, chest, neck, head, both arms and legs with radii per
segment; separate spheres for skull and joints that need mass; boxes for hands and feet; jaw,
eyes, teeth, tongue, horns and hair volumes as separate objects. Costume as separate solidified
surfaces built outward in overlap order: body, inner garment, outer garment, belts and straps,
mantle or hood, cape and ornaments. Give garments real circumference and clearance for a full
stride; a skin-tight cone cannot be turned into a skirt later by simulation settings. Sleeves are
separate tubes with real arm openings; never bridge the armpit with accidental geometry.
Armour models the real overlap order: pauldron over the upper-arm plate, couter over the
vambrace, tassets over the thigh plates, each with visible edge thickness and bevels that catch
light.

Keep a complete body under the costume in the master; make coverage cuts only on the export copy
and test every equipment combination for holes.

Techniques for faces, smooth analytic forms, hands, the neck join, armour over clothing and strand hair:

- Face: calibrate a front and a profile blueprint of the head (a pixel scale, the pupil height, the
  facial midline, 30 to 50 landmarks in world space) and fit the head to them: the midline profile
  to the side silhouette, the outline to the front one, eyeballs placed from the pupils with the
  lids wrapping them, ears from the profile landmarks. Done when the overlays through calibrated
  reference cameras show landmark errors under about 1 mm. Three-quarter concept views are
  usually not metric (AI or painted views disagree with the blueprints by several percent); use
  them to judge likeness, never to measure. Texture the skin by projecting the de-lit blueprints
  through rest-pose UV maps (front, and profile mirrored for the far side), blended by which way
  the rest normal faces; strip painted brows and lashes and grow them as strands.
- Smooth analytic forms (SDF heads, bodies): tables of widths or depths need smoothing, or
  linear interpolation shows as shading bands; blend two descriptions of the same surface by
  position weight, not smooth union, which bulges where they coincide.
- Hands: build them in a local frame (palm normal, thumb side, length) and mirror the frame for
  the other hand; a rotated copy of one hand puts the thumb behind and reverses the finger order.
  Relaxed hands at the thighs have the thumb forward. Fingerless-glove cuts end at the fingertip,
  or curled fists open holes in the glove.
- Neck: the body's neck follows the head's neck just inside it (1 to 2 mm) so the textured head
  owns the visible skin and there is no step; give both the same skin texture mapping.
- Armour and straps over clothing: sample the garment surface on rays around a limb axis and
  offset along the ray, designing each outline in (angle around the limb, height) space. Plates
  then hug the leather whatever the limb shape, and outlines stay exact. Layer high collars and
  gorgets as body, undersuit up to the neckline, collar with a few mm of air around the neck,
  gorget resting on the shoulders over the collar base, then pauldrons. Check clearances with
  mesh overlap tests, not by eye. Check the layer order at every garment boundary from behind as
  well as from the front (trousers tucked into boot shafts, greaves over the shafts, straps over
  the greaves): a trouser leg drawn over a greave's edge made the leg armour read as ill-fitting
  from behind.
- Strand hair: give each class of hair its own collider. The envelope that keeps long hair
  outside the pauldrons is far too fat beside the neck and turns short face-framing locks into a
  sideways tuft. Shading: a Principled Hair BSDF fitted by colour models a dense hair volume, so
  its transmission makes a sparse backlit lock read blonde; use it as a highlight layer (about 15
  percent, transmission weakened) over a Principled base, and check a thin lock against a dark
  background, not only the dense mass.

Realistic anatomy, for the parts people look at closely. A head, hand or boot built from
primitives reads as low-poly at any triangle count, and folded-over ears read as injury. When
realism matters, start from an anatomical base mesh and fit it to the reference. Blender Studio's
Human Base Meshes bundle is CC0: a realistic head with separate sclera and iris, hands and feet.
Record its source and licence in `ref/` and in the manifest.

- **Head fit.** Fit in stages, each measured against the blueprint:
  1. A similarity transform from the pupils and the cornea plane.
  2. A vertical remap through the landmarks (brow, nose tip, subnasal point, lips, chin,
     menton), monotone cubic, so the features land at their heights.
  3. Depth, piecewise about the ear line: the face plane moves to the profile, the ear line stays,
     and the back of the skull stretches at most 15 percent. One depth scale for the whole head
     stretched the jaw about 30 percent.
  4. Width per height, to the front outline minus the hair thickness.
  5. A small radial-basis warp (a few cm radius) to put the eyes, nose tip and lips on the paint.

  Aim for a profile IoU of about 0.9 before hair. Keep the base mesh's ears and eyelids. The
  eyeballs are real spheres (sclera, iris) on eye bones. Hair and beard volume is a displacement
  masked by the painted projection's hair colour; scale the mask smoothing with the mesh density,
  or dense levels groove. Project the painted back view on back-facing normals, and sample the
  crown from a clean top-down hair tile, not from the side view's edge.
- **Painted features the mesh already has.** A painting projected onto a head brings along what
  the geometry models separately: an ear painted on the side of the head shows as a ghost ear
  behind the real one, and nostrils painted on the side of the nose show as dark spots. Paint them
  out of the projection texture before baking. Fill each masked area from donor regions of the
  right material (hair above and neck skin below for an ear, the nose's own skin for nostril
  marks), feather the fill inward over about 10 px, and blend the donors across the gap. A
  harmonic fill alone pulls in the background or the neighbouring feature's colour. Review the
  head from the side and at three-quarters, not only from the front.
- **Hands and gloves.** Map the base hand to the measured wrist and hand length in a local frame,
  mirroring the frame for the left hand. Read the finger joint chain from the mesh and put the
  finger bones on it. Put plates (the back of a gauntlet, the knuckle guard) a few mm off the glove,
  following its envelope. Keep the rest pose open: grips come from the pose (rigging-animation.md
  section 4).
- **Feet and boots.** Build the boot on a real last from the base foot: sole and heel block, welt,
  toe spring, toe cap and instep strap, with a length of about 15 percent of height (a 0.29 m boot
  for a 1.88 m man). A painted turnaround boot 0.39 m long built as drawn reads as a brick slab.
  Build the real one and record the silhouette deviation.
- **Joint armour.** Knee cops (poleyns) and couters are shaped cops:
  - an outline designed in (angle around the limb, height) space, with a raised bulge;
  - a rolled rim tube;
  - a side wing;
  - an upper and a lower lame.

  They are not hemispheres: domes read as balls stuck on a flat knee. They ride helper bones that
  turn half the joint's bend (rigging-animation.md section 1).
- **Layered plates.** Build a stack of plates (a pauldron's cap over its lames, lames over a
  sleeve, tassets) inside out: the lowest plate fitted over the padding, each plate above fitted
  over the ones already under it, the cover plate last. Fitting the cover to the padding first
  leaves no room beneath it (two 4.5 mm lames need about 12 mm): the lames get squeezed into the
  padding, which then shows through their lower edges. Shape each lame to the layer under it but
  keep it a straight band down the limb (one straight radius profile per column), and seat edge
  trims and rivets on the fitted plate by ray from its axis, not on the designed surface, or they
  float and cut through. Finish with a face-level overlap settle (`cloth_tools.settle_faces`).
- **Cloth at the neck.** Stacked scarf tubes read as fake. Drape cowls, scarves and hoods with
  Blender's cloth solver: a pleated tube pinned under the jaw falls onto collision copies of the
  neck, gorget, pauldrons and cloak (the same builders at low detail). Pin the frame rate so the
  settle is reproducible, and keep the settled shape as the rest mesh. Then finish it
  (`assets/cloth_tools.py`):
  - Taubin-smooth it. The solver's small crumples read as crushed paper on the delivery mesh; a
    plain Laplacian shrinks the cowl onto the neck.
  - Put the clearances back after smoothing, each vertex along the nearest surface's own normal
    so it keeps its side. Pushing everything "away from the body" drags cloth the solver tucked
    inside a gorget's collar through the plate.
  - Give steel a larger gap than soft layers, in the solver's collision thickness and in the
    clearance pass (about 9 mm against 4 mm for a cowl with 18 mm faces). A face between two
    clear vertices still cuts across a plate's rim when the gap is smaller than its sag over the
    rim, and decimating the cloth for LOD0 makes it worse.
  - Follow the reference's overlap order. The concept's collar lies over the cloak, whose top
    rises into it: roll the collar out over the cloak where the solver left it under, eased over
    the faces. A cloak lowered away from the collar reads as "floating, not connected", and a
    cloak top cut straight across below the collar shows a band of armour between them: raise
    the cloak along the shoulder line to the base of the neck under the collar.
  - A cloak whose top gathers into the collar is one garment rolled over at the neck, not a hood
    lying on the back. A collar given a hood's room and drop down the back settled as a bib with its
    hem lying on the cloak, and a review read "two separate pieces of cloth: one for the hood and
    one for the back". Instead:
    - give the collar less fabric at the back (about two thirds of the sides' and front's) so it
      settles as a roll at the nape;
    - run the cloak's top edge up under the roll everywhere; its corners beside the collar looked
      "cut or sliced";
    - tuck the collar's hem a few mm into the cloak's thickness, eased over its last few rows, so the
      folds run into it. Laid 1.5 mm off the cloak, its thin, decimated edge still showed as a line.
      Keep the passes after the tuck (clearances, the face settle) from pushing it back out.
  - Simulating the collar and the cloak's top as one sheet, pinned at the jaw and on the cloak, did
    not work: the collar's extra fabric fell into the sheet below and dragged it through the
    backplate. Keep two pieces and lay them together.
  - A real hood lying on the back falls as one broad, rounded drape. Give the solver's start shape its
    extra room and drop evenly across the back (a plateau over about 60 degrees either side), not
    peaked at the centre, which falls as a tongue.
  - A closed collar's sides come round to the front of the neck over an open cloak and must pass
    over the cloak's top edge, not through it (`cloth_tools.lift_over_edge`, after smoothing).
  - Simulate once. Build the LODs from the finished high-detail cloth, and give ornaments seated on
    it the high-detail placement. A second solver run in a later phase settles a few mm
    differently: a brooch seated on it moved 13 mm, and the bake projected cloth onto it.
  - Do not clean up leftover intersections by pushing single vertices off whatever they touch in
    a loop. Where the cloth is caught between two obstacles it oscillates and grows spikes.
  - Review it with the cloth in its own colour: a triangle-pair count cannot tell a hidden tuck
    from steel showing through. Look with stowed gear taken off as well: gear on the back, the
    viewer's default state, hid the cloak's top that the reviewer saw.
- **Cloaks and pauldrons.** Lift a cloak over the armour by ray casts and check it with an overlap
  test: armour poking through a cape is the first thing seen from behind. When the reference hangs
  it over one pauldron and under the other, lift it over the torso armour and the near pauldron
  only. Then tuck it under the far pauldron's cap, lames and neck guard (a ray from inside the
  cloth meeting one of its plates within the cloth's thickness plus the clearance), testing the
  tuck where the lift left the cloth. A tuck tested on the unlifted surface misses the cloth that
  the lift's easing pushed into the plate.
- **Ornaments on cloth.** A fastener (brooch, clasp) presses the cloth it pins against what lies
  under it, so it touches both. Seated on the highest fold under it, a brooch stood 25 mm off the
  breastplate. Slid clear of the gorget ring above it, it stood 8 mm off. Both read as floating.
  - Draw the cloth onto the plate or garment at the pin with a smooth falloff round the pin point,
    so the brooch visibly holds both.
  - Lay the cloth flat under the footprint, a few mm off a plate and easing out beyond it. Do this
    after any pass that pushes cloth off steel.
  - Square the fastener to the plane of the surface under its whole footprint, not to the normal at
    one point: a chest curves under a 5 cm disc.
  - Rest it on the highest support under each point: cloth where the drape reaches, plate where it
    does not. Let the wool give 1-2 mm and press the cloth under the disc.
  - Move the pin rather than sliding the ornament out to clear a neighbouring rim.
  - Put it where the cloth is: a disc half off the cowl's hem reads as floating.
  - Judge the gap on a section through it. Against a curving plate a side view's silhouette hides
    the gap or invents one.
- **Belts and hanging gear.** Build each piece so it is held:
  - buckles as open frames with a prong lying on the strap;
  - pouches hung from the belt by loops, with flaps and studs;
  - a scabbard hung by straps or hangers from the belt. A block "frog" reads as a brown rectangle
    holding a sword.

  The sheathed weapon is checked the way the engine shows it: the weapon asset attached to the
  hip socket, at the bind pose.
  - Put the hilt on the blade's centre line at the guard, so the grip rises from the middle of the
    scabbard's mouth. A single-edged blade with the grip on its spine line looks off centre.
  - Start the scabbard just below the guard and its block, which rest on the throat. The guard
    and block inside the scabbard's mouth read as the sword clipping through it.
  - Close the mouth with a slotted throat plate the blade passes through. A capped mouth cuts
    the blade, and an open one shows a hole.
  - Rivet each hanger flat on the belt's face and run it down over the belt's edge. A loop round
    the belt passes through tassets hung behind it.
  - Land each hanger on the side of its fitting that faces the belt, tangent to a leather loop
    round the fitting. A curved blade's spine can face away from the belt, and a strap to the spine
    crosses the scabbard and the blade inside it.

  At rest the sheathed weapon and the whole scabbard assembly intersect nothing.

  Check contact with `validate.py --attachments`. For hanging gear, make the declared holder the
  exact part that carries it. A pouch that touches the skirt behind it is still floating off its
  belt.

Realism checklist for the close-up review (SKILL.md gate protocol step 4):
- **Face:** proportions against the blueprint; eyes with sclera and iris set behind the lids; nose,
  lips and chin from the fit; no faceting at the silhouette.
- **Ears:** helix, antihelix and lobe; not a folded blob.
- **Hair and beard:** volume at the hairline and jaw; no painted-flat scalp, bald band or combed
  streaks at the crown.
- **Hands:** finger lengths and joints; knuckles; glove thickness. A grip closes round the handle
  with every phalanx on it, not only the fingertips, and the thumb over the fingers.
- **Feet:** length about 15 percent of height; a last shape; sole, heel and toe spring; the
  foot on the ground.
- **Knees and elbows:** shaped cops, no domes; nothing clipping at full bend.
- **Neck and cape:** the cloth hangs in folds; no armour through it at rest or in poses.
- **Attachments:** nothing hovering; every strap, buckle, pouch, handle and hanger touches its
  holder.
- **Weapons:** in the hand in every pose; clear of the body, scabbard and ground; stowed gear
  resting on what carries it; sheathed, the hilt centred on the scabbard's mouth with the guard
  resting on the throat.

Topology (LOW): continuous loops around eyes, mouth, shoulders, elbows, wrists, hips, knees and
ankles; three or more segments on each side of a bending joint; no long thin triangles or high
valence poles on a crease; clavicle geometry that lets an arm rise without collapsing the chest;
individual finger joint sections when hands grip or draw; a jaw with a sensible pivot and a
lip-to-cheek transition. Quads in the editable source, triangulated delivery, and the intended
triangulation locked before baking.

UV and material: unique texture space for the face and focal costume areas, shared trims for
repeated straps, buckles and chain; consistent texel density across the body; roles such as
skin, hair, woven cloth, worn leather, corroded metal each with a believable roughness range.

Articulation: humanoid deformation skeleton (see rigging-animation.md), sockets for both hands,
weapon tip, back mount, head, chest and feet.

Acceptance specifics:
- Role and silhouette readable at gameplay size in greyscale.
- Feet contact the floor.
- Hands grip their weapon: fingers closed on the handle's mesh, the thumb over them.
- Shoulders, elbows, hips and knees deform cleanly on the extreme-pose sheet.
- No holes between costume pieces in any pose.
- The realism checklist passes on the close-ups.

## 3. Creatures

Read the reference for: body length and shoulder height, head length as the proportion unit,
limb count and gait type, joint placement (scapula, shoulder, elbow, carpus; hip, stifle, hock),
neck length and range, tail length and taper, wing span and fold, jaw gape, membranes, spines,
plates, scales and where they stop, the action it must perform (bite, lunge, breath, pounce).

Scale cues: a large dog 0.6 m at the shoulder, a horse 1.6 m, a bear 1.0 m on all fours; wing
span roughly 2 to 2.5 times body length for flight-capable designs.

Construct: `skin_chain` for spine (nose to tail tip) and each limb with the correct joint count
and positions. A quadruped's apparent backward knee is the hock; the stifle sits higher near the
body, and the scapula floats on the ribcage. Ribcage and pelvis as separate ellipsoids so the
shoulder and hip motion has masses to slide over. Wings: leading-edge chain (humerus, radius,
metacarpal, digits) plus membranes built as grids bridged between the digit chains and the body,
with enough resolution to fold without reversing their surface. Tails, horns, tendrils and
tongues with `curve_tube`. Jaw, tongue, teeth, eyes, claws and membranes as separate objects
where they need independent shading, deformation or articulation.

Topology: loops at every joint listed above, extra loops where the neck curves and the tail arcs,
membrane grids aligned to fold lines, a jaw loop that can open to the reference gape. Test neck
curvature, mouth opening, wing fold and tail arc before accepting topology.

UV and material: skin, scales, plates, membrane and teeth as distinct roles; membranes may need
two-sided shading and translucency tested against cost; symmetry mirroring is fine for hide,
unique space for the head.

Articulation: quadruped or winged rig family, sockets for mouth (breath, bite origin), eyes,
feet, saddle or rider point, and effect points on chest or back. Mouth socket forward must agree
with the attack direction.

Acceptance specifics: gait-critical joints in the right place, wings fold and unfold without
self-intersection, neck and jaw reach the reference action pose, silhouette readable at distance.

## 4. Architecture

Read the reference for: storey height, door and window openings and their rhythm, wall thickness,
roof pitch and overhang, plinth and cornice lines, repeat modules, ornament families, materials by
surface (stone, plaster, timber, tile, metal), damage and weathering pattern, and what is a
separate object (doors, shutters, gates, banners).

Scale cues: door 0.9 x 2.1 m, storey 3.0 to 3.6 m (grander 4 to 5 m), step 0.17 m rise, brick
course 0.075 m, window sill 0.9 m, railing 1.0 m, medieval wall 0.6 to 1.2 m thick.

Construct as a kit on the gameplay grid (`--cell` from init_master): floor tiles, wall segments
(plain, window, door, corner, end cap), pillars, arches (`profile_extrude` or `profile_spin` for
half domes), roof segments (extruded pitch profile), trims and cornices (`profile_extrude`, or
a curve with a profile bevel object), stairs (`array`), railings (`curve_tube` and `array`). Every
piece's origin sits at its grid corner on the floor so pieces snap; wall thickness and floor
thickness are constants shared by every piece. Hero buildings are assembled from the kit plus a
few unique pieces, never sculpted as one blob.

Parts: doors, gates and shutters are separate objects with the pivot at the hinge line. Colliders
are simple prisms per piece, independent from ornament density. Two or three silhouette variants
per wall type (damaged, vined, plain) beat unique geometry everywhere.

Topology: clean quads with bevels only where light catches, controlled reduction is fine on
rubble and ornament; planar faces stay planar for snapping seams; no doubled faces where pieces
overlap at seams.

UV and material: tileable materials for large surfaces (stone, plaster, timber) with a trim sheet
for edges, cornices, mouldings and door frames; unique decals for signs and damage; small props
share atlases. Never a unique large texture per stone. Texel density constant across the kit.
Set the tileable UV scale so the brick course or plank width matches the metre scale.

Articulation: hinge pivots for doors and gates, sockets for torches, banners, signs and effect
points. Interactables (chest, gate, portal) get named open/close states.

Acceptance specifics: a 2 x 2 assembly of the kit shows no seams, gaps or z-fighting; door
clearance passes the REF_door proxy; the collider set blocks the player where the visual does;
the tileable scale reads right next to the REF_ruler.

## 5. Vehicles

Read the reference for: overall length, width, height, wheelbase and track (or hull length and
beam, span and fuselage length), wheel diameter, ground clearance, body sections and panel gaps,
glazing, doors and hatches, turrets and weapons, lights, exhausts, intakes, suspension travel,
and the interior visible through glass or open cockpits.

Scale cues: car wheel 0.6 to 0.75 m, truck wheel 1.0 m, sedan 4.5 m long, 1.8 m wide, 1.45 m
tall; door handle 0.95 m from ground; tank 6 to 8 m long, 3.5 m wide; light aircraft 7 to 9 m
span; seat height 0.45 m above the floor inside.

Construct: body shell with `loft` from cross sections measured at 6 to 12 stations along the
length (height from the side view, width from the top view, corner radii from the front view),
then Subdivision or Bevel; wheels with `profile_spin` (tyre, rim, hub) as separate objects with
their origin at the axle centre; wheel wells and windows via `boolean`; doors, hatches, hood, trunk
and turret as separate objects cut from the shell with panel gaps and inner thickness; tracks as
an `array` of one link along a curve; suspension arms and axles as simple cylinders; interior only
to the depth that is visible. Front of the vehicle faces -Y like everything else.

Parts: separate objects for anything that moves (wheels, steering knuckles, doors, hatches,
turret, barrel, props, rotors, flaps, rudder) and for glass. Lights and exhausts are separate for
material reasons. Vehicle origin at the ground centre under the wheelbase midpoint.

Topology: even quad flow along body lines, supporting loops at panel edges, bevelled edges with
thickness at every exposed edge; wheels around 32 to 48 segments at LOD0; no ngons on curved
panels.

UV and material: painted metal, chrome, rubber, glass, plastic, fabric and light emissive as
roles; unique space for the body, shared trims and atlases for wheels, interior and hardware;
decals for numbers and insignia; roughness variation from wear and dust, not noise.

Articulation: a rig or empty hierarchy with real pivots: wheels spin about their axle and steer
about the kingpin, doors about the hinge line, turret about its ring, barrel about its trunnion.
Sockets for driver seat, passenger seats, weapon mounts, exhaust and light effects, tow points,
camera mounts. Colliders: a body hull plus wheel cylinders, or a convex set.

Acceptance specifics: wheels sit on the ground with the reference clearance, wheelbase and track
match the reference within 2 percent, doors open without clipping, the silhouette reads from the
game camera, glass does not hide the driver when it should not.

## 6. Props and weapons

Read the reference for: overall dimensions, grip or contact point, moving parts and hinges,
material roles, wear, what is decorative versus functional.

Scale cues: hand grip diameter 0.03 to 0.045 m, sword blade 0.7 to 0.9 m, rifle 1.0 m, pistol
0.2 m, barrel 0.9 m tall, crate 0.5 to 1.0 m, torch 0.5 m, chest 0.8 x 0.5 x 0.5 m.

Construct: primitives plus `bevel` for hard surface, `profile_spin` for anything round (bottle,
barrel, bolt head, pommel), `profile_extrude` for blades and beams, `curve_tube` for straps,
chains and cables, `boolean` for cut-outs. Weapon origin at the grip centre, local +Y toward the
tip or muzzle, +Z toward the edge or sights, so it matches the hand socket convention.

Parts: separate objects at every hinge (lid, gate, trigger, bolt), with the origin at the pivot.
Strings on bows and cables on winches are separate so they can flex.

Topology: light and clean; small props under a few hundred triangles, hero weapons a few thousand
with real edge bevels; no hidden interior geometry.

UV and material: shared atlases for small props of one family, unique space for hero weapons,
trims for straps and metal edges.

Articulation: hinge empties or bones, `SOCKET_grip` and `SOCKET_tip` (or muzzle) with the
convention above; the socket must be tested with the actual hand and animation, not an empty at
the hand origin.

Shields:
- **Centre grip.** A round shield with a boss has a hand hole under the boss and the handle
  riveted across it on the back. The hand grips it as a punch into the boss: the fist round the
  handle, the knuckles into the boss, so the socket's face direction is the hand's length square
  to the handle (rigging-animation.md section 4). A palm facing the board is wrong, and so is a
  handle floating off the board.
- **The boss.** It has to hold the closed fist. The knuckles of a fist round a 30 mm bar reach
  about 65 mm ahead of its axis, so a boss 40 mm proud of the face pushed the fingers straight
  through it. Keep its inner surface about 5 mm beyond the fist's measured envelope (about 55 mm
  proud on a 0.75 m shield), and model it as a shell over the hand hole.
- **Strapped shields.** They carry an arm strap (enarmes) and a grip near the rim instead.
- **The dome.** A domed board curls its rim back towards the bearer. Keep the dome shallow (4 to 6
  cm on a 0.75 m shield), so the forearm lying behind a centre grip clears the rim.
- **Painted designs.** A design projected by position through a thin board paints its back too.
  Mask it by the face normal, and give the back bare wood or leather.

Acceptance specifics:
- The grip fits a hand of the character it belongs to, and the handle touches what holds it.
- Hinge motion passes through its real range without clipping.
- The silhouette survives at gameplay distance.

## 7. Environment pieces

Read the reference for: overall size, silhouette layers (mass, secondary forms, surface break-up),
tiling or instancing intent, contact with the ground, material roles.

Construct: rocks from a subdivided box or sphere with `push` displacement and voxel Remesh, then
Decimate for LODs; trees with `curve_tube` trunks and branches plus card or shell canopies; terrain
chunks as displaced grids; cliffs as lofted profiles. Keep the bottom flat or buried so placement
does not float.

Parts: single objects where possible; separate canopies for wind; separate collision proxies.

Topology: controlled reduction is fine here (rubble, rocks); align the pivot to the ground contact
and keep the silhouette at each LOD.

UV and material: tileable rock, bark and soil with a triplanar or box projection and a detail
normal; leaf cards with opaque cut-outs tested before any true transparency.

Acceptance specifics: reads as its material at distance, no floating on flat ground, LODs preserve
the outline, instances tile without visible repetition at gameplay density.
