---
title: "How three-mesh-bvh Makes Raycasting 100x Faster"
date: 2026-06-17
description: "A visual deep-dive into Bounding Volume Hierarchies: the spatial acceleration structure that turns O(n) raycasting into O(log n)"
tags: ["computer-graphics", "spatial-data-structures", "three.js", "algorithms"]
---

# How three-mesh-bvh Makes Raycasting 100x Faster

You have an 80,000-triangle mesh.

You need to cast 500 rays per frame.

At 60fps.

Without a BVH, you check every ray against every triangle.

That's **40 million** intersection tests per frame.

With a BVH, you check only the triangles each ray actually passes through.

That's around **5,000** intersection tests per frame.

**8000x fewer tests.**

This is what three-mesh-bvh does.

---

## The Problem

Imagine you're building a first-person game in Three.js.

Your player aims a gun.

You fire a raycast to see what they hit.

```javascript
const raycaster = new THREE.Raycaster();
raycaster.setFromCamera(mouse, camera);
const hits = raycaster.intersectObjects(scene.children);
```

Behind the scenes, Three.js tests that ray against **every triangle** in every mesh.

For a simple scene, this is fine.

For a realistic environment—buildings, terrain, foliage—this is catastrophic.

Testing one ray against one triangle is cheap.

Testing one ray against **80,000 triangles** is not.

Testing **500 rays** (for selection, shadows, physics) against **80,000 triangles** brings your frame rate to its knees.

You need a spatial acceleration structure.

You need a **Bounding Volume Hierarchy**.

---

## What is a BVH?

A BVH is a binary tree.

Each node stores:
- A bounding box
- Either two children (internal node)
- Or a list of triangles (leaf node)

The tree is constructed so that:
- The root contains all geometry
- Each level splits space into two regions
- Leaves contain small clusters of triangles

Here's the key insight:

**If a ray misses a bounding box, it misses everything inside.**

You test the ray against the root box.

If it misses, you're done in one test.

If it hits, you descend to the children.

At each level, you eliminate half the geometry.

This turns O(n) raycasting into **O(log n)**.

---

## Visual Example: Building a BVH

Let's build a BVH for 8 triangles.

### Step 1: Compute the Root Bounding Box

```
All 8 triangles:

     T3  T4
   /  \ /  \
  T1  T2  T5  T6
       \ /
        T7
         T8

Root bounding box:
┌─────────────────┐
│  T1 T2 T3 T4    │
│     T5 T6       │
│      T7 T8      │
└─────────────────┘
```

The root contains all geometry.

### Step 2: Find the Split Axis

Which axis splits the triangles most evenly?

We could split on:
- X axis (left/right)
- Y axis (top/bottom)
- Z axis (front/back)

The BVH typically chooses the **longest axis** of the bounding box.

In this case, X.

### Step 3: Find the Split Position

Where on the X axis do we split?

Three strategies:

**CENTER**: Split at the center of the bounding box
```
Split position = (xMin + xMax) / 2
```

**AVERAGE**: Split at the average centroid position
```
Split position = average(triangle centroids)
```

**SAH (Surface Area Heuristic)**: Split to minimize expected ray traversal cost
```
Split position = argmin(cost of left + cost of right)
```

Let's use CENTER for now.

### Step 4: Partition the Triangles

Sort triangles based on whether their centroid is left or right of the split.

```
Left child (4 triangles):      Right child (4 triangles):
┌──────────┐                   ┌──────────┐
│ T1  T2   │                   │ T4  T5   │
│   T3     │                   │ T6  T7   │
│     T7   │                   │     T8   │
└──────────┘                   └──────────┘
```

Now we have two nodes, each with 4 triangles.

### Step 5: Recurse

Repeat the process for each child until each node has ≤ `maxLeafSize` triangles (default: 10).

After recursion:

```
                   Root
                 /     \
              Left      Right
             /   \      /   \
           T1,T2 T3,T7 T4,T5 T6,T8
```

Each leaf now contains 2 triangles.

The tree is complete.

---

## How Raycasting Works with a BVH

Now fire a ray.

### Step 1: Test Against the Root

