"""
CLOTH TOOLS
Cloth at the neck (cowls, scarves, hoods, a cloak's top) designed over the body, finishing passes for
cloth from Blender's cloth solver, and placing rigid ornaments pinned on cloth. Copy next to the build
scripts and import it (it only needs numpy, bpy and mathutils).

Designed cloth (clean fabric; the same every build):

  import cloth_tools as C
  el = np.radians(np.arange(-45.0, 82.0, 0.5))                  # down the chest and back .. up the neck
  M = C.support_envelope(neck_point, [(soft, 0.004), (steel, 0.009), (cloak, 0.004)], 128, el, usable)
  E = C.membrane(M, elevations=el, column=True)                 # smooth over rims, edges and folds
  Q, N = C.envelope_surface(neck_point, E, el)                   # points, and directions to push out
  # per column: points down Q at even arc lengths from the collar's top to its width, each moved
  # along N by the collar's height there (rolls, folds); the hem at the sides and back brought down
  # onto a tighter membrane, C.membrane(M, passes=25, ...); then keep_clear and the checks below

Solver cloth:

  V = C.taubin(V, F, fixed=range(ring * 2))                 # soft folds, the pinned rows kept
  V = C.keep_clear(V, [(soft_tree, 0.004), (steel_tree, 0.009), (cloak_tree, 0.004)])
  V = C.roll_over(V, F, cloak_tree, axis_xy=(0.0, 0.02))     # the collar over the cloak's top
  V = C.taubin(V, F, iters=4, fixed=range(ring * 2))
  V = C.keep_clear(V, [...], rounds=3)
  for _ in range(3):                                          # the collar's sides over the cloak's
      V = C.lift_over_edge(V, F, cloak_tree, cloak_top_xz)    # top edge, not through it
      V = C.keep_clear(V, [...])

Both:

  M = C.slide_clear(brooch_verts, brooch_polys, M, normal, armour_tree)   # a pinned ornament
  C.settle_faces(cowl_object, [armour_tree, cloak_tree], away)            # delivered faces, last

What each pass does and why:
- support_envelope, membrane, envelope_surface: a solver's drape of a bunched cowl read as "a crumpled
  mess" however it was smoothed or stiffened, and moved 1-3 cm between runs. Design it instead on a
  membrane: along rays from a point in the neck column, the outermost support plus its clearance
  (measured straight off every surface, not along the ray: oblique plates and rims beside the ray
  keep theirs), blurred and lifted back so it never dips under the support. Reject hits the cloth
  does not lie on with `usable` (the head above the jaw line; a cap closing a garment's neck hole),
  and continue the neck up as a column above its last hit, or the rows run up the face.
- taubin: the solver leaves small crumples that read as crushed paper on a delivery mesh. Taubin
  smoothing (a Laplacian step in, then a slightly larger one out) removes them without shrinking
  the cloth; a plain Laplacian pulls a cowl tight onto the neck.
- keep_clear: put clearances back after any pass that moves vertices. A vertex is inside a surface
  only when it lies straight behind the nearest face and shallow; it then moves out along the face's
  normal and keeps its side (cloth tucked inside a gorget's collar stays inside). Beside a plate's
  rim or a thin shell's edge the nearest face can face sideways or down: read as a signed distance
  along its normal, points 2-3 cm outside came out inside and were shoved through the steel and a
  cloak's corner, as pinches in the cloth. Never push everything "away from the body": it drags
  tucked cloth through the plate.
- Gaps by material: give steel a larger gap than soft layers (about 9 mm against 4 mm for a cowl
  with 18 mm faces). A face between two vertices that clear a plate's rim still cuts across the rim
  when the gap is smaller than the face's sag over it. Decimating the cloth for LOD0 makes it worse.
- roll_over: the reference decides the overlap order. A collar that lies over the cloak (the
  cloak rising into it) is rolled out over the cloak's top where the solver left it underneath,
  the move eased over the faces so the cloth rolls over the edge instead of folding across it.
- lift_over_edge: a closed collar over an open garment hanging behind it (a cloak): its sides come
  round to the front of the neck, and below the cloak's top edge that path runs through the cloak.
  Lift the cloth of every face that crosses the cloak, on its body side, above the cloak's top
  edge, eased over the collar. Lowering the cloak's top under them instead turns the cloak into a
  bib and leaves the collar nothing to rest on.
- settle_faces: the last word, for plates as well as cloth. Clearances hold at the vertices, but a
  face between two of them can still cut a curved neighbour. Intersect the object's evaluated
  surface (thickness and bevel included) with the neighbours and move the crossing faces' own
  corner vertices a small step along a clearing direction until nothing crosses. Map faces to
  vertices by their corners: a search radius smaller than a coarse LOD's faces finds no vertex and
  the pass silently does nothing. Apply a LOD's decimation first; under a live Decimate modifier
  the collapse pattern changes every round and the settle never converges.
- Do not "resolve" leftover intersections by pushing single vertices off whatever they touch in a
  loop: where the cloth is caught between two obstacles (a pauldron's rim and the sleeve) it
  oscillates and grows spikes. Fix the gaps upstream instead.
- slide_clear: a rigid ornament on cloth (a brooch) sits square to the cloth's averaged normal with
  its back on the highest folds under it, then slides out along that normal until it overlaps no
  armour. Pushing its vertices one by one bends it.

Check the result with a rest-pose overlap inventory per part pair and with renders in which the
cloth has its own colour: a triangle-pair count cannot tell a hidden tuck from steel showing
through.
"""
import math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree


