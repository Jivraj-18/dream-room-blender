import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { RoomEnvironment } from './vendor/RoomEnvironment.js';

const $ = id => document.getElementById(id);
const rooms = {
  1:{file:'01_simple',title:'Simple.',description:'The essentials. Warm oak, daylight, and room to begin.'},
  2:{file:'02_comfort',title:'Comfort.',description:'Soft linen, a reading light, and a little green. A room becomes a retreat.'},
  3:{file:'03_studio',title:'Studio.',description:'Books, music, and a place to make things. Everyday objects give the room its character.'},
  4:{file:'04_dream',title:'Dream.',description:'Glass, sculptural brass, and layers of fabric. Familiar space, a richer expression.'}
};
const host = $('canvas-host');
let renderer;
try { renderer = new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'high-performance'}); }
catch(error) { $('loading-text').textContent='This browser could not start WebGL. Try a browser with hardware acceleration enabled.'; throw error; }
renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));
renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate=false;
renderer.shadowMap.needsUpdate=true;
renderer.toneMapping=THREE.AgXToneMapping;
renderer.toneMappingExposure=.9;
host.appendChild(renderer.domElement);
renderer.domElement.setAttribute('aria-label','3D room viewport');
renderer.domElement.setAttribute('tabindex','0');
const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
const env = new RoomEnvironment();
scene.environment = pmrem.fromScene(env,.04).texture;
env.dispose();pmrem.dispose();
scene.add(new THREE.HemisphereLight(0xf2eee1,0x76664d,1.3));
const sun=new THREE.DirectionalLight(0xffe2b3,2.5);
sun.position.set(-3,7,-4);sun.castShadow=true;
sun.shadow.mapSize.set(2048,2048);
Object.assign(sun.shadow.camera,{left:-5,right:5,top:5,bottom:-5,near:.2,far:22});
sun.shadow.bias=-.0007;sun.shadow.normalBias=.025;scene.add(sun);
const fill=new THREE.DirectionalLight(0xe4ecff,1.15);fill.position.set(3,5,7);scene.add(fill);
const ground=new THREE.Mesh(new THREE.PlaneGeometry(80,80),new THREE.MeshStandardMaterial({color:0x171e19,roughness:.96}));
ground.rotation.x=-Math.PI/2;ground.position.y=-.34;ground.receiveShadow=true;scene.add(ground);
const camera=new THREE.PerspectiveCamera(42,1,.03,100);
const controls=new OrbitControls(camera,renderer.domElement);
controls.enableDamping=true;controls.dampingFactor=.07;
controls.minDistance=1.3;controls.maxDistance=23;controls.maxPolarAngle=Math.PI*.49;
const loader=new GLTFLoader();
const cache=new Map();
let currentRoom=1,current=null,mode='orbit',sideWallsHidden=false,request=0,helper=null,needsRender=true;
let yaw=0,pitch=0,pointer=null;
const keys=new Set();
const raycaster=new THREE.Raycaster();
const cursor=new THREE.Vector2();
const wallPattern=/^(Left wall|Right wall)(\.|$)/;
const objectName=obj=>obj.userData.name||obj.name.replaceAll('_',' ');

function resize(){const {width,height}=host.getBoundingClientRect();renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();needsRender=true;}
new ResizeObserver(resize).observe(host);resize();
function orbitView(){camera.position.set(.15,7.6,9.0);controls.target.set(0,1.02,0);controls.update();}
orbitView();
function setMode(next){
  needsRender=true;
  mode=next;controls.enabled=mode==='orbit';keys.clear();
  for(const id of ['orbit','walk']){$(id).classList.toggle('active',(id==='orbit')===(mode==='orbit'));$(id).setAttribute('aria-pressed',String((id==='orbit')===(mode==='orbit')));}
  $('touch-walk').hidden=mode!=='walk';
  $('instructions').textContent=mode==='walk'?'Drag to look · WASD / arrow keys to move · Double-click the floor to go there':'Drag to orbit · Scroll to zoom · Click an object to inspect';
  if(mode==='walk'){
    camera.position.set(-1.35,1.60,2.30);
    yaw=-.52;pitch=0;camera.rotation.order='YXZ';camera.rotation.set(pitch,yaw,0);
  }else{orbitView();}
}
$('orbit').onclick=()=>setMode('orbit');$('walk').onclick=()=>setMode('walk');
$('reset').onclick=()=>setMode(mode);
$('walls').onclick=()=>{
  sideWallsHidden=!sideWallsHidden;
  $('walls').textContent=sideWallsHidden?'Show side walls':'Hide side walls';
  $('walls').setAttribute('aria-pressed',String(sideWallsHidden));applyWalls();
};
function applyWalls(){
  if(!current)return;
  current.batches.children.forEach(o=>{if(o.userData.sideWall)o.visible=!sideWallsHidden;});
  renderer.shadowMap.needsUpdate=true;needsRender=true;
}
function clearSelection(){if(helper){scene.remove(helper);helper.geometry.dispose();helper.material.dispose();helper=null;}$('selection').hidden=true;needsRender=true;}
$('clear-selection').onclick=clearSelection;

