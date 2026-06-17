---
title: "Photorealism in the Browser: How GPU Path Tracing Works"
date: 2026-06-17
description: "From ray tracing to path tracing: understanding the physics of light, Monte Carlo integration, and how three-gpu-pathtracer brings offline rendering quality to WebGL"
tags: ["computer-graphics", "rendering", "path-tracing", "webgl", "physically-based-rendering"]
---

# Photorealism in the Browser: How GPU Path Tracing Works

Look at this image:

![Path traced interior scene with global illumination](https://user-images.githubusercontent.com/734200/162287477-96696b18-890b-4c1b-8a73-d662e577cc48.png)

This was rendered in a web browser.

In real-time.

Using WebGL 2.

No pre-baked lighting.

No lightmaps.

No screen-space approximations.

**Physically accurate global illumination.**

This is what [three-gpu-pathtracer](https://github.com/gkjohnson/three-gpu-pathtracer) does.

---

## The Problem with Traditional Rendering

Traditional real-time rendering (rasterization) is fast but **incorrect**.

When you render a scene in Three.js:

```javascript
renderer.render(scene, camera);
```

The GPU:
1. Projects triangles onto the screen
2. Computes lighting at each pixel using **approximations**
3. Renders one frame in 16ms

The approximations:
- **Direct lighting only** – light travels straight from source to surface
- **No inter-reflections** – red wall doesn't tint nearby white wall
- **Ambient occlusion faked** – corners are darkened using heuristics
- **Shadows are binary** – an object is either in shadow or not
- **Reflections are screen-space** – you only see what's already on screen

This produces good-looking images.

But not **physically accurate** images.

---

## How Light Actually Works

In the real world:

Light bounces.

A photon leaves a light source.

It hits a surface.

Some energy is absorbed.

The rest scatters in random directions.

It hits another surface.

Bounces again.

And again.

Until it:
- Reaches your eye (camera)
- Gets absorbed completely
- Escapes the scene

This is called a **light path**.

A single pixel's color is the integral of **all possible light paths** that reach it.

Computing this integral exactly is impossible.

But we can **estimate** it.

---

## Enter Monte Carlo Integration

Monte Carlo integration is a simple idea:

**To estimate an integral, take random samples and average them.**

For a 1D integral:

```
∫[a,b] f(x) dx ≈ (b-a)/N * Σ f(xᵢ)
```

Where each `xᵢ` is a random point in `[a, b]`.

For rendering:

```
Pixel color ≈ (1/N) * Σ trace_random_path()
```

Each path is a random walk through the scene.

Trace 1 path per pixel: **noisy image**
Trace 10 paths per pixel: **less noisy**
Trace 100 paths: **even smoother**
Trace 1000 paths: **converges to ground truth**

The noise decreases at a rate of **1/√N**.

To halve the noise, you need **4x more samples**.

This is why path tracing is expensive.

---

## Path Tracing Algorithm: The Core Loop

```javascript
function tracePixel(x, y, samplesPerPixel) {
    let color = [0, 0, 0];
    
    for (let s = 0; s < samplesPerPixel; s++) {
        // 1. Generate a random ray from the camera through pixel (x, y)
        const ray = camera.generateRay(x + random(), y + random());
        
        // 2. Trace the path
        color = add(color, tracePath(ray));
    }
    
    // 3. Average
    return divide(color, samplesPerPixel);
}

function tracePath(ray, depth = 0, throughput = [1, 1, 1]) {
    if (depth > MAX_BOUNCES) return [0, 0, 0];
    
    // 1. Find the closest intersection
    const hit = scene.intersect(ray);
    
    if (!hit) {
        // Ray escaped: return environment light
        return multiply(environmentMap(ray.direction), throughput);
    }
    
    // 2. Hit a surface: accumulate emission
    let color = multiply(hit.material.emission, throughput);
    
    // 3. Sample a random bounce direction
    const newDirection = hit.material.sampleBSDF(ray.direction, hit.normal);
    const brdf = hit.material.evaluateBSDF(ray.direction, newDirection, hit.normal);
    const pdf = hit.material.pdf(newDirection, hit.normal);
    
    // 4. Update throughput (how much light survives the bounce)
    const newThroughput = multiply(throughput, divide(brdf, pdf));
    
    // 5. Spawn a new ray and continue
    const newRay = { origin: hit.point, direction: newDirection };
    color = add(color, tracePath(newRay, depth + 1, newThroughput));
    
    return color;
}
```

This is the essence of path tracing.

**But there's a problem.**

---

## The Problem: Convergence is Slow

Imagine a scene with a small light source.

Most random bounces miss the light.

You waste computation on dark paths.

Example:

```
Sample 1: miss light → contributes 0
Sample 2: miss light → contributes 0
Sample 3: miss light → contributes 0
Sample 4: HIT LIGHT → contributes 10
Sample 5: miss light → contributes 0
...
```

After 100 samples:
- 95 samples contributed 0
- 5 samples contributed 10 each
- Average: 0.5

High variance = slow convergence = **noisy image**.

The solution: **importance sampling**.

---

## Importance Sampling: Sample What Matters

Instead of choosing random directions uniformly, **bias toward important directions**.

For a diffuse surface (Lambertian BRDF):

**Uniform sampling:**
```javascript
function sampleUniform() {
    const u = random();
    const v = random();
    const theta = acos(sqrt(1 - u));
    const phi = 2 * PI * v;
    return sphericalToCartesian(theta, phi);
}
```

Samples the hemisphere uniformly. PDF = `1 / (2π)`.

**Cosine-weighted sampling:**
```javascript
function sampleCosineWeighted() {
    const u = random();
    const v = random();
    const theta = acos(sqrt(u));
    const phi = 2 * PI * v;
    return sphericalToCartesian(theta, phi);
}
```

Samples directions proportional to `cos(θ)`. PDF = `cos(θ) / π`.

Why does this help?

The Lambertian BRDF is `albedo / π`.

The rendering equation integrates `BRDF * cos(θ) * incomingLight`.

If we sample with PDF = `cos(θ) / π`, the `cos(θ)` terms cancel:

```
color ≈ Σ (BRDF * cos(θ) * L) / PDF
      = Σ (albedo/π * cos(θ) * L) / (cos(θ)/π)
      = Σ albedo * L
```

No more `cos(θ)` in the estimator → **lower variance**.

---

## Multiple Importance Sampling (MIS): The Best of Both Worlds

We can sample:
1. **The BRDF** (material direction)
2. **The lights** (light direction)

Which should we choose?

**Answer: both.**

**BRDF sampling** is good when:
- The surface is very glossy
- The light source is large

**Light sampling** is good when:
- The surface is diffuse
- The light source is small

MIS combines both strategies optimally.

### The Balance Heuristic

Sample the BRDF with probability `p`.

Sample the lights with probability `1 - p`.

Weight each sample by:

```
weight = pdf_i / (pdf_brdf + pdf_light)
```

This is called the **balance heuristic** (Veach & Guibas, 1995).

It's provably close to optimal.

In code:

```javascript
// 1. Sample the light
const lightSample = sampleRandomLight();
const lightDirection = normalize(lightSample.position - hit.point);
const lightPdf = lightSample.pdf;
const brdfPdf = hit.material.pdf(lightDirection);
const misWeight = lightPdf / (lightPdf + brdfPdf);

const shadowRay = { origin: hit.point, direction: lightDirection };
if (!scene.intersect(shadowRay, lightSample.distance)) {
    const brdf = hit.material.evaluate(lightDirection);
    color += brdf * lightSample.emission * misWeight / lightPdf;
}

// 2. Sample the BRDF
const brdfDirection = hit.material.sample();
const brdfPdf2 = hit.material.pdf(brdfDirection);
const lightPdf2 = scene.pdfLight(brdfDirection); // If we hit a light
const misWeight2 = brdfPdf2 / (brdfPdf2 + lightPdf2);

const brdfRay = { origin: hit.point, direction: brdfDirection };
const brdfHit = scene.intersect(brdfRay);
if (brdfHit && brdfHit.material.emission > 0) {
    color += brdfHit.material.emission * misWeight2 / brdfPdf2;
}
```

Result: **significantly faster convergence**.

---

## How three-gpu-pathtracer Works

### 1. Scene Setup

```javascript
import * as THREE from 'three';
import { WebGLPathTracer } from 'three-gpu-pathtracer';

const renderer = new THREE.WebGLRenderer();
renderer.toneMapping = THREE.ACESFilmicToneMapping;

const pathTracer = new WebGLPathTracer(renderer);
pathTracer.tiles.set(3, 3);  // Render in 3x3 tiles for responsiveness
pathTracer.bounces = 10;      // Max bounces per path
pathTracer.setScene(scene, camera);

function animate() {
    requestAnimationFrame(animate);
    pathTracer.renderSample();  // Accumulate one more sample
}

animate();
```

### 2. BVH Construction

Before tracing, the scene is converted into a BVH (using three-mesh-bvh).

All geometry is flattened into:
- A single index buffer
- A single vertex buffer
- A single normal buffer
- A single UV buffer
- Texture atlases

The BVH is uploaded to the GPU as textures.

### 3. GPU Shader: The Path Tracer

The core algorithm runs entirely in a fragment shader.

**Vertex Shader** (simple):
```glsl
varying vec2 vUv;

void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
```

**Fragment Shader** (complex):
```glsl
uniform sampler2D bvhTexture;
uniform sampler2D triangleTexture;
uniform sampler2D materialTexture;
uniform sampler2D lightTexture;
uniform sampler2D envMap;
uniform int seed;
uniform int bounces;
uniform int sample;

varying vec2 vUv;

// Random number generator (using seed + pixel position + sample count)
float rand(int i) {
    return fract(sin(float(seed + i) * 12.9898 + float(gl_FragCoord.x) * 78.233 + float(gl_FragCoord.y) * 45.543) * 43758.5453);
}

vec3 traceScene(Ray ray, inout SurfaceHit hit) {
    // BVH traversal
    bool didHit = bvhIntersectFirstHit(
        bvhTexture, 
        ray.origin, 
        ray.direction, 
        hit.faceIndex, 
        hit.faceNormal, 
        hit.barycoord, 
        hit.distance
    );
    
    if (!didHit) {
        return texture2D(envMap, directionToEquirect(ray.direction)).rgb;
    }
    
    return vec3(0.0); // Continue path
}

vec3 directLightContribution(vec3 rayOrigin, SurfaceRecord surf) {
    vec3 result = vec3(0.0);
    
    // Sample a random light
    LightRecord lightRec = randomLightSample(rayOrigin);
    
    // Check visibility
    Ray shadowRay;
    shadowRay.origin = rayOrigin;
    shadowRay.direction = lightRec.direction;
    
    SurfaceHit shadowHit;
    traceScene(shadowRay, shadowHit);
    
    if (shadowHit.distance > lightRec.distance) {
        // Not in shadow: compute contribution
        vec3 brdf = evaluateBSDF(surf, lightRec.direction);
        float lightPdf = lightRec.pdf;
        float brdfPdf = pdfBSDF(surf, lightRec.direction);
        
        // MIS weight
        float misWeight = lightPdf / (lightPdf + brdfPdf);
        
        result = brdf * lightRec.emission * misWeight / lightPdf;
    }
    
    return result;
}

void main() {
    // Generate camera ray
    Ray ray = getCameraRay(vUv);
    
    vec3 color = vec3(0.0);
    vec3 throughput = vec3(1.0);
    
    for (int i = 0; i < bounces; i++) {
        SurfaceHit hit;
        vec3 envColor = traceScene(ray, hit);
        
        if (hit.distance == INFINITY) {
            // Hit environment
            color += throughput * envColor;
            break;
        }
        
        // Get surface properties
        SurfaceRecord surf = getSurfaceRecord(hit);
        
        // Add emission
        color += throughput * surf.emission;
        
        // Direct lighting (MIS)
        color += throughput * directLightContribution(hit.point, surf);
        
        // Sample next bounce
        vec3 direction = sampleBSDF(surf);
        vec3 brdf = evaluateBSDF(surf, direction);
        float pdf = pdfBSDF(surf, direction);
        
        throughput *= brdf / pdf;
        
        // Russian roulette
        float p = max(throughput.r, max(throughput.g, throughput.b));
        if (rand(i) > p) break;
        throughput /= p;
        
        // Spawn new ray
        ray.origin = hit.point + hit.normal * 0.001;
        ray.direction = direction;
    }
    
    gl_FragColor = vec4(color, 1.0);
}
```

### 4. Progressive Rendering

Each call to `renderSample()`:
1. Renders one sample per pixel
2. Blends it with previous samples:
   ```
   newColor = (oldColor * sampleCount + newSample) / (sampleCount + 1)
   ```
3. Displays to canvas

After 100 frames, you have 100 samples per pixel.

After 1000 frames, 1000 samples.

The image converges over time.

---

## Key Features

### 1. GGX Microfacet BRDF

Realistic metals and plastics.

The BRDF:

```glsl
float D_GGX(float NdotH, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float denom = (NdotH * NdotH * (a2 - 1.0) + 1.0);
    return a2 / (PI * denom * denom);
}

float G_Smith(float NdotV, float NdotL, float roughness) {
    float k = (roughness + 1.0) * (roughness + 1.0) / 8.0;
    float gl = NdotL / (NdotL * (1.0 - k) + k);
    float gv = NdotV / (NdotV * (1.0 - k) + k);
    return gl * gv;
}

vec3 F_Schlick(float VdotH, vec3 F0) {
    return F0 + (1.0 - F0) * pow(1.0 - VdotH, 5.0);
}

vec3 GGX_BRDF(vec3 V, vec3 L, vec3 N, float roughness, vec3 F0) {
    vec3 H = normalize(V + L);
    float NdotV = max(dot(N, V), 0.0);
    float NdotL = max(dot(N, L), 0.0);
    float NdotH = max(dot(N, H), 0.0);
    float VdotH = max(dot(V, H), 0.0);
    
    float D = D_GGX(NdotH, roughness);
    float G = G_Smith(NdotV, NdotL, roughness);
    vec3 F = F_Schlick(VdotH, F0);
    
    return (D * G * F) / max(4.0 * NdotV * NdotL, 0.001);
}
```

### 2. Importance Sampling GGX

Sample directions proportional to the GGX lobe:

```glsl
vec3 sampleGGX(vec3 N, float roughness, vec2 uv) {
    float a = roughness * roughness;
    
    float phi = 2.0 * PI * uv.x;
    float cosTheta = sqrt((1.0 - uv.y) / (1.0 + (a * a - 1.0) * uv.y));
    float sinTheta = sqrt(1.0 - cosTheta * cosTheta);
    
    vec3 H;
    H.x = sinTheta * cos(phi);
    H.y = sinTheta * sin(phi);
    H.z = cosTheta;
    
    // Transform to world space
    vec3 up = abs(N.z) < 0.999 ? vec3(0, 0, 1) : vec3(1, 0, 0);
    vec3 tangent = normalize(cross(up, N));
    vec3 bitangent = cross(N, tangent);
    
    return tangent * H.x + bitangent * H.y + N * H.z;
}
```

### 3. Physical Camera

Depth of field with aperture simulation:

```javascript
import { PhysicalCamera } from 'three-gpu-pathtracer';

const camera = new PhysicalCamera(45, aspect, 0.1, 100);
camera.focusDistance = 10;  // Focus 10 units away
camera.fStop = 1.4;         // Wide aperture (shallow DOF)
camera.apertureBlades = 6;  // Hexagonal bokeh
```

Rays are jittered across the aperture:

```glsl
vec3 getCameraRay(vec2 uv) {
    // Jitter within pixel
    uv += vec2(rand(0), rand(1)) / resolution;
    
    // NDC to world
    vec4 near = inverseProjection * vec4(uv * 2.0 - 1.0, -1.0, 1.0);
    vec4 far = inverseProjection * vec4(uv * 2.0 - 1.0, 1.0, 1.0);
    
    near.xyz /= near.w;
    far.xyz /= far.w;
    
    vec3 direction = normalize(far.xyz - near.xyz);
    
    // Depth of field: jitter origin across aperture
    vec2 apertureSample = sampleAperture(rand(2), rand(3));
    vec3 focalPoint = near.xyz + direction * focusDistance;
    vec3 origin = near.xyz + apertureSample.x * right + apertureSample.y * up;
    direction = normalize(focalPoint - origin);
    
    return Ray(origin, direction);
}
```

### 4. Area Lights

Soft shadows:

```javascript
const light = new THREE.RectAreaLight(0xffffff, 10, 2, 2);
light.position.set(0, 5, 0);
scene.add(light);
```

Sampled uniformly:

```glsl
LightRecord randomAreaLightSample(Light light, vec3 rayOrigin) {
    // Random point on rectangle
    vec3 randomPos = light.position 
                   + light.u * (rand(0) - 0.5) 
                   + light.v * (rand(1) - 0.5);
    
    vec3 toLight = randomPos - rayOrigin;
    float distSq = dot(toLight, toLight);
    float dist = sqrt(distSq);
    vec3 direction = toLight / dist;
    
    vec3 normal = normalize(cross(light.u, light.v));
    float pdf = distSq / (light.area * abs(dot(direction, normal)));
    
    return LightRecord(dist, direction, pdf, light.color * light.intensity);
}
```

### 5. Environment Map Importance Sampling

Instead of sampling the environment uniformly, build a **probability distribution** over the map.

1. Compute luminance for each pixel
2. Build a 2D CDF (cumulative distribution function)
3. Sample using binary search

```glsl
vec3 sampleEnvironment(vec2 uv, out float pdf) {
    // Sample the CDF to find (theta, phi)
    vec2 coord = sampleCDF(uv);
    
    // Convert to direction
    float theta = coord.y * PI;
    float phi = coord.x * 2.0 * PI;
    vec3 direction = sphericalToCartesian(theta, phi);
    
    // PDF proportional to luminance
    pdf = textureLuminance(coord) / totalLuminance;
    
    return texture2D(envMap, coord).rgb;
}
```

Bright areas (sun) are sampled more often than dark areas (sky).

### 6. Volumetric Fog

Participating media:

```javascript
scene.fog = new THREE.Fog(0x000000, 1, 50);
scene.fog.density = 0.01;
```

At each step, test if the ray scatters inside the volume:

```glsl
float intersectFogVolume(Material fogMaterial, float xi) {
    // Sample distance using Beer's law
    float density = fogMaterial.density;
    return -log(1.0 - xi) / density;
}
```

If scatter distance < surface distance, spawn a new ray:

```glsl
if (fogDistance < hit.distance) {
    // Scattered inside fog
    vec3 scatterPoint = ray.origin + ray.direction * fogDistance;
    vec3 scatterDirection = sampleSphere(rand(0), rand(1));
    
    ray.origin = scatterPoint;
    ray.direction = scatterDirection;
    
    throughput *= fogMaterial.albedo;
}
```

---

## Performance: Tiled Rendering

Rendering the full frame every sample is slow.

**Solution: tiled rendering.**

Divide the frame into tiles (e.g., 3×3 = 9 tiles).

Render one tile per frame.

After 9 frames, the entire image has one more sample.

```javascript
pathTracer.tiles.set(3, 3);
```

This keeps the page responsive.

You see **progressive updates** instead of a frozen frame.

---

## Performance: Dynamic Low-Res Preview

While the full-res image renders, also render a **low-res preview**:

```javascript
pathTracer.dynamicLowRes = true;
pathTracer.lowResScale = 0.25; // 1/4 resolution
```

The preview:
- Renders at 25% scale (16x fewer pixels)
- Converges 16x faster
- Gives instant feedback while the full image accumulates

---

## Performance: Denoising

Path tracing is noisy at low sample counts.

**Option 1: Denoise in post-processing**

Use an AI denoiser (e.g., Intel Open Image Denoise, OptiX Denoiser).

**Option 2: Adaptive sampling**

Allocate more samples to noisy regions.

Measure variance per tile.

Render high-variance tiles more.

three-gpu-pathtracer doesn't include a built-in denoiser yet, but you can:

1. Render to a render target
2. Pass it to a denoising shader
3. Display the denoised result

---

## Real-World Example: Interior Scene

```javascript
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { WebGLPathTracer, PhysicalCamera, PhysicalSpotLight } from 'three-gpu-pathtracer';

// Load scene
const loader = new GLTFLoader();
const gltf = await loader.loadAsync('interior.glb');
scene.add(gltf.scene);

// Setup camera
const camera = new PhysicalCamera(50, aspect, 0.1, 100);
camera.position.set(0, 1.6, 3);
camera.focusDistance = 5;
camera.fStop = 2.8;

// Add area light (window)
const sunlight = new THREE.RectAreaLight(0xffffee, 50, 3, 2);
sunlight.position.set(2, 3, 0);
sunlight.lookAt(0, 0, 0);
scene.add(sunlight);

// Add spot light (lamp)
const lamp = new PhysicalSpotLight(0xffaa77, 10, 10, Math.PI / 6, 0.3);
lamp.position.set(-1, 2, 1);
lamp.radius = 0.05; // Soft shadows
scene.add(lamp);

// Environment
const envMap = await new RGBELoader().loadAsync('studio.hdr');
scene.environment = envMap;
scene.background = envMap;

// Path tracer
const renderer = new THREE.WebGLRenderer({ antialias: false });
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;

const pathTracer = new WebGLPathTracer(renderer);
pathTracer.tiles.set(2, 2);
pathTracer.bounces = 5;
pathTracer.filterGlossyFactor = 0.5; // Reduce fireflies
pathTracer.setScene(scene, camera);

// Render
function animate() {
    requestAnimationFrame(animate);
    
    if (pathTracer.samples < 1000) {
        pathTracer.renderSample();
        stats.textContent = `Samples: ${pathTracer.samples}`;
    }
}

animate();
```

After 100 samples: recognizable but noisy
After 500 samples: smooth, photorealistic
After 1000 samples: nearly converged

**Live demo:** [Interior Scene](https://gkjohnson.github.io/three-gpu-pathtracer/example/bundle/interior.html)

---

## Comparison: Rasterization vs Path Tracing

| Feature | Rasterization | Path Tracing |
|---------|---------------|--------------|
| **Speed** | ~16ms/frame | ~1000ms for convergence |
| **Quality** | Approximate | Physically accurate |
| **Global Illumination** | Baked or faked | Real-time, dynamic |
| **Soft Shadows** | Shadow maps (artifacts) | Naturally soft |
| **Caustics** | Not supported | Emerges naturally |
| **Depth of Field** | Post-process blur | Physically accurate |
| **Reflections** | Screen-space only | Infinite bounces |
| **Materials** | Empirical models | Physically based |

Path tracing is **slower but correct**.

Rasterization is **faster but approximate**.

The future is hybrid:
- Rasterize primary visibility
- Path trace indirect lighting
- Denoise aggressively

(This is what RTX and AMD's ray tracing APIs do.)

---

## The Math: The Rendering Equation

Everything we've discussed is solving this integral:

```
L_o(x, ω_o) = L_e(x, ω_o) + ∫_Ω f_r(x, ω_i, ω_o) L_i(x, ω_i) cos(θ_i) dω_i
```

Where:
- `L_o(x, ω_o)` = outgoing radiance at point `x` in direction `ω_o`
- `L_e(x, ω_o)` = emitted radiance (if `x` is a light)
- `f_r(x, ω_i, ω_o)` = BRDF (how much light from `ω_i` reflects to `ω_o`)
- `L_i(x, ω_i)` = incoming radiance from direction `ω_i`
- `cos(θ_i)` = Lambert's cosine law
- `Ω` = hemisphere above `x`

This is a **recursive integral** (because `L_i` depends on `L_o` at other points).

Path tracing solves it via **Monte Carlo**:

```
L_o ≈ L_e + (1/N) Σ [f_r * L_i * cos(θ) / pdf]
```

Each sample = one random direction `ω_i`.

---

## Optimizations in three-gpu-pathtracer

### 1. Russian Roulette

Instead of always tracing to `MAX_BOUNCES`, **probabilistically terminate** paths.

At each bounce, compute the throughput:

```glsl
float p = max(throughput.r, max(throughput.g, throughput.b));
if (rand() > p) break;
throughput /= p;
```

Low-energy paths terminate early.

High-energy paths continue.

**Unbiased** (the expected value is still correct).

### 2. Next Event Estimation (NEE)

At every bounce, **explicitly sample the lights** (in addition to BRDF sampling).

This ensures every path contributes light (instead of relying on randomly hitting a light).

Combined with MIS, this is **much faster** than naive path tracing.

### 3. Texture Atlasing

All textures are packed into a **single texture array**.

Avoids texture binding overhead in shaders.

All materials share one atlas.

### 4. SharedArrayBuffer for BVH Generation

Building the BVH can be slow (100ms+ for large scenes).

three-gpu-pathtracer uses Web Workers:

```javascript
import { GenerateMeshBVHWorker } from 'three-mesh-bvh/worker';

const worker = new GenerateMeshBVHWorker();
await worker.generate(geometry, { strategy: SAH });
```

On systems with `SharedArrayBuffer` support, uses **parallel BVH construction**.

---

## Limitations

### 1. WebGL Constraints

- No recursion in GLSL → simulate via iterative loops
- Limited texture units → atlas everything
- No ray tracing hardware acceleration (yet)

**WebGPU** will improve this (three-gpu-pathtracer has experimental WebGPU support).

### 2. Convergence Time

1000 samples can take minutes.

For production, you'd render offline or use denoising.

### 3. Caustics and Fireflies

Bright specular highlights (caustics) cause **fireflies** (single-pixel noise).

`filterGlossyFactor` helps but removes some caustics.

Proper solution: **bidirectional path tracing** or **photon mapping** (not yet implemented).

### 4. Memory

Large scenes consume lots of GPU memory:
- BVH structure
- Geometry buffers
- Texture atlases
- Material data
- Light data

Practical limit: ~50M triangles.

---

## Use Cases

### ✅ Ideal For

- Product visualization (jewelry, cars, furniture)
- Architectural previews
- Material design (verify PBR materials)
- Lighting studies
- Film/VFX previsualization
- Educational rendering demos

### ❌ Not Ideal For

- Real-time games (too slow)
- Mobile devices (no WebGL 2 / limited memory)
- Huge scenes (> 50M triangles)

---

## The Future

Path tracing is becoming mainstream:

**Hardware:**
- RTX GPUs (dedicated ray tracing cores)
- Apple Silicon (optimized for ray tracing)
- Consoles (PS5, Xbox Series X)

**Software:**
- Unreal Engine 5 (Lumen = hybrid path tracing)
- Unity (Progressive GPU Lightmapper)
- Blender Cycles (GPU path tracing since 2011)

**Web:**
- WebGPU (compute shaders, better performance)
- Neural denoising in the browser (WASM + WebGL)
- Real-time path tracing at 60fps (with aggressive denoising)

three-gpu-pathtracer is **ahead of the curve**.

It's production-ready today.

And it will only get faster.

---

## What We Learned

Path tracing is the **correct** way to render.

It simulates physics.

Light bounces.

Shadows soften.

Colors bleed.

Caustics emerge.

Everything is an integral.

Monte Carlo estimates the integral.

Importance sampling reduces variance.

MIS combines strategies optimally.

The GPU parallelizes millions of paths.

BVH acceleration makes it tractable.

Progressive rendering makes it interactive.

Convergence is slow but inevitable.

The result is **photorealism**.

---

## Try It Yourself

**Quick start:**

```bash
npm install three three-gpu-pathtracer
```

```javascript
import * as THREE from 'three';
import { WebGLPathTracer } from 'three-gpu-pathtracer';

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 100);

// Add geometry
const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(1, 64, 64),
    new THREE.MeshStandardMaterial({ 
        color: 0xff0000, 
        metalness: 0.0, 
        roughness: 0.2 
    })
);
scene.add(sphere);

// Add light
const light = new THREE.RectAreaLight(0xffffff, 10, 2, 2);
light.position.set(0, 3, 0);
scene.add(light);

// Path trace
const renderer = new THREE.WebGLRenderer();
const pathTracer = new WebGLPathTracer(renderer);
pathTracer.setScene(scene, camera);

function animate() {
    requestAnimationFrame(animate);
    pathTracer.renderSample();
}

animate();
```

**Live examples:**

- [Basic Setup](https://gkjohnson.github.io/three-gpu-pathtracer/example/bundle/basic.html)
- [Material Ball](https://gkjohnson.github.io/three-gpu-pathtracer/example/bundle/materialBall.html)
- [Interior Scene](https://gkjohnson.github.io/three-gpu-pathtracer/example/bundle/interior.html)
- [Depth of Field](https://gkjohnson.github.io/three-gpu-pathtracer/example/bundle/depthOfField.html)
- [Drag & Drop Viewer](https://gkjohnson.github.io/three-gpu-pathtracer/example/bundle/viewer.html)

---

## Further Reading

**Path Tracing:**

- [PBRT Book](https://www.pbr-book.org/) – Physically Based Rendering: From Theory to Implementation (free online)
- [Ray Tracing in One Weekend](https://raytracing.github.io/) – Minimal CPU path tracer in C++
- [Scratchapixel](https://www.scratchapixel.com/) – Rendering tutorials with code

**Monte Carlo:**

- [Veach Thesis (1997)](https://graphics.stanford.edu/papers/veach_thesis/) – The bible of MIS and light transport

**GGX:**

- [Understanding the Masking-Shadowing Function](https://jcgt.org/published/0003/02/03/) – Heitz 2014
- [Importance Sampling Microfacet-Based BSDFs](https://schuttejoe.github.io/post/ggximportancesamplingpart1/) – Joe Schutte

**Projects:**

- [three-mesh-bvh](https://github.com/gkjohnson/three-mesh-bvh) – The BVH library powering this
- [three-gpu-pathtracer](https://github.com/gkjohnson/three-gpu-pathtracer) – The library itself
- [Cycles](https://www.cycles-renderer.org/) – Blender's production path tracer

---

**Rendering is solving an integral.**

**Path tracing is the solution.**

**three-gpu-pathtracer brings it to the web.**

**Photorealism is no longer offline.**

**It's in your browser.**

**Right now.**