def neighbours(n, F):
    """Vertex neighbour lists of a polygon mesh (n vertices, faces F as index lists)."""
    nb = [set() for _ in range(n)]
    for f in F:
        for a in f:
            nb[a].update(f)
    return [[j for j in sorted(nb[i]) if j != i] for i in range(n)]


def taubin(V, F, iters=10, lam=0.5, mu=-0.53, fixed=()):
    """Shrink-free smoothing of cloth vertices V (n, 3); `fixed` indices stay put (pinned rows)."""
    nbl = neighbours(len(V), F)
    free = np.ones((len(V), 1))
    free[list(fixed)] = 0.0
    P = np.array(V, dtype=float)
    for _ in range(iters):
        for w in (lam, mu):
            C = np.array([P[l].mean(axis=0) if l else P[i] for i, l in enumerate(nbl)])
            P = P + w * (C - P) * free
    return P


def keep_clear(V, trees_gaps, reach=0.06, rounds=1, inside=0.012):
    """Each vertex moved off each (BVHTree, gap) pair's surface to at least `gap`. Inside (straight
    behind the nearest face, within about 25 degrees of its normal, and less than `inside` deep): out
    along the face's normal, keeping its side. Outside but nearer than `gap`: straight away from the
    nearest point. A vertex beside a rim or a shell's edge is outside, however its nearest face faces."""
    P = np.array(V, dtype=float)
    for _ in range(rounds):
        for tree, gap in trees_gaps:
            for i, p in enumerate(P):
                q = Vector(tuple(p))
                loc, n, _, d = tree.find_nearest(q, reach)
                if loc is None:
                    continue
                v = q - loc
                if d < 1e-7:
                    P[i] = tuple(q + n * gap)
                    continue
                c = v.dot(n) / d
                if c < -0.9 and d < inside:
                    P[i] = tuple(q + n * (gap + d))
                elif d < gap:
                    P[i] = tuple(q + (v / d * (gap - d) if c > -0.9 else n * (gap + d)))
    return P


def ray_dir(a, ph):
    """Unit ray at ring angle a (0 towards -Y, the character's front; pi/2 towards +X) and elevation ph."""
    return Vector((math.sin(a) * math.cos(ph), -math.cos(a) * math.cos(ph), math.sin(ph)))


def support_envelope(origin, trees_gaps, n_angles, elevations, usable=None, reach=0.6):
    """M[i, k]: distance from `origin` along ray (2 pi i / n_angles, elevations[k]) to the outermost surface
    of the (BVHTree, gap) pairs plus that pair's gap, the gap measured straight off every surface (the
    point moves out along the ray until no surface is nearer than its gap). usable(pair index, point,
    angle) -> bool rejects hits and near points the cloth does not lie on. 0 where a ray meets nothing."""
    M = np.zeros((n_angles, len(elevations)))
    for i in range(n_angles):
        a = 2 * math.pi * i / n_angles
        for k, ph in enumerate(elevations):
            D = ray_dir(a, ph)
            best = 0.0
            for j, (tree, gap) in enumerate(trees_gaps):
                h = tree.ray_cast(origin + D * reach, -D, reach)
                if h[0] is not None and (usable is None or usable(j, h[0], a)):
                    best = max(best, reach - h[3] + gap)
            if best > 0:
                for _ in range(30):
                    p = origin + D * best
                    worst = 0.0
                    for j, (tree, gap) in enumerate(trees_gaps):
                        loc, _, _, dist = tree.find_nearest(p, gap)
                        if loc is not None and (usable is None or usable(j, loc, a)):
                            worst = max(worst, gap - dist)
                    if worst <= 2e-4:
                        break
                    best += max(worst, 0.0005)
            M[i, k] = best
    return M