```
Ray: ─────────────────────────►

┌─────────────────┐
│  Root           │  ← Does ray intersect? YES
└─────────────────┘
```

The ray hits the root. Descend.

### Step 2: Test Against Children

```
┌──────────┐    ┌──────────┐
│ Left     │    │ Right    │
└──────────┘    └──────────┘
     ↑                ✗
   HIT             MISS
```

The ray hits the left child, misses the right.

We just eliminated **4 triangles** without testing them.

### Step 3: Test Against Leaves

Descend into the left child:

```
┌─────┐  ┌─────┐
│T1,T2│  │T3,T7│
└─────┘  └─────┘
   ✗        ↑
  MISS     HIT
```

The ray hits the right leaf (T3, T7).

Now test the ray against **only** T3 and T7.

T3: miss
T7: **hit at distance 5.2**

Done.

### What We Tested

- 1 root box
- 2 child boxes
- 2 triangles

**5 tests** instead of **8 tests**.

For 80,000 triangles, this becomes:
- ~**20 box tests**
- ~**10 triangle tests**

**30 tests** instead of **80,000 tests**.

This is why BVHs are fast.

---

## The Three Splitting Strategies

three-mesh-bvh supports three algorithms for choosing where to split.

### CENTER

Split at the midpoint of the bounding box.

```javascript
const geom = new THREE.TorusKnotGeometry(10, 3, 400, 100);
geom.computeBoundsTree({ strategy: CENTER });
```

**Pros:**
- Fast to compute
- Simple

**Cons:**
- Can create unbalanced trees if geometry is unevenly distributed

**When to use:**
- Uniformly distributed geometry
- Prototyping
- WebWorker generation (speed matters)

### AVERAGE

Split at the average centroid position.

```javascript
geom.computeBoundsTree({ strategy: AVERAGE });
```

**Pros:**
- Better balance than CENTER
- Still fast

**Cons:**
- Doesn't account for triangle size
- Can create poorly clustered nodes

**When to use:**
- Default choice for most use cases
- Good balance of speed and quality

### SAH (Surface Area Heuristic)

Split to minimize expected traversal cost.

The cost function:

```
cost = (leftSurfaceArea / nodeSurfaceArea) * leftCount * INTERSECT_COST
     + (rightSurfaceArea / nodeSurfaceArea) * rightCount * INTERSECT_COST
     + TRAVERSAL_COST
```

Where:
- `leftSurfaceArea` = surface area of left bounding box
- `rightSurfaceArea` = surface area of right bounding box
- `nodeSurfaceArea` = surface area of parent bounding box
- `leftCount` = number of primitives in left child
- `rightCount` = number of primitives in right child

The algorithm tries **32 split candidates** (bins) per axis and picks the one with minimum cost.

```javascript
geom.computeBoundsTree({ strategy: SAH });
```

**Pros:**
- Provably optimal for ray tracing
- Best raycast performance

**Cons:**
- Slowest to build (10-20x slower than CENTER)
- More memory overhead during construction

**When to use:**
- Static geometry (build once, query many times)
- Path tracing / high ray counts
- Production assets

---

## How the Code Works

Let's trace through the actual implementation.

### Entry Point: `computeBoundsTree()`

```javascript
import { computeBoundsTree } from 'three-mesh-bvh';

THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;

const geom = new THREE.TorusKnotGeometry(10, 3, 400, 100);
geom.computeBoundsTree();
```

This creates a `MeshBVH` and stores it in `geom.boundsTree`.

### Step 1: Compute Primitive Bounds

For each triangle, compute its bounding box and centroid:

```javascript
// From src/core/build/buildTree.js
const primitiveBounds = new Float32Array(6 * count);
bvh.computePrimitiveBounds(offset, count, primitiveBounds);
```

Each triangle gets 6 floats:
```
[xMin, yMin, zMin, xMax, yMax, zMax]
```

The centroid is stored implicitly as the midpoint.

### Step 2: Build the Tree Recursively

