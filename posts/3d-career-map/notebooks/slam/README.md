# SLAM Hands-On Notebooks

Three self-contained Colab notebooks covering the SLAM engineering learning path
from first principles. No robotics background required — only Python + NumPy.

---

## Notebooks

### 01 — Kalman Filter & EKF: Robot Tracking from Scratch
**File:** `01_ekf_robot_tracking.ipynb`

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ChenChihYuan/geo-instructor/blob/main/posts/3d-career-map/notebooks/slam/01_ekf_robot_tracking.ipynb)

What you build:
- Linear Kalman Filter for 1-D position tracking
- Extended Kalman Filter (EKF) for a 2-D robot driving in a circle
- Jacobian verification via finite differences
- Visualization: convergence, covariance ellipses, Kalman gain

Key concepts: predict-update loop, Gaussian belief, Kalman gain, CTRV motion model, Jacobian

---

### 02 — ICP: Aligning Two Point Clouds from Scratch
**File:** `02_icp_alignment.ipynb`

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ChenChihYuan/geo-instructor/blob/main/posts/3d-career-map/notebooks/slam/02_icp_alignment.ipynb)

What you build:
- Point-to-Point ICP with SVD closed-form solution
- KD-tree accelerated nearest neighbor (vs brute-force benchmark)
- Surface normal estimation via local PCA
- Point-to-Plane ICP (linearized Gauss-Newton)
- Basin of convergence analysis

Key concepts: SVD rigid transform, KD-tree, normals, point-to-plane error, initial guess

---

### 03 — Pose Graph Optimization: Closing the Loop
**File:** `03_pose_graph_opt.ipynb`

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ChenChihYuan/geo-instructor/blob/main/posts/3d-career-map/notebooks/slam/03_pose_graph_opt.ipynb)

What you build:
- Pose graph with odometry edges + loop closure edge
- Weighted least-squares cost function
- Analytic Jacobians for SE(2) edge error
- L-BFGS-B optimization via scipy
- Multi-loop closure experiments
- Comparison to GTSAM/g2o architecture

Key concepts: factor graph, information matrix, Gauss-Newton, loop closure, drift correction

---

## Dependencies

All standard Python:
```
numpy
scipy
matplotlib
```

No installs needed on Google Colab (all pre-installed).

---

## Learning Path

```
NB 01: EKF          -> understand uncertainty + sensor fusion
NB 02: ICP          -> understand scan matching + registration
NB 03: Pose Graph   -> understand SLAM back-end + loop closure
                               |
                        Now read: GTSAM, ORB-SLAM3, LOAM source code
```