def _blur(X, passes_a=1, passes_p=4):
    k = (1.0, 4.0, 6.0, 4.0, 1.0)
    for _ in range(passes_a):                          # periodic round the axis
        X = sum(w * np.roll(X, s, axis=0) for w, s in zip(k, (-2, -1, 0, 1, 2))) / 16.0
    for _ in range(passes_p):                          # clamped up and down
        Pd = np.pad(X, ((0, 0), (2, 2)), mode="edge")
        X = sum(w * Pd[:, 2 + s:2 + s + X.shape[1]] for w, s in zip(k, (-2, -1, 0, 1, 2))) / 16.0
    return X


def membrane(M, passes=60, elevations=None, column=False):
    """A smooth surface over the envelope M that never dips under it: rays that met nothing take their
    neighbours' value up and down, then M is blurred and lifted back to M `passes` times. column (with
    elevations): above each angle's last hit the support goes on up as a vertical column of that radius
    (a neck whose head was left out)."""
    M = np.array(M, dtype=float)
    for i in range(M.shape[0]):
        ok = np.flatnonzero(M[i] > 0)
        if column and len(ok):
            k = ok[-1]
            M[i, k + 1:] = M[i, k] * math.cos(elevations[k]) / np.cos(elevations[k + 1:])
            ok = np.flatnonzero(M[i] > 0)
        if len(ok) and len(ok) < M.shape[1]:
            M[i] = np.interp(np.arange(M.shape[1]), ok, M[i][ok])
    E = M.copy()
    for _ in range(passes):
        E = np.maximum(_blur(E), M)
    return np.maximum(_blur(E, 1, 2), M)


def envelope_surface(origin, E, elevations, blur=12, radial=1.0):
    """(Q, N): the membrane's points (angles x elevations x 3) and the unit directions to push cloth out
    along: the normals of the membrane blurred `blur` passes up and down, plus `radial` of the ray from
    origin. A membrane's own normals converge at a concave corner (a neck meeting the shoulders) and a
    roll higher than the corner's radius folds over itself there; the rays spread."""
    n = E.shape[0]
    D = np.array([[tuple(ray_dir(2 * math.pi * i / n, ph)) for ph in elevations] for i in range(n)])
    Q = np.array(tuple(origin)) + D * E[..., None]
    Qn = np.array(tuple(origin)) + D * (_blur(E, 1, blur) if blur else E)[..., None]
    N = np.cross(np.gradient(Qn, axis=1), (np.roll(Qn, -1, axis=0) - np.roll(Qn, 1, axis=0)) * 0.5)
    N *= np.sign((N * D).sum(axis=2))[..., None]
    N /= np.linalg.norm(N, axis=2)[..., None] + 1e-12
    if radial:
        N = N + radial * D
        N /= np.linalg.norm(N, axis=2)[..., None] + 1e-12
    return Q, N


def roll_over(V, F, tree, axis_xy, clear=0.006, depth=0.06, ease=16):
    """Cloth vertices that lie behind the outer face of `tree` (up to `depth` inside it, along the
    horizontal ray from the vertical axis through axis_xy) move out over it to `clear`, the move
    eased over the faces (`ease` rounds)."""
    cx, cy = axis_xy
    n = len(V)
    need = np.zeros(n)
    dirs = np.zeros((n, 3))
    for i, p in enumerate(V):
        d = Vector((p[0] - cx, p[1] - cy, 0.0))
        r = d.length
        if r < 1e-6:
            continue
        d /= r
        dirs[i] = tuple(d)
        o, travelled, r_out = Vector((cx, cy, p[2])), 0.0, None
        while travelled < r + 0.08:                    # the outermost face along this ray
            hit = tree.ray_cast(o, d, r + 0.08 - travelled)
            if hit[0] is None:
                break
            travelled += hit[3]
            r_out = travelled
            o = hit[0] + d * 0.0005
            travelled += 0.0005
        if r_out is not None and r_out - depth < r < r_out + clear:
            need[i] = r_out + clear - r
    nbl = neighbours(n, F)
    disp = need.copy()
    for _ in range(ease):
        disp = np.array([max(need[i], 0.5 * disp[i] + 0.5 * np.mean([disp[j] for j in nbl[i]] or [0.0]))
                         for i in range(n)])
    return np.array(V, dtype=float) + dirs * disp[:, None]