```javascript
function splitNode(node, offset, count, centroidBoundingData, depth = 0) {
    // Base case: make a leaf
    if (count <= maxLeafSize || depth >= maxDepth) {
        node.offset = offset;
        node.count = count;
        return node;
    }

    // Find the split
    const split = getOptimalSplit(
        node.boundingData,
        centroidBoundingData,
        primitiveBounds,
        offset,
        count,
        strategy
    );

    // Partition triangles
    const splitOffset = partition(
        partitionBuffer,
        partitionStride,
        primitiveBounds,
        offset,
        count,
        split
    );

    // Create left child
    const left = new BVHNode();
    const lcount = splitOffset - offset;
    getBounds(primitiveBounds, offset, lcount, left.boundingData);
    splitNode(left, offset, lcount, cacheBoundingData, depth + 1);

    // Create right child
    const right = new BVHNode();
    const rcount = count - lcount;
    getBounds(primitiveBounds, splitOffset, rcount, right.boundingData);
    splitNode(right, splitOffset, rcount, cacheBoundingData, depth + 1);

    node.left = left;
    node.right = right;
    node.splitAxis = split.axis;
}
```

This is a classic **top-down** recursive construction.

### Step 3: Flatten to a Buffer

For GPU-friendly access, the tree is flattened into a typed array:

```javascript
// From src/core/build/buildUtils.js
export function populateBuffer(byteOffset, node, buffer) {
    const stride4Offset = byteOffset / 4;
    const stride4 = UINT32_PER_NODE / 4;
    const isLeaf = !node.left;

    const boundingData = node.boundingData;
    for (let i = 0; i < 6; i++) {
        buffer[stride4Offset + i] = boundingData[i];
    }

    if (isLeaf) {
        buffer[stride4Offset + 6] = node.offset;
        buffer[stride4Offset + 7] = node.count;
    } else {
        // Encode split axis
        buffer[stride4Offset + 6] = node.splitAxis;
        // Child pointers stored implicitly by traversal order
    }
}
```

Each node takes **32 bytes**:
- 24 bytes: bounding box (6 floats)
- 4 bytes: offset or splitAxis
- 4 bytes: count or unused

Internal nodes and leaves use the same layout.

The tree is stored as a pre-order traversal:
```
[Root][Left subtree][Right subtree]
```

This enables fast traversal without pointers.

---

## Querying the BVH

### Raycasting

```javascript
const raycaster = new THREE.Raycaster();
raycaster.firstHitOnly = true; // Use raycastFirst()
const hits = raycaster.intersectObject(mesh);
```

The traversal algorithm:

```javascript
// Simplified from src/core/cast/raycastFirst.generated.js
function raycastFirst(bvh, root, side, ray) {
    let nodeIndex = 0;
    let closestHit = null;

    while (nodeIndex !== -1) {
        const isLeaf = IS_LEAF(nodeIndex, bvh);
        
        if (isLeaf) {
            // Test triangles in this leaf
            const offset = OFFSET(nodeIndex);
            const count = COUNT(nodeIndex);
            
            for (let i = 0; i < count; i++) {
                const triIndex = offset + i;
                const hit = intersectRay(ray, triIndex);
                
                if (hit && (!closestHit || hit.distance < closestHit.distance)) {
                    closestHit = hit;
                }
            }
            
            nodeIndex = NEXT_NODE(nodeIndex);
        } else {
            // Test bounding boxes
            const left = nodeIndex + 1;
            const right = RIGHT_NODE(nodeIndex);
            
            const hitLeft = intersectBox(ray, left);
            const hitRight = intersectBox(ray, right);
            
            if (hitLeft && hitRight) {
                // Hit both: visit closer first
                if (hitLeft.distance < hitRight.distance) {
                    nodeIndex = left;
                    // Push right to stack
                } else {
                    nodeIndex = right;
                    // Push left to stack
                }
            } else if (hitLeft) {
                nodeIndex = left;
            } else if (hitRight) {
                nodeIndex = right;
            } else {
                nodeIndex = NEXT_NODE(nodeIndex);
            }
        }
    }
    
    return closestHit;
}
```

The key optimizations:

1. **Early exit**: Once we find a hit, we can skip any box farther away
2. **Front-to-back traversal**: Visit closer boxes first
3. **Leaf threshold**: Stop subdividing at ~10 triangles