function prepare(gltf){
  const root=gltf.scene;root.updateMatrixWorld(true);
  const pickables=[],obstacles=[],buckets=new Map();
  root.traverse(o=>{
    if(!o.isMesh)return;
    pickables.push(o);
    o.castShadow=true;o.receiveShadow=true;
    const isWall=wallPattern.test(objectName(o));
    if(/Bed structural base|Oak desk top|Desk chair seat|Lounge chair lower seat|Fluted upholstered ottoman|Round oak side table top|Circular glass coffee tabletop/.test(objectName(o))){
      const box=new THREE.Box3().setFromObject(o);box.min.x-=.15;box.max.x+=.15;box.min.z-=.15;box.max.z+=.15;obstacles.push(box);
    }
    const geo=o.geometry.clone().applyMatrix4(o.matrixWorld);
    const signature=Object.keys(geo.attributes).sort().map(k=>`${k}:${geo.attributes[k].itemSize}:${geo.attributes[k].array.constructor.name}`).join(',');
    const key=`${o.material.uuid}:${signature}:${isWall}`;
    if(!buckets.has(key))buckets.set(key,{material:o.material,geometries:[],isWall});
    buckets.get(key).geometries.push(geo);
  });
  // Static batching cuts draw calls; originals remain available for exact object picking.
  const batches=new THREE.Group();
  for(const bucket of buckets.values()){
    const geometry=mergeGeometries(bucket.geometries,false);
    if(!geometry)throw new Error('Could not assemble browser geometry');
    const mesh=new THREE.Mesh(geometry,bucket.material);mesh.castShadow=true;mesh.receiveShadow=true;mesh.userData.sideWall=bucket.isWall;batches.add(mesh);
    bucket.geometries.forEach(g=>g.dispose());
  }
  root.visible=false;
  return {root,batches,pickables,obstacles};
}

async function loadRoom(number){
  const token=++request;currentRoom=number;clearSelection();
  const spec=rooms[number];$('room-number').textContent=`ROOM ${String(number).padStart(2,'0')} / 04`;
  $('room-title').textContent=spec.title;$('room-description').textContent=spec.description;
  $('download').href=`models/${spec.file}.glb`;
  document.querySelectorAll('[data-room]').forEach(b=>{const selected=Number(b.dataset.room)===number;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));});
  $('loading').hidden=false;$('loading-text').textContent='Opening the room…';
  try{
    if(!cache.has(number)){
      const gltf=await loader.loadAsync(`models/${spec.file}.glb`,event=>{if(token===request&&event.total)$('loading-text').textContent=`Opening the room… ${Math.round(event.loaded/event.total*100)}%`;});
      cache.set(number,prepare(gltf));
    }
    if(token!==request)return;
    if(current){scene.remove(current.root);scene.remove(current.batches);}
    current=cache.get(number);scene.add(current.root);scene.add(current.batches);applyWalls();
    setMode(mode);$('loading').hidden=true;document.body.dataset.loadedRoom=String(number);
    window.dispatchEvent(new CustomEvent('room-loaded',{detail:{room:number,objects:current.pickables.length}}));
  }catch(error){if(token!==request)return;$('loading-text').textContent='The room could not load. Serve this folder over HTTP, and check that its models folder is present.';console.error(error);}
}
document.querySelectorAll('[data-room]').forEach(b=>b.onclick=()=>loadRoom(Number(b.dataset.room)));