def ridge_offset(cloth_tree, centre, normal, frame, radius, rings=(0.0, 0.5, 1.0), spokes=12):
    """How far out along `normal` the cloth's highest fold stands within a disc of `radius` round
    `centre` (frame: a 3x3 whose columns span the disc's plane and normal): where an ornament's
    back should sit."""
    top = 0.0
    for k in range(spokes):
        a = 2 * np.pi * k / spokes
        for f in rings:
            q = centre + frame @ Vector((np.cos(a) * radius * f, 0.0, np.sin(a) * radius * f))
            h = cloth_tree.ray_cast(q + normal * 0.05, -normal, 0.1)
            if h[0] is not None:
                top = max(top, (h[0] - centre).dot(normal))
    return top


def slide_clear(local_verts, polys, M, direction, tree, step=0.001, max_steps=40):
    """A rigid piece (vertices in its local frame, placed by 4x4 M) moved along `direction` until
    it overlaps nothing in `tree`. Returns the new matrix."""
    for _ in range(max_steps):
        if not BVHTree.FromPolygons([M @ v for v in local_verts], polys).overlap(tree):
            break
        M = Matrix.Translation(direction * step) @ M
    return M


def lift_over_edge(V, F, tree, edge_xz, behind=Vector((0, 1, 0)), clear=0.010, ease=20, reach=0.12):
    """Cloth faces that cross the garment in `tree` (a cloak hanging behind the collar) with their
    vertices on its body side (a ray along `behind` meets it within `reach`) rise above its top
    edge (edge_xz: (x, z) points along that edge) plus `clear`, the lift eased over the cloth."""
    xs = np.array([p[0] for p in sorted(edge_xz)])
    zs = np.array([p[1] for p in sorted(edge_xz)])
    n = len(V)
    need = np.zeros(n)
    cloth = BVHTree.FromPolygons([Vector(tuple(v)) for v in V], [list(f) for f in F])
    for a, _ in cloth.overlap(tree):                  # (cloth face, garment face)
        for i in F[a]:
            p = Vector(tuple(V[i]))
            if not xs[0] <= p.x <= xs[-1] or tree.ray_cast(p, behind, reach)[0] is None:
                continue
            need[i] = max(need[i], float(np.interp(p.x, xs, zs)) + clear - p.z)
    if not need.any():
        return np.array(V, dtype=float)
    nbl = neighbours(n, F)
    disp = need.copy()
    for _ in range(ease):
        disp = np.array([max(need[i], 0.5 * disp[i] + 0.5 * np.mean([disp[j] for j in nbl[i]] or [0.0]))
                         for i in range(n)])
    out = np.array(V, dtype=float)
    out[:, 2] += disp
    return out


def settle_faces(ob, trees, away, step=0.0008, iters=20, reach=0.013):
    """Move ob's vertices near its crossings with the BVH trees `trees` a `step` along away(p) (a
    world point to a unit direction) per round, eased over two rings of neighbours, until its
    evaluated surface crosses none of them. Returns (rounds, crossings left)."""
    import bpy
    from mathutils.kdtree import KDTree
    me = ob.data
    mw, inv = ob.matrix_world, ob.matrix_world.inverted()
    nbl = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nbl[a].append(b)
        nbl[b].append(a)
    top = bpy.context.scene.collection.objects
    linked = ob.name not in bpy.context.view_layer.objects and ob.name not in top
    if linked:                                        # an excluded collection is not evaluated
        top.link(ob)
    left = 0
    try:
        for rnd in range(iters):
            dg = bpy.context.evaluated_depsgraph_get()
            eo = ob.evaluated_get(dg)
            em = eo.to_mesh()
            ev = [mw @ v.co for v in em.vertices]
            polys = [list(q.vertices) for q in em.polygons]
            eo.to_mesh_clear()
            mine = BVHTree.FromPolygons(ev, polys)
            pairs = [pr for t in trees for pr in mine.overlap(t)]
            left = len(pairs)
            if not pairs:
                return rnd, 0
            kd = KDTree(len(me.vertices))
            for v in me.vertices:
                kd.insert(mw @ v.co, v.index)
            kd.balance()
            w = [0.0] * len(me.vertices)
            for a in {a for a, _ in pairs}:
                for k in polys[a]:                    # the face's own corners, then its neighbourhood
                    _, i, dist = kd.find(ev[k])
                    if i is not None and dist < 0.012:
                        w[i] = 1.0
                c = sum((ev[i] for i in polys[a]), Vector()) / len(polys[a])
                for _, i, _ in kd.find_range(c, reach):
                    w[i] = 1.0
            for _ in range(2):
                w = [max(w[i], 0.5 * max((w[j] for j in nbl[i]), default=0.0)) for i in range(len(w))]
            for v in me.vertices:
                if w[v.index]:
                    p = mw @ v.co
                    v.co = inv @ (p + away(p) * step * w[v.index])
            me.update()
    finally:
        if linked:
            top.unlink(ob)
    return iters, left