### Shapecast: The Swiss Army Knife

`shapecast` is a generalized traversal function.

Want to find all triangles in a sphere?

```javascript
const sphere = new THREE.Sphere(center, radius);
const triangles = [];

bvh.shapecast({
    intersectsBounds: box => sphere.intersectsBox(box),
    intersectsTriangle: tri => {
        if (tri.intersectsSphere(sphere)) {
            triangles.push(tri.clone());
            return false; // Keep searching
        }
    }
});
```

Want to find the closest point on the mesh to a query point?

```javascript
const closestPoint = new THREE.Vector3();
let closestDistance = Infinity;

bvh.shapecast({
    intersectsBounds: (box, isLeaf, score) => {
        const dist = box.distanceToPoint(point);
        return dist < closestDistance; // Prune if farther
    },
    intersectsTriangle: (tri) => {
        tri.closestPointToPoint(point, temp);
        const dist = temp.distanceTo(point);
        
        if (dist < closestDistance) {
            closestDistance = dist;
            closestPoint.copy(temp);
        }
    }
});
```

`shapecast` powers:
- Sphere casting
- Box casting
- Frustum culling
- Closest point queries
- SDF generation
- Triangle painting
- Voxelization

It's the most powerful function in the library.

---

## Real-World Use Cases

### 1. First-Person Games

Player movement with collision:

```javascript
const player = {
    position: new THREE.Vector3(0, 1.6, 0),
    velocity: new THREE.Vector3(0, 0, 0),
    radius: 0.3
};

function updatePlayer(delta) {
    // Apply gravity
    player.velocity.y -= 9.8 * delta;
    
    // Compute next position
    const nextPos = player.position.clone().addScaledVector(player.velocity, delta);
    
    // Sphere cast
    const sphere = new THREE.Sphere(nextPos, player.radius);
    let collision = false;
    
    bvh.shapecast({
        intersectsBounds: box => box.intersectsSphere(sphere),
        intersectsTriangle: tri => {
            if (tri.intersectsSphere(sphere)) {
                collision = true;
                return true; // Stop searching
            }
        }
    });
    
    if (!collision) {
        player.position.copy(nextPos);
    } else {
        // Resolve collision (slide along surface)
        player.velocity.y = 0;
    }
}
```

### 2. GPU Path Tracing

BVH data can be uploaded to shaders:

```glsl
// Vertex shader passes ray
varying vec3 vOrigin;
varying vec3 vDirection;

void main() {
    vOrigin = cameraPosition;
    vDirection = normalize(vWorldPosition - cameraPosition);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
```

```glsl
// Fragment shader traverses BVH
uniform sampler2D bvhData;
uniform sampler2D triangleData;

void main() {
    vec3 origin = vOrigin;
    vec3 direction = vDirection;
    
    // Traverse BVH on GPU
    float t = traverseBVH(origin, direction);
    
    if (t < MAX_DIST) {
        vec3 hitPoint = origin + direction * t;
        vec3 normal = computeNormal(hitPoint);
        
        // Path trace
        vec3 color = computeRadiance(hitPoint, normal);
        gl_FragColor = vec4(color, 1.0);
    } else {
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    }
}
```

