import matplotlib.pyplot as plt
import numpy as np

# 1. Simulate a 3D helical path (blue line) moving diagonally while rotating
t = np.linspace(0, 6 * np.pi, 150)  # 3 full rotations (50 frames per rotation)
frames_per_rotation = 50

# Helical motion + diagonal drift
x = np.cos(t) + 0.3 * t
y = np.sin(t) + 0.3 * t
z = 0.5 * t
path = np.column_stack((x, y, z))

# 2. Calculate the moving center axis (red line) using a sliding window
# Window size matches 1 full rotation so circular offsets cancel out
half_w = frames_per_rotation // 2
axis_points = []
valid_path_points = []

for i in range(half_w, len(path) - half_w):
    window = path[i - half_w : i + half_w + 1]
    center_i = np.mean(window, axis=0)
    axis_points.append(center_i)
    valid_path_points.append(path[i])

axis_points = np.array(axis_points)
valid_path_points = np.array(valid_path_points)

# 3. Plot the 3D "Scala a Chiocciola"
fig = plt.figure(figsize=(8, 8))
ax = fig.add_subplot(111, projection="3d")

# Blue line: Outer trajectory of the point
ax.plot(
    path[:, 0],
    path[:, 1],
    path[:, 2],
    color="blue",
    linewidth=2,
    label="Point Path",
)

# Red line: Moving center axis
ax.plot(
    axis_points[:, 0],
    axis_points[:, 1],
    axis_points[:, 2],
    color="darkred",
    linewidth=2.5,
    label="Center Axis",
)

# Yellow lines: Radial spokes (drawn every 5th frame for clarity)
for i in range(0, len(valid_path_points), 5):
    p = valid_path_points[i]
    c = axis_points[i]
    ax.plot([p[0], c[0]], [p[1], c[1]], [p[2], c[2]], color="gold", linewidth=1.5)

ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.set_zlabel("Z")
ax.legend()
plt.show()
