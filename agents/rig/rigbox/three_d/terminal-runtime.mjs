// Same pinned Three/GLTF/Meshopt/KTX2 stack as Rig's existing review viewer.
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {KTX2Loader} from 'three/addons/loaders/KTX2Loader.js';
import {MeshoptDecoder} from 'three/addons/libs/meshopt_decoder.module.js';

export async function createStage(canvas, bytes, reducedMotion = false) {
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true});
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.5));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(35, 1, .001, 1000);
  scene.add(new THREE.HemisphereLight(0xf0f7ff, 0x263e66, 3));
  for (const [colour, strength, position] of [[0xffffff, 4, [2, 3, 4]], [0x76aaff, 3, [-3, 1, -2]]]) {
    const light = new THREE.DirectionalLight(colour, strength); light.position.set(...position); scene.add(light);
  }
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true; controls.dampingFactor = .08; controls.enablePan = false;
  controls.autoRotate = !reducedMotion; controls.autoRotateSpeed = .6;
  const manager = new THREE.LoadingManager();
  manager.setURLModifier(url => { if (url.startsWith('blob:')) return url; throw Error('External model resources are not allowed'); });
  const textures = new KTX2Loader().setTranscoderPath(new URL('preview/basis/', import.meta.url).href).detectSupport(renderer);
  const loader = new GLTFLoader(manager).setMeshoptDecoder(MeshoptDecoder).setKTX2Loader(textures);
  let frame = 0, destroyed = false, observer, last = 0, frames = 0;
  const wires = [], materials = [];
  function dispose() {
    destroyed = true; cancelAnimationFrame(frame); observer?.disconnect(); controls.dispose();
    scene.traverse(object => {
      object.geometry?.dispose();
      for (const material of [].concat(object.material || [])) {
        for (const value of Object.values(material)) if (value?.isTexture) value.dispose();
        material.dispose();
      }
    });
    // The terminal reuses one canvas while cycling approved builds. Dispose
    // GPU resources without invalidating the context needed by the next model.
    textures.dispose(); renderer.dispose();
  }
  try {
    const {scene: object} = await loader.parseAsync(bytes, '');
    scene.add(object);
    const box = new THREE.Box3().setFromObject(object), size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.length() / 2, .001), centre = box.getCenter(new THREE.Vector3());
    object.position.sub(centre);
    camera.near = radius / 100; camera.far = radius * 100;
    controls.minDistance = radius * 1.2; controls.maxDistance = radius * 12;
    object.traverse(mesh => {
      if (!mesh.isMesh) return;
      for (const material of [].concat(mesh.material)) {
        materials.push({material, opacity: material.opacity, transparent: material.transparent});
        if (!reducedMotion) { material.transparent = true; material.opacity = 0; }
      }
      const wire = new THREE.LineSegments(new THREE.WireframeGeometry(mesh.geometry),
        new THREE.LineBasicMaterial({color: 0x77beff, transparent: true, opacity: reducedMotion ? 0 : .9}));
      wire.renderOrder = 2; wires.push(wire); mesh.add(wire);
    });
    const render = () => renderer.render(scene, camera);
    let framed = false;
    const resize = () => {
      const {width, height} = canvas.getBoundingClientRect();
      if (!width || !height) return;
      renderer.setSize(width, height, false); camera.aspect = width / height;
      if (!framed) {
        const angle = THREE.MathUtils.degToRad(camera.fov / 2);
        const distance = radius / Math.sin(Math.atan(Math.tan(angle) * Math.min(camera.aspect, 1))) * 1.2;
        camera.position.set(1, .55, 1.3).normalize().multiplyScalar(distance); framed = true;
      }
      camera.updateProjectionMatrix(); controls.update(); render();
    };
    observer = new ResizeObserver(resize); observer.observe(canvas); resize();
    const start = performance.now();
    canvas.dataset.phase = reducedMotion ? 'solid' : 'wireframe';
    function tick(now) {
      if (destroyed) return;
      const progress = reducedMotion ? 1 : Math.min((now - start) / 1400, 1);
      const smooth = progress * progress * (3 - 2 * progress);
      for (const {material, opacity, transparent} of materials) {
        material.opacity = opacity * smooth;
        if (progress === 1) material.transparent = transparent;
      }
      for (const wire of wires) { wire.material.opacity = (1 - smooth) * .9; wire.visible = progress < 1; }
      canvas.dataset.phase = progress < 1 ? 'wireframe' : 'solid';
      if (!document.hidden) {
        // r160 controls use a nominal frame step; compensate for actual RAF time.
        controls.autoRotateSpeed = .6 * Math.min(Math.max((now - (last || now)) / (1000 / 60), 0), 3);
        controls.update(); render(); frames++;
      }
      last = now; frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return {
      rotate(angle) { camera.position.applyAxisAngle(new THREE.Vector3(0, 1, 0), angle); controls.update(); },
      zoom(factor) { camera.position.setLength(THREE.MathUtils.clamp(camera.position.length() * factor, controls.minDistance, controls.maxDistance)); controls.update(); },
      reduced(value) { reducedMotion = value; controls.autoRotate = !value; },
      stats() { return {frames, position: camera.position.toArray(), drawCalls: renderer.info.render.calls}; },
      dispose,
    };
  } catch (error) { dispose(); throw error; }
}
