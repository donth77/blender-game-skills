"""
CLOTH TOOLS
Finishing passes for draped cloth (cowls, scarves, hoods, cloaks) after Blender's cloth solver has
settled it, and for rigid ornaments pinned on it. Copy next to the build scripts and import it (it
only needs numpy, bpy and mathutils):

  import cloth_tools as C
  V = C.taubin(V, F, fixed=range(ring * 2))                 # soft folds, the pinned rows kept
  V = C.keep_clear(V, [(soft_tree, 0.004), (steel_tree, 0.009), (cloak_tree, 0.004)])
  V = C.roll_over(V, F, cloak_tree, axis_xy=(0.0, 0.02))     # the collar over the cloak's top
  V = C.taubin(V, F, iters=4, fixed=range(ring * 2))
  V = C.keep_clear(V, [...], rounds=3)
  M = C.slide_clear(brooch_verts, brooch_polys, M, normal, armour_tree)   # a pinned ornament

What each pass does and why:
- taubin: the solver leaves small crumples that read as crushed paper on a delivery mesh. Taubin
  smoothing (a Laplacian step in, then a slightly larger one out) removes them without shrinking
  the cloth; a plain Laplacian pulls a cowl tight onto the neck. The fold pattern is low
  frequency and stays.
- keep_clear: smoothing moves vertices a few mm, so put the solver's clearances back afterwards,
  along the nearest surface's own normal. That keeps each vertex on the side the solver left it
  (cloth tucked inside a gorget's collar stays inside). Never push everything "away from the body":
  it drags the tucked cloth through the plate.
- Gaps by material: give steel a larger gap than soft layers, in the solver (collision thickness)
  and here (about 9 mm against 4 mm for a cowl with 18 mm faces). A face between two vertices
  that clear a plate's rim still cuts across the rim when the gap is smaller than the face's sag
  over it. Decimating the cloth for LOD0 makes faces larger and the cutting worse.
- roll_over: the reference decides the overlap order. A collar that lies over the cloak (the
  cloak rising into it) is rolled out over the cloak's top where the solver left it underneath,
  the move eased over the faces so the cloth rolls over the edge instead of folding across it.
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


def keep_clear(V, trees_gaps, reach=0.06, rounds=1):
    """Each vertex moved off each (BVHTree, gap) pair's surface to at least `gap`, along the nearest
    face's normal (it keeps its side of that surface)."""
    P = np.array(V, dtype=float)
    for _ in range(rounds):
        for tree, gap in trees_gaps:
            for i, p in enumerate(P):
                q = Vector(tuple(p))
                loc, n, _, _ = tree.find_nearest(q, reach)
                if loc is None:
                    continue
                s = (q - loc).dot(n)
                if s < gap:
                    P[i] = tuple(q + n * (gap - s))
    return P


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