Check the [GPU path tracing example](https://gkjohnson.github.io/three-mesh-bvh/example/bundle/gpuPathTracingSimple.html).

### 3. SDF Generation

Signed Distance Fields for each pixel:

```javascript
const resolution = 256;
const sdfData = new Float32Array(resolution * resolution * resolution);

for (let z = 0; z < resolution; z++) {
    for (let y = 0; y < resolution; y++) {
        for (let x = 0; x < resolution; x++) {
            const point = new THREE.Vector3(
                (x / resolution - 0.5) * 2,
                (y / resolution - 0.5) * 2,
                (z / resolution - 0.5) * 2
            );
            
            // Closest point query
            const result = bvh.closestPointToPoint(point);
            const distance = result.distance;
            
            // Determine sign (inside/outside)
            const ray = new THREE.Ray(point, result.point.clone().sub(point).normalize());
            const hits = bvh.raycast(ray);
            const isInside = hits.length % 2 === 1;
            
            const idx = x + y * resolution + z * resolution * resolution;
            sdfData[idx] = isInside ? -distance : distance;
        }
    }
}
```

Check the [SDF generation example](https://gkjohnson.github.io/three-mesh-bvh/example/bundle/sdfGeneration.html).

### 4. Triangle Painting

Paint only visible triangles:

```javascript
const mouse = new THREE.Vector2();
const raycaster = new THREE.Raycaster();
const paintRadius = 0.5;

canvas.addEventListener('mousemove', (e) => {
    mouse.x = (e.clientX / canvas.width) * 2 - 1;
    mouse.y = -(e.clientY / canvas.height) * 2 + 1;
    
    raycaster.setFromCamera(mouse, camera);
    const hit = raycaster.intersectObject(mesh)[0];
    
    if (hit) {
        const sphere = new THREE.Sphere(hit.point, paintRadius);
        const colorAttribute = mesh.geometry.attributes.color;
        
        bvh.shapecast({
            intersectsBounds: box => box.intersectsSphere(sphere),
            intersectsTriangle: (tri, index) => {
                if (tri.intersectsSphere(sphere)) {
                    // Paint this triangle red
                    colorAttribute.setXYZ(index * 3 + 0, 1, 0, 0);
                    colorAttribute.setXYZ(index * 3 + 1, 1, 0, 0);
                    colorAttribute.setXYZ(index * 3 + 2, 1, 0, 0);
                }
            }
        });
        
        colorAttribute.needsUpdate = true;
    }
});
```

Check the [triangle painting example](https://gkjohnson.github.io/three-mesh-bvh/example/bundle/collectTriangles.html).

---

## Performance Characteristics

### Build Time

| Strategy | Speed      | Quality    |
|----------|------------|------------|
| CENTER   | Fastest    | Good       |
| AVERAGE  | Fast       | Better     |
| SAH      | Slow       | Best       |

For an 80,000 triangle mesh:
- CENTER: ~20ms
- AVERAGE: ~40ms
- SAH: ~400ms

### Memory Usage

Each BVH node: **32 bytes**

Tree depth: **~log₂(triangles / leafSize)**

For 80,000 triangles with leafSize=10:
- Leaf count: 8,000 leaves
- Internal nodes: ~8,000 nodes
- Total nodes: ~16,000 nodes
- Memory: 16,000 × 32 = **512 KB**

Plus the reordered index buffer (same size as original).

### Query Performance

| Operation            | Without BVH | With BVH   |
|---------------------|-------------|------------|
| Single raycast      | O(n)        | O(log n)   |
| Closest point       | O(n)        | O(log n)   |
| Sphere intersection | O(n)        | O(log n)   |
| 500 rays @ 80k tris | ~5 fps      | ~60 fps    |

The speedup depends on:
- Ray coherence (parallel rays are faster)
- Geometry distribution (sparse is better)
- Tree quality (SAH > AVERAGE > CENTER)

---

## Advanced: Indirect Mode

By default, three-mesh-bvh **reorders the index buffer** to match the BVH leaf order.

This improves cache coherency.

But it modifies the geometry.

If you can't modify the index (e.g., the geometry is shared), use **indirect mode**:

```javascript
geom.computeBoundsTree({ indirect: true });
```

In indirect mode:
- The original index is **not** modified
- An extra indirection buffer maps BVH leaves to original indices
- Slightly slower queries (~10%)
- Higher memory usage

---

## Async Generation with Web Workers

Building a BVH blocks the main thread.

For large meshes, generate async:

```javascript
import { GenerateMeshBVHWorker } from 'three-mesh-bvh/worker';

const worker = new GenerateMeshBVHWorker();
const geometry = new THREE.TorusKnotGeometry(10, 3, 400, 100);

worker.generate(geometry, { strategy: SAH }).then(bvh => {
    geometry.boundsTree = bvh;
    console.log('BVH ready!');
});
```

For **parallel** generation (uses SharedArrayBuffer):

```javascript
import { ParallelMeshBVHWorker } from 'three-mesh-bvh/worker';

const worker = new ParallelMeshBVHWorker();
worker.generate(geometry).then(bvh => {
    geometry.boundsTree = bvh;
});
```

This splits construction across multiple cores.

---

## Comparison to Other Spatial Structures

### BVH vs Octree

**Octree:**
- Splits space uniformly
- Fixed depth
- Can waste nodes on empty space

**BVH:**
- Splits geometry adaptively
- Variable depth
- Tighter bounds

For triangle meshes, **BVH wins**.

### BVH vs KD-Tree

**KD-Tree:**
- Splits space with planes
- Triangles can span multiple nodes (slower build)
- Tighter bounds than BVH

**BVH:**
- Splits geometry into disjoint sets
- Faster to build
- Simpler to implement

For ray tracing, KD-Trees are theoretically better.

In practice, **SAH BVH** is competitive and much easier to build.

### BVH vs Grid

**Uniform Grid:**
- O(1) lookup for point queries
- Poor for raycasting (must check many cells)
- Fixed memory cost

**BVH:**
- O(log n) lookup
- Excellent for raycasting
- Adaptive memory

For general spatial queries on meshes, **BVH wins**.

---

## Tips and Pitfalls

### ✅ Do

- **Use SAH for static geometry**  
  Build once, query thousands of times

- **Enable `firstHitOnly` for raycasting**  
  ```javascript
  raycaster.firstHitOnly = true;
  ```

- **Refit the BVH for dynamic geometry**  
  ```javascript
  // After modifying vertex positions:
  geom.computeBoundingBox();
  geom.boundsTree.refit();
  ```

- **Use `shapecast` for custom queries**  
  It's faster than iterating triangles manually

### ❌ Don't

- **Don't modify the index buffer after building**  
  The BVH assumes the index order matches the tree

- **Don't forget to dispose**  
  ```javascript
  geom.disposeBoundsTree();
  ```

- **Don't build a BVH for small meshes (<100 triangles)**  
  The overhead isn't worth it

- **Don't use CENTER for highly irregular geometry**  
  You'll get unbalanced trees

---

## What We Learned

A BVH is a binary tree of bounding boxes.

It turns O(n) queries into O(log n).

three-mesh-bvh provides:
- Three splitting strategies (CENTER, AVERAGE, SAH)
- Fast raycasting (`raycast`, `raycastFirst`)
- Flexible spatial queries (`shapecast`)
- GPU-friendly data layout
- Async generation
- Dynamic refitting

It's the engine behind:
- [three-gpu-pathtracer](https://github.com/gkjohnson/three-gpu-pathtracer) (photorealistic rendering)
- [three-bvh-csg](https://github.com/gkjohnson/three-bvh-csg) (constructive solid geometry)
- Character controllers
- Collision systems
- Selection tools
- Voxelizers

It makes complex 3D interactions **real-time**.

---

## Further Reading

**Foundational Papers:**

- ["On building fast kd-Trees for Ray Tracing, and on doing that in O(N log N)"](https://www.sci.utah.edu/~wald/Publications/2006/fastbuild/fastbuild.pdf) – Ingo Wald & Vlastimil Havran, 2006  
  Introduces SAH-based splitting

- ["Fast BVH Construction on GPUs"](https://research.nvidia.com/publication/2013-07_fast-bvh-construction-gpus) – Tero Karras & Timo Aila, 2013  
  GPU-parallel BVH construction

**three-mesh-bvh Resources:**

- [GitHub Repository](https://github.com/gkjohnson/three-mesh-bvh)
- [Live Examples](https://gkjohnson.github.io/three-mesh-bvh/example/bundle/raycast.html)
- [API Documentation](https://github.com/gkjohnson/three-mesh-bvh#api)

**Related Projects:**

- [Embree (Intel)](https://www.embree.org/) – Production ray tracing kernels
- [OptiX (NVIDIA)](https://developer.nvidia.com/optix) – GPU ray tracing framework
- [Radeon Rays (AMD)](https://gpuopen.com/radeon-rays/) – Open-source GPU ray tracing

---

**Every complex 3D interaction is a spatial query.**

**Every spatial query is geometry.**

**Accelerate the geometry.**

**Accelerate the world.**
