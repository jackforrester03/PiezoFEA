"""Spike: structured r-z mesh of a full-electroded disc for openCFS (axi).

Coordinates: x = r, y = z (openCFS axi convention, as in the Testsuite case HarmAxiQ).
Physical groups: 'piezo' (surface), 'top', 'bottom', 'axis', 'outer' (lines).
"""

import sys

import gmsh

RADIUS = 15e-3  # m
THICKNESS = 2.1e-3  # m
H = 0.125e-3  # target element size, m (quadratic elements)


def build(path: str) -> None:
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("disc")
    geo = gmsh.model.geo
    p1 = geo.addPoint(0, 0, 0)
    p2 = geo.addPoint(RADIUS, 0, 0)
    p3 = geo.addPoint(RADIUS, THICKNESS, 0)
    p4 = geo.addPoint(0, THICKNESS, 0)
    bottom = geo.addLine(p1, p2)
    outer = geo.addLine(p2, p3)
    top = geo.addLine(p3, p4)
    axis = geo.addLine(p4, p1)
    loop = geo.addCurveLoop([bottom, outer, top, axis])
    surf = geo.addPlaneSurface([loop])

    nr = round(RADIUS / H)
    nz = round(THICKNESS / H)
    for line, n in ((bottom, nr), (top, nr), (outer, nz), (axis, nz)):
        geo.mesh.setTransfiniteCurve(line, n + 1)
    geo.mesh.setTransfiniteSurface(surf)
    geo.mesh.setRecombine(2, surf)
    geo.synchronize()

    for dim, tag, name in (
        (2, surf, "piezo"),
        (1, top, "top"),
        (1, bottom, "bottom"),
        (1, axis, "axis"),
        (1, outer, "outer"),
    ):
        gmsh.model.setPhysicalName(dim, gmsh.model.addPhysicalGroup(dim, [tag]), name)

    gmsh.option.setNumber("Mesh.ElementOrder", 2)
    gmsh.option.setNumber("Mesh.SecondOrderIncomplete", 1)  # 8-node serendipity quads
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.model.mesh.generate(2)
    gmsh.write(path)
    gmsh.finalize()
    print(f"wrote {path}: {nr} x {nz} quad8 elements")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "disc.msh")
