import numpy as np
import pyvista as pv

# ---------------------------------------------------------
# 1. Sample Data (Replace with your extracted frame coordinates)
# ---------------------------------------------------------
# Simulating 150 frames (3 full rotations, 50 frames per rotation)
t = np.linspace(0, 6 * np.pi, 150)
frames_per_rotation = 50

# Blue helical trajectory
path = np.column_stack((np.cos(t) + 0.3 * t, np.sin(t) + 0.3 * t, 0.5 * t))

# ---------------------------------------------------------
# 2. Compute Moving Center Axis (Red Line)
# ---------------------------------------------------------
# Note: If you already have multiple tags per frame, replace this loop
# with: axis_points = np.array([np.mean(list(frame.values()), axis=0) for frame in frames])
half_w = frames_per_rotation // 2
axis_points = []
valid_path = []

for i in range(half_w, len(path) - half_w):
    window = path[i - half_w : i + half_w + 1]
    axis_points.append(np.mean(window, axis=0))
    valid_path.append(path[i])

axis_points = np.array(axis_points)
valid_path = np.array(valid_path)

# ---------------------------------------------------------
# 3. Build PyVista Meshes
# ---------------------------------------------------------
# Blue Line: Continuous outer trajectory
blue_path_mesh = pv.lines_from_points(path)

# Red Line: Continuous central axis
red_axis_mesh = pv.lines_from_points(axis_points)

# Yellow Lines: Radial spokes ("scala a chiocciola" steps)
# Sample every 5th frame so the steps are clean and readable
step_stride = 5
p_sub = valid_path[::step_stride]
c_sub = axis_points[::step_stride]

# Interleave points: [p0, c0, p1, c1, p2, c2, ...]
spoke_vertices = np.empty((len(p_sub) * 2, 3), dtype=float)
spoke_vertices[0::2] = p_sub
spoke_vertices[1::2] = c_sub

# Create disconnected line segments connecting pairs (0-1, 2-3, 4-5...)
n_spokes = len(p_sub)
cells = np.column_stack(
    (
        np.full(n_spokes, 2),  # 2 points per line segment
        np.arange(0, 2 * n_spokes, 2),  # Start index (outer point)
        np.arange(1, 2 * n_spokes, 2),  # End index (center axis point)
    )
).ravel()

yellow_spokes_mesh = pv.PolyData(spoke_vertices, lines=cells)

# ---------------------------------------------------------
# 4. Render Scene
# ---------------------------------------------------------
plotter = pv.Plotter()
plotter.set_background("white")

# Add meshes (use .tube() if you want 3D cylindrical thickness instead of flat lines)
plotter.add_mesh(blue_path_mesh, color="blue", line_width=4, label="Point Path")
plotter.add_mesh(red_axis_mesh, color="darkred", line_width=5, label="Center Axis")
plotter.add_mesh(yellow_spokes_mesh, color="gold", line_width=3, label="Radial Steps")

# Optional: Add spheres at the path vertices for visual clarity
plotter.add_points(
    valid_path[::step_stride],
    color="blue",
    point_size=8,
    render_points_as_spheres=True,
)

plotter.add_legend()
plotter.show_grid()
plotter.show()