function pointRay(event){const r=renderer.domElement.getBoundingClientRect();cursor.set((event.clientX-r.left)/r.width*2-1,-(event.clientY-r.top)/r.height*2+1);raycaster.setFromCamera(cursor,camera);}
function inspect(event){
  if(!current)return;pointRay(event);
  const hits=raycaster.intersectObjects(current.pickables,false).filter(h=>!(sideWallsHidden&&wallPattern.test(objectName(h.object))));
  clearSelection();if(!hits.length)return;
  const obj=hits[0].object;
  helper=new THREE.BoxHelper(obj,0xe2ba77);scene.add(helper);
  needsRender=true;
  $('selection-category').textContent=obj.userData.inspection_group||'Room object';
  $('selection-name').textContent=objectName(obj).replace(/\.\d+$/,'');$('selection').hidden=false;
}
renderer.domElement.addEventListener('pointerdown',e=>{pointer={x:e.clientX,y:e.clientY,lastX:e.clientX,lastY:e.clientY,id:e.pointerId};if(mode==='walk')renderer.domElement.setPointerCapture(e.pointerId);});
renderer.domElement.addEventListener('pointermove',e=>{
  if(!pointer||mode!=='walk')return;
  yaw-=(e.clientX-pointer.lastX)*.004;pitch-=(e.clientY-pointer.lastY)*.004;pitch=THREE.MathUtils.clamp(pitch,-1.15,1.15);
  camera.rotation.set(pitch,yaw,0);pointer.lastX=e.clientX;pointer.lastY=e.clientY;
  needsRender=true;
});
renderer.domElement.addEventListener('pointerup',e=>{if(pointer&&Math.hypot(e.clientX-pointer.x,e.clientY-pointer.y)<5)inspect(e);pointer=null;});
renderer.domElement.addEventListener('pointercancel',()=>pointer=null);
function canStand(x,z){return !current||!current.obstacles.some(b=>x>b.min.x&&x<b.max.x&&z>b.min.z&&z<b.max.z);}
renderer.domElement.addEventListener('dblclick',e=>{
  if(mode!=='walk')return;pointRay(e);const point=new THREE.Vector3();
  if(raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,1,0),-.055),point)){
    const x=THREE.MathUtils.clamp(point.x,-3.03,3.03),z=THREE.MathUtils.clamp(point.z,-2.53,2.53);
    if(canStand(x,z)){camera.position.set(x,1.60,z);needsRender=true;}
  }
});
const moveKeys=new Set(['w','a','s','d','arrowup','arrowdown','arrowleft','arrowright','shift']);
window.addEventListener('keydown',e=>{if(mode==='walk'&&moveKeys.has(e.key.toLowerCase())){e.preventDefault();keys.add(e.key.toLowerCase());}});
window.addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));window.addEventListener('blur',()=>keys.clear());
document.querySelectorAll('[data-move]').forEach(button=>{
  const key={forward:'w',back:'s',left:'a',right:'d'}[button.dataset.move];
  button.addEventListener('pointerdown',e=>{e.preventDefault();keys.add(key);button.setPointerCapture(e.pointerId);});
  for(const event of ['pointerup','pointercancel'])button.addEventListener(event,()=>keys.delete(key));
});
let last=performance.now();
controls.addEventListener('change',()=>needsRender=true);
function frame(now){
  const dt=Math.min((now-last)/1000,.10);last=now;
  if(mode==='orbit')controls.update();
  else{
    const forward=Number(keys.has('w')||keys.has('arrowup'))-Number(keys.has('s')||keys.has('arrowdown'));
    const sideways=Number(keys.has('d')||keys.has('arrowright'))-Number(keys.has('a')||keys.has('arrowleft'));
    if(forward||sideways)needsRender=true;
    const speed=dt*(keys.has('shift')?2.7:1.45)/Math.max(1,Math.hypot(forward,sideways));
    const dx=(-Math.sin(yaw)*forward+Math.cos(yaw)*sideways)*speed;
    const dz=(-Math.cos(yaw)*forward-Math.sin(yaw)*sideways)*speed;
    const x=THREE.MathUtils.clamp(camera.position.x+dx,-3.03,3.03);
    if(canStand(x,camera.position.z))camera.position.x=x;
    const z=THREE.MathUtils.clamp(camera.position.z+dz,-2.53,2.53);
    if(canStand(camera.position.x,z))camera.position.z=z;
  }
  if(needsRender){renderer.render(scene,camera);needsRender=false;}
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);loadRoom(1);
// Exposes observables for artifact verification without leaking internals into the UI.
window.roomViewer={loadRoom,setMode,get room(){return currentRoom;},get mode(){return mode;},get objects(){return current?.pickables.length||0;},get drawCalls(){return renderer.info.render.calls;},get cameraPosition(){return camera.position.toArray();},get ready(){return !!current&&$('loading').hidden;},get visibleSideWallBatches(){return current?.batches.children.filter(o=>o.userData.sideWall&&o.visible).length||0;}};
