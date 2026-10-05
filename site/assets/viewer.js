// STL viewer for design pages. three.js is imported only after the visitor
// opens the 3D view, so the page itself loads only the preview image.

const section = document.querySelector('[data-viewer]');

if (section) {
  const stage = section.querySelector('.viewer-stage');
  const startButton = section.querySelector('.viewer-start');
  const partButtons = [...section.querySelectorAll('button[data-stl]')];
  const info = section.querySelector('.viewer-info');
  const defaultInfo = info.textContent;
  let viewerPromise = null;
  let request = 0;

  const selected = () => partButtons.find((b) => b.getAttribute('aria-pressed') === 'true') ?? partButtons[0];

  const open = () => {
    viewerPromise ??= createViewer(stage, info).catch((error) => {
      viewerPromise = null;
      throw error;
    });
    return viewerPromise;
  };

  const show = async (button) => {
    const id = ++request;
    for (const other of partButtons) other.setAttribute('aria-pressed', String(other === button));
    startButton.disabled = true;
    info.textContent = 'Loading the 3D viewer…';
    try {
      const viewer = await open();
      startButton.hidden = true;
      await viewer.load(button.dataset.stl, defaultInfo, () => id === request);
    } catch (error) {
      if (id !== request) return;
      startButton.disabled = false;
      info.textContent = `Could not show ${button.dataset.stl}: ${error.message}`;
    }
  };

  startButton.addEventListener('click', () => show(selected()));
  for (const button of partButtons) {
    button.addEventListener('click', () => show(button));
  }
}

async function createViewer(stage, info) {
  const THREE = await import('three');
  const { STLLoader } = await import('three/addons/loaders/STLLoader.js');
  const { OrbitControls } = await import('three/addons/controls/OrbitControls.js');

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(getComputedStyle(stage).backgroundColor);

  // STL files from CAD use Z as the vertical axis.
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 10000);
  camera.up.set(0, 0, 1);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f96, 2.2));
  const keyLight = new THREE.DirectionalLight(0xffffff, 1.6);
  camera.add(keyLight);
  keyLight.position.set(1, 1, 2);
  scene.add(camera);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  const material = new THREE.MeshStandardMaterial({ color: 0x4f8fd6, roughness: 0.6, metalness: 0.0 });
  const loader = new STLLoader();
  let mesh = null;
  let grid = null;

  stage.replaceChildren(renderer.domElement);

  const resize = () => {
    const { clientWidth: width, clientHeight: height } = stage;
    if (width === 0 || height === 0) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(stage);
  resize();

  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });

  const frame = (box) => {
    const size = box.getSize(new THREE.Vector3());
    const radius = size.length() / 2;
    const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2));
    camera.near = distance / 100;
    camera.far = distance * 100;
    camera.position.set(distance * 0.6, -distance * 0.75, distance * 0.45);
    camera.updateProjectionMatrix();
    controls.target.set(0, 0, size.z / 2);
    controls.update();
  };

  return {
    async load(url, hint, isCurrent) {
      info.textContent = `Loading ${url}…`;
      const geometry = await loader.loadAsync(url, (event) => {
        if (event.lengthComputable && isCurrent()) {
          info.textContent = `Loading ${url}… ${Math.round((event.loaded / event.total) * 100)} %`;
        }
      });
      if (!isCurrent()) {
        geometry.dispose();
        return;
      }
      geometry.computeBoundingBox();
      const box = geometry.boundingBox;
      const center = box.getCenter(new THREE.Vector3());
      // Center in X and Y and place the lowest point on the grid.
      geometry.translate(-center.x, -center.y, -box.min.z);
      geometry.computeBoundingBox();
      if (!geometry.hasAttribute('normal')) geometry.computeVertexNormals();

      if (mesh) {
        scene.remove(mesh);
        mesh.geometry.dispose();
      }
      if (grid) {
        scene.remove(grid);
        grid.geometry.dispose();
      }
      mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);

      const size = geometry.boundingBox.getSize(new THREE.Vector3());
      const span = Math.ceil(Math.max(size.x, size.y) * 1.4 / 10) * 10;
      grid = new THREE.GridHelper(span, span / 10, 0x888888, 0xbbbbbb);
      grid.rotation.x = Math.PI / 2;
      scene.add(grid);
      frame(geometry.boundingBox);

      const dims = [size.x, size.y, size.z].map((v) => v.toFixed(1)).join(' × ');
      info.textContent = `${url}: ${dims} mm (X × Y × Z, grid 10 mm). ${hint}`;
    },
  };
}
