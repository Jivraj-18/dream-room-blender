# Dream Room — four editable reconstructions

Four rooms authored in Blender 5.2.2 LTS from the supplied reference board:

| Room | Editable Blender file | Still render | Browser model |
|---|---|---|---|
| 01 Simple | `scenes/01_simple.blend` | `renders/01_simple.png` | `viewer/models/01_simple.glb` |
| 02 Comfort | `scenes/02_comfort.blend` | `renders/02_comfort.png` | `viewer/models/02_comfort.glb` |
| 03 Studio | `scenes/03_studio.blend` | `renders/03_studio.png` | `viewer/models/03_studio.glb` |
| 04 Dream | `scenes/04_dream.blend` | `renders/04_dream.png` | `viewer/models/04_dream.glb` |

`renders/overview.png` is a labeled contact sheet of actual Blender renders.

These are interpreted reconstructions, not the recovered original scenes. Room dimensions are assumed to be 6.4 × 5.5 × 3.06 metres. Hidden geometry, furniture construction, small decorations, textile folds, plants and artwork are approximate. All four use the same architectural layout and main camera so their progression is comparable.

Interior objects are genuine geometry. Bedding and curtains use authored meshes, not cloth simulation. The distant greenery seen through the window is a flat backdrop sampled from the supplied reference; the outside forest is not modeled. The source image is packed into each Blender scene. No paid assets, external model-generation service, or additional model API was used. Existing Codex-session usage was not measured as a reconciled monetary bill.

## Open and edit in Blender

From `/home/jivraj/experiments/blender`:

```bash
./blender dream_rooms/scenes/04_dream.blend
```

Room objects are organized into Architecture, Furniture, Textiles, Plants and Decor collections. Render lights, the camera and the studio ground have separate collections. Objects are individually named and editable; modifiers remain in the Blender source.

## Explore in a browser

Serve the static viewer over HTTP, rather than opening `index.html` directly:

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory dream_rooms/viewer
```

Open **http://127.0.0.1:8765/**.

- Choose any of the four rooms.
- Orbit: drag to rotate, scroll/pinch to zoom, right-drag to pan.
- Walk inside: drag to look; use WASD/arrow keys or the onscreen buttons to move.
- Double-click the floor in walk mode to move to an unobstructed location.
- Click an object to see its name and collection, with a bounding-box highlight.
- Hide/show the side walls for inspection.
- Download the selected room's GLB.

Walkthrough collision is a basic check against selected furniture bounds and the room perimeter, not a complete physics engine. Doors are visual reconstructions, not functioning exit passages. The viewer uses baked base-color textures and its own light rig; it does not reproduce the Cycles still renders exactly. Procedural micro-bump is omitted from GLB, and base-color baking uses a canonical UV plane rather than an individual bake for every object.

Geometry is batched for rendering while retaining originals for object inspection. Rendering pauses when the view is idle. Browser speed depends on WebGL support, hardware and room complexity; no frame-rate guarantee is made. Walk mode is a viewer feature, not a rigged-player simulation.

## GitHub Pages

The **contents of `viewer/`** form a self-contained static site: HTML, CSS, JavaScript, vendor modules, posters and GLB models. No backend, API token, npm build or paid service is required. Published repository: [Jivraj-18/dream-room-blender](https://github.com/Jivraj-18/dream-room-blender). Explore all four rooms at [the live GitHub Pages viewer](https://jivraj-18.github.io/dream-room-blender/).

To publish using an existing public repository, put those contents into its root or a `docs/` folder. In repository **Settings → Pages**, choose deployment from the relevant branch and folder. Preserve the relative `models/`, `posters/` and `vendor/` paths. See [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).

Three.js **0.180.0** is bundled locally; its MIT license is preserved in `viewer/vendor/THREE-LICENSE.txt`. The viewer does not fetch runtime modules from a CDN. GLB 2.0 models include their image resources.

## Rebuild

```bash
./blender --background --factory-startup --python-exit-code 1 \
  --python dream_rooms/build_rooms.py -- --room 4

./blender --background dream_rooms/scenes/04_dream.blend \
  --python-exit-code 1 --python dream_rooms/export_browser.py -- --room 4
```

Use `--room 1`, `2`, `3` or `4`. Add `--preview` to the builder for a smaller 16-sample render. Final renders use CPU Cycles with 64 samples and denoising. Browser export operates on a working scene copy and does not replace the editable Blender file.

`finalize_scene.py -- --diagnostic` renders a supplementary side view with the left wall temporarily hidden, without saving those inspection changes to the source.

## Verification and evidence

- All four Blender scenes were authored and rendered successfully on CPU.
- Final `.blend` files were reopened for export.
- All four GLBs loaded in the browser; object counts matched their export manifests.
- Room selection, walkthrough entry/movement, return to orbit, side-wall hiding and object picking were exercised.
- A Simple-room cube was successfully picked and identified.
- The Dream room has an additional side-view render in `evidence/04_dream_side.png`.
- Model bounds, embedded resources, GLB headers and file sizes are recorded in `evidence/artifact-verification.json`.

The self-review corrected an overly flat camera, duvet/throw intersections, the loose blanket's overlap with underlying textiles, browser name sanitization and unnecessary idle rendering. This was one Codex session with visual inspection, not an independently judged or repeated research benchmark. No numeric reconstruction accuracy or production-readiness score is claimed.
