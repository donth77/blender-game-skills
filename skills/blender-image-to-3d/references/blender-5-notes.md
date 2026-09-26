# Blender 5.x notes

API changes and runtime behaviour met while building assets with this skill on Blender 5.2, plus
review and look-development lessons that are easy to lose between sessions. Read this when a
script fails on a 5.x API, before long renders or bakes, and when the review renders and the
user's viewport disagree.

## 1. API changes that break older bpy code

- Geometry Nodes modifier inputs are no longer ID properties: `mod["Socket_2"] = v` raises
  "id properties not supported". Set `getattr(mod.properties.inputs, identifier).value = v`, where
  `identifier` comes from the node group's interface socket (`socket.identifier`). Keep a fallback
  to `mod[identifier]` for 4.x.
- Actions are layered: `action.fcurves` is gone. Walk `action.layers[*].strips[*].channelbags[*].fcurves`
  (or keyframe through `keyframe_insert` and let Blender create the channelbag). For stepped keys
  without touching F-curves, set `bpy.context.preferences.edit.keyframe_new_interpolation_type =
  "CONSTANT"` around the `keyframe_insert` call and restore it after.
- `BVHTree.FromObject` builds in the object's local space; transform queries by
  `ob.matrix_world.inverted()`, or build with `FromPolygons` from world-space vertices.
- Materials and worlds always use nodes; `use_nodes` is deprecated. Guard it with
  `bpy.app.version < (5, 0, 0)`.
- Vertex group names live on the mesh data. A copied mesh already carries the names, so creating
  the same group again yields `Group.001`; check `ob.vertex_groups.get(name)` first, and merge any
  `.001` groups before export.
- EEVEE's engine identifier differs between versions (`BLENDER_EEVEE_NEXT` in the 4.2-era
  releases, `BLENDER_EEVEE` in 5.x, where the other is rejected); try both inside
  `try/except TypeError`.
- EEVEE does not support the Principled Hair BSDF. Give hair (and anything else EEVEE cannot shade)
  two Material Output nodes, one with target EEVEE and one with target CYCLES. Cycles renders the
  CYCLES-target output even when the EEVEE one is active; anything that rewires an output for
  baking must pick the same node (`scripts/bake_maps.py` does).
- Look nodes up by type (`n.type == "BSDF_PRINCIPLED"`, `"OUTPUT_MATERIAL"`, `"BACKGROUND"`), never by
  display name: names are translated in non-English UIs.
- Command-line values that start with a minus sign need the `--arg=-0.28,0,1` form, or argparse
  reads them as a new option.

## 2. Runtime and performance

- An object in a collection excluded from the view layer (a working collection hidden between
  phases) is not in the depsgraph: `evaluated_get` returns it without its modifiers, with no
  error. Every BVH, fit or clearance test built from it silently loses the solidify thickness,
  the bevel and any decimation: a cloak built there measured 8 mm thinner than the delivered one,
  and a collar cleared against it cut the real cloak's outer face. Link such objects to the scene
  collection while they are evaluated (`build_template.in_view_layer`), or un-exclude the
  collection for the build.

- Cycles on Apple Silicon: enable only the METAL device. Adding the CPU as a second device made
  frames about twice as slow (M-series Pro, 1080p, 48 to 64 samples with OpenImageDenoise ran at
  12 to 20 s per frame GPU-only).
- `render.use_persistent_data = True` speeds up animations where only the camera or a few objects
  move.
- Selected-to-active bakes spend most of their time syncing the scene: hide every renderable that
  is neither a source nor the target (except for AO, where neighbours should occlude). Strand hair
  with tens of thousands of curves is the usual culprit.
- Transparent shells (corneas, visors, glass) catch bake rays in front of what they cover; leave
  them out of the sources (`bake_maps.py --exclude-sources`) and give the delivery copy its own
  simple transparent material.
- A long headless render should write numbered frames and skip frames that already exist, so it
  can be stopped, fixed and resumed; encode with ffmpeg at the end.
- `blender --background --python x.py` exits 0 even when the script raises. Pass
  `--python-exit-code 1` in every chained command, or a failed phase lets the next one run on
  stale data.
- Cycles on Metal (Blender 5.1) intermittently aborted at the start of a bake with
  "NSURL initFileURLWithPath: nil string parameter", thrown from the background kernel
  specialisation threads (MetalKernelPipeline::compile). Two long bake chains died this way at
  different steps. Set the Cycles preference `kernel_optimization_level = "OFF"` for bakes
  (`bake_maps.py --device GPU` does), and write multi-step bake chains so they resume at a named
  step.
- Pose solvers that only read bones (grip searches, aim searches, settle passes) should switch the
  Armature modifiers off (`show_viewport = False`) while they search. Otherwise every depsgraph
  update re-skins every mesh, which dominates a search over hundreds of candidates. Switch them
  back on before saving, rendering or measuring overlaps. Grip searches over finger angles need
  no updates at all: compose the chain's pose matrices from the rest matrices (forward
  kinematics).
- The glTF exporter samples constraint results into exported actions. A helper bone driven by
  Copy Rotation arrives in three.js with its half turn baked into the pose action; the rest pose
  carries no constraint, so write the runtime rule into the manifest. A glTF joint's local
  quaternion includes its rest rotation: take the fraction of the target's change from rest
  (rigging-animation.md section 1), not of its raw quaternion.
- The cloth solver is not reproducible between runs. Two builds of the same code settled a cowl
  up to 13 mm apart (median under 1 mm), and later passes built on it still varied when the settle
  was cached and reused. Every rebuild re-rolls the fine folds, so re-measure what sits on the
  cloth (fasteners, straps) after each one, and do not promise identical folds.

## 3. Review and look-development lessons

- The viewport is what the user sees. An object hidden only with `hide_render` (a body mannequin
  under the costume, a helper) still shows in the user's viewport and pokes through there; hide
  it for both viewport and render, and review close-ups with everything the viewport shows.
- Match painted concept colours by numbers: sample the median sRGB of the same world-space box
  in the reference and in a render under the review lights, and adjust albedo until they agree.
  Grey-looking leather was specular sheen and edge-wear masks firing over whole thin straps, not
  the base colour. The same mask baked a 4 mm leather cuff solid light tan, which read as bare skin
  between a vambrace and a glove. Give thin shells a material whose wear ignores small curvature
  (the glove's), and check the baked maps per part: the cuff also took metallic from the steel
  plate under it, within the bake's ray distance.
- Painted concept metal usually reads brown-lit: give glossy rays their own warm studio (Light
  Path "Is Glossy Ray" in the world shader) while diffuse rays keep a dark environment.
- The Standard view transform keeps saturated skin and hair close to a painted sheet; AgX washes
  them out. Pick one for the look and keep it for every comparison.
- When a colour looks wrong, test hypotheses one at a time on a small render border (lighting,
  reflections, clipping, the shader itself) and give each object a flat emission debug colour to
  find which object is at fault before changing materials.
