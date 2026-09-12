/**
 * React Bits "Liquid Ether" (https://reactbits.dev/backgrounds/liquid-ether), ported to
 * TypeScript. A WebGL fluid simulation (advection/viscosity/pressure solve) driven by
 * `three.js`, colored by a palette texture and nudged by the pointer.
 *
 * The internal simulation classes are ported close to the upstream source (a fluid solver, not
 * app business logic) and kept loosely typed - only the public component props are strict.
 */

import { useEffect, useRef } from 'react';
import * as THREE from 'three';

import styles from './LiquidEther.module.css';

interface LiquidEtherProps {
  className?: string;
  style?: React.CSSProperties;
  colors?: string[];
  backgroundColor?: string;
  lightMode?: boolean;
  mouseForce?: number;
  cursorSize?: number;
  isViscous?: boolean;
  viscous?: number;
  iterationsViscous?: number;
  iterationsPoisson?: number;
  dt?: number;
  BFECC?: boolean;
  resolution?: number;
  isBounce?: boolean;
  autoDemo?: boolean;
  autoSpeed?: number;
  autoIntensity?: number;
  takeoverDuration?: number;
  autoResumeDelay?: number;
  autoRampDuration?: number;
}

export function LiquidEther({
  className = '',
  style = {},
  colors = ['#5227FF', '#FF9FFC', '#B497CF'],
  backgroundColor = '#FFFFFF',
  lightMode = false,
  mouseForce = 20,
  cursorSize = 100,
  isViscous = false,
  viscous = 30,
  iterationsViscous = 32,
  iterationsPoisson = 32,
  dt = 0.014,
  BFECC = true,
  resolution = 0.5,
  isBounce = false,
  autoDemo = true,
  autoSpeed = 0.5,
  autoIntensity = 2.2,
  takeoverDuration = 0.25,
  autoResumeDelay = 1000,
  autoRampDuration = 0.6,
}: LiquidEtherProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    function makePaletteTexture(stops: string[]) {
      const arr = stops.length === 1 ? [stops[0], stops[0]] : stops.length ? stops : ['#ffffff', '#ffffff'];
      const w = arr.length;
      const data = new Uint8Array(w * 4);
      for (let i = 0; i < w; i++) {
        const c = new THREE.Color(arr[i]);
        data[i * 4 + 0] = Math.round(c.r * 255);
        data[i * 4 + 1] = Math.round(c.g * 255);
        data[i * 4 + 2] = Math.round(c.b * 255);
        data[i * 4 + 3] = 255;
      }
      const tex = new THREE.DataTexture(data, w, 1, THREE.RGBAFormat);
      tex.magFilter = THREE.LinearFilter;
      tex.minFilter = THREE.LinearFilter;
      tex.wrapS = THREE.ClampToEdgeWrapping;
      tex.wrapT = THREE.ClampToEdgeWrapping;
      tex.generateMipmaps = false;
      tex.needsUpdate = true;
      return tex;
    }

    const paletteTex = makePaletteTexture(colors);
    const bg = new THREE.Color(backgroundColor);
    const bgVec4 = lightMode ? new THREE.Vector4(bg.r, bg.g, bg.b, 1) : new THREE.Vector4(0, 0, 0, 0);

    class CommonClass {
      width = 0;
      height = 0;
      aspect = 1;
      pixelRatio = 1;
      container: HTMLElement | null = null;
      renderer!: THREE.WebGLRenderer;
      clock!: THREE.Clock;
      init(el: HTMLElement) {
        this.container = el;
        this.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
        this.resize();
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.autoClear = false;
        this.renderer.setClearColor(new THREE.Color(0x000000), 0);
        this.renderer.setPixelRatio(this.pixelRatio);
        this.renderer.setSize(this.width, this.height);
        this.renderer.domElement.style.width = '100%';
        this.renderer.domElement.style.height = '100%';
        this.renderer.domElement.style.display = 'block';
        this.clock = new THREE.Clock();
        this.clock.start();
      }
      resize() {
        if (!this.container) return;
        const rect = this.container.getBoundingClientRect();
        this.width = Math.max(1, Math.floor(rect.width));
        this.height = Math.max(1, Math.floor(rect.height));
        this.aspect = this.width / this.height;
        if (this.renderer) this.renderer.setSize(this.width, this.height, false);
      }
      update() {
        this.clock.getDelta();
      }
    }
    const Common = new CommonClass();

    class MouseClass {
      coords = new THREE.Vector2();
      coords_old = new THREE.Vector2();
      diff = new THREE.Vector2();
      timer: number | null = null;
      container: HTMLElement | null = null;
      isHoverInside = false;
      hasUserControl = false;
      isAutoActive = false;
      autoIntensity = 2.0;
      takeoverActive = false;
      takeoverStartTime = 0;
      takeoverDuration = 0.25;
      takeoverFrom = new THREE.Vector2();
      takeoverTo = new THREE.Vector2();
      onInteract: (() => void) | null = null;
      private onMouseMove = (event: MouseEvent) => {
        if (!this.updateHoverState(event.clientX, event.clientY)) return;
        this.onInteract?.();
        if (this.isAutoActive && !this.hasUserControl && !this.takeoverActive) {
          if (!this.container) return;
          const rect = this.container.getBoundingClientRect();
          if (rect.width === 0 || rect.height === 0) return;
          const nx = (event.clientX - rect.left) / rect.width;
          const ny = (event.clientY - rect.top) / rect.height;
          this.takeoverFrom.copy(this.coords);
          this.takeoverTo.set(nx * 2 - 1, -(ny * 2 - 1));
          this.takeoverStartTime = performance.now();
          this.takeoverActive = true;
          this.hasUserControl = true;
          this.isAutoActive = false;
          return;
        }
        this.setCoords(event.clientX, event.clientY);
        this.hasUserControl = true;
      };
      private onTouchStart = (event: TouchEvent) => {
        if (event.touches.length !== 1) return;
        const t = event.touches[0];
        if (!this.updateHoverState(t.clientX, t.clientY)) return;
        this.onInteract?.();
        this.setCoords(t.clientX, t.clientY);
        this.hasUserControl = true;
      };
      private onTouchMove = (event: TouchEvent) => {
        if (event.touches.length !== 1) return;
        const t = event.touches[0];
        if (!this.updateHoverState(t.clientX, t.clientY)) return;
        this.onInteract?.();
        this.setCoords(t.clientX, t.clientY);
      };
      private onTouchEnd = () => {
        this.isHoverInside = false;
      };
      private onLeave = () => {
        this.isHoverInside = false;
      };
      init(el: HTMLElement) {
        this.container = el;
        window.addEventListener('mousemove', this.onMouseMove);
        window.addEventListener('touchstart', this.onTouchStart, { passive: true });
        window.addEventListener('touchmove', this.onTouchMove, { passive: true });
        window.addEventListener('touchend', this.onTouchEnd);
        document.addEventListener('mouseleave', this.onLeave);
      }
      dispose() {
        window.removeEventListener('mousemove', this.onMouseMove);
        window.removeEventListener('touchstart', this.onTouchStart);
        window.removeEventListener('touchmove', this.onTouchMove);
        window.removeEventListener('touchend', this.onTouchEnd);
        document.removeEventListener('mouseleave', this.onLeave);
        this.container = null;
      }
      isPointInside(clientX: number, clientY: number) {
        if (!this.container) return false;
        const rect = this.container.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;
        return clientX >= rect.left && clientX <= rect.right && clientY >= rect.top && clientY <= rect.bottom;
      }
      updateHoverState(clientX: number, clientY: number) {
        this.isHoverInside = this.isPointInside(clientX, clientY);
        return this.isHoverInside;
      }
      setCoords(x: number, y: number) {
        if (!this.container) return;
        if (this.timer) window.clearTimeout(this.timer);
        const rect = this.container.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const nx = (x - rect.left) / rect.width;
        const ny = (y - rect.top) / rect.height;
        this.coords.set(nx * 2 - 1, -(ny * 2 - 1));
        this.timer = window.setTimeout(() => undefined, 100);
      }
      setNormalized(nx: number, ny: number) {
        this.coords.set(nx, ny);
      }
      update() {
        if (this.takeoverActive) {
          const t = (performance.now() - this.takeoverStartTime) / (this.takeoverDuration * 1000);
          if (t >= 1) {
            this.takeoverActive = false;
            this.coords.copy(this.takeoverTo);
            this.coords_old.copy(this.coords);
            this.diff.set(0, 0);
          } else {
            const k = t * t * (3 - 2 * t);
            this.coords.copy(this.takeoverFrom).lerp(this.takeoverTo, k);
          }
        }
        this.diff.subVectors(this.coords, this.coords_old);
        this.coords_old.copy(this.coords);
        if (this.coords_old.x === 0 && this.coords_old.y === 0) this.diff.set(0, 0);
        if (this.isAutoActive && !this.takeoverActive) this.diff.multiplyScalar(this.autoIntensity);
      }
    }
    const Mouse = new MouseClass();

    class AutoDriver {
      active = false;
      current = new THREE.Vector2(0, 0);
      target = new THREE.Vector2();
      lastTime = performance.now();
      activationTime = 0;
      margin = 0.2;
      private tmpDir = new THREE.Vector2();
      constructor(
        private mouse: MouseClass,
        private manager: { lastUserInteraction: number },
        public enabled: boolean,
        public speed: number,
        public resumeDelay: number,
        public rampDurationMs: number,
      ) {
        this.pickNewTarget();
      }
      pickNewTarget() {
        this.target.set((Math.random() * 2 - 1) * (1 - this.margin), (Math.random() * 2 - 1) * (1 - this.margin));
      }
      forceStop() {
        this.active = false;
        this.mouse.isAutoActive = false;
      }
      update() {
        if (!this.enabled) return;
        const now = performance.now();
        const idle = now - this.manager.lastUserInteraction;
        if (idle < this.resumeDelay) {
          if (this.active) this.forceStop();
          return;
        }
        if (this.mouse.isHoverInside) {
          if (this.active) this.forceStop();
          return;
        }
        if (!this.active) {
          this.active = true;
          this.current.copy(this.mouse.coords);
          this.lastTime = now;
          this.activationTime = now;
        }
        this.mouse.isAutoActive = true;
        let dtSec = (now - this.lastTime) / 1000;
        this.lastTime = now;
        if (dtSec > 0.2) dtSec = 0.016;
        const dir = this.tmpDir.subVectors(this.target, this.current);
        const dist = dir.length();
        if (dist < 0.01) {
          this.pickNewTarget();
          return;
        }
        dir.normalize();
        let ramp = 1;
        if (this.rampDurationMs > 0) {
          const t = Math.min(1, (now - this.activationTime) / this.rampDurationMs);
          ramp = t * t * (3 - 2 * t);
        }
        const step = this.speed * dtSec * ramp;
        const move = Math.min(step, dist);
        this.current.addScaledVector(dir, move);
        this.mouse.setNormalized(this.current.x, this.current.y);
      }
    }

    const face_vert = `
attribute vec3 position;
uniform vec2 px;
uniform vec2 boundarySpace;
varying vec2 uv;
precision highp float;
void main(){
  vec3 pos = position;
  vec2 scale = 1.0 - boundarySpace * 2.0;
  pos.xy = pos.xy * scale;
  uv = vec2(0.5)+(pos.xy)*0.5;
  gl_Position = vec4(pos, 1.0);
}
`;
    const line_vert = `
attribute vec3 position;
uniform vec2 px;
precision highp float;
varying vec2 uv;
void main(){
  vec3 pos = position;
  uv = 0.5 + pos.xy * 0.5;
  vec2 n = sign(pos.xy);
  pos.xy = abs(pos.xy) - px * 1.0;
  pos.xy *= n;
  gl_Position = vec4(pos, 1.0);
}
`;
    const mouse_vert = `
precision highp float;
attribute vec3 position;
attribute vec2 uv;
uniform vec2 center;
uniform vec2 scale;
uniform vec2 px;
varying vec2 vUv;
void main(){
  vec2 pos = position.xy * scale * 2.0 * px + center;
  vUv = uv;
  gl_Position = vec4(pos, 0.0, 1.0);
}
`;
    const advection_frag = `
precision highp float;
uniform sampler2D velocity;
uniform float dt;
uniform bool isBFECC;
uniform vec2 fboSize;
uniform vec2 px;
varying vec2 uv;
void main(){
  vec2 ratio = max(fboSize.x, fboSize.y) / fboSize;
  if(isBFECC == false){
    vec2 vel = texture2D(velocity, uv).xy;
    vec2 uv2 = uv - vel * dt * ratio;
    vec2 newVel = texture2D(velocity, uv2).xy;
    gl_FragColor = vec4(newVel, 0.0, 0.0);
  } else {
    vec2 spot_new = uv;
    vec2 vel_old = texture2D(velocity, uv).xy;
    vec2 spot_old = spot_new - vel_old * dt * ratio;
    vec2 vel_new1 = texture2D(velocity, spot_old).xy;
    vec2 spot_new2 = spot_old + vel_new1 * dt * ratio;
    vec2 error = spot_new2 - spot_new;
    vec2 spot_new3 = spot_new - error / 2.0;
    vec2 vel_2 = texture2D(velocity, spot_new3).xy;
    vec2 spot_old2 = spot_new3 - vel_2 * dt * ratio;
    vec2 newVel2 = texture2D(velocity, spot_old2).xy;
    gl_FragColor = vec4(newVel2, 0.0, 0.0);
  }
}
`;
    const color_frag = `
precision highp float;
uniform sampler2D velocity;
uniform sampler2D palette;
uniform vec4 bgColor;
uniform bool lightMode;
varying vec2 uv;
void main(){
  vec2 vel = texture2D(velocity, uv).xy;
  float lenv = clamp(length(vel), 0.0, 1.0);
  vec3 c = texture2D(palette, vec2(lenv, 0.5)).rgb;
  float peak = max(c.r, max(c.g, c.b));
  vec3 chroma = clamp(c / max(peak, 0.0001), 0.0, 1.0);
  chroma = pow(chroma, vec3(1.25));
  vec3 ink = lightMode ? chroma : c;
  vec3 outRGB = mix(bgColor.rgb, ink, lenv);
  float outA = mix(bgColor.a, 1.0, lenv);
  gl_FragColor = vec4(outRGB, outA);
}
`;
    const divergence_frag = `
precision highp float;
uniform sampler2D velocity;
uniform float dt;
uniform vec2 px;
varying vec2 uv;
void main(){
  float x0 = texture2D(velocity, uv-vec2(px.x, 0.0)).x;
  float x1 = texture2D(velocity, uv+vec2(px.x, 0.0)).x;
  float y0 = texture2D(velocity, uv-vec2(0.0, px.y)).y;
  float y1 = texture2D(velocity, uv+vec2(0.0, px.y)).y;
  float divergence = (x1 - x0 + y1 - y0) / 2.0;
  gl_FragColor = vec4(divergence / dt);
}
`;
    const externalForce_frag = `
precision highp float;
uniform vec2 force;
uniform vec2 center;
uniform vec2 scale;
uniform vec2 px;
varying vec2 vUv;
void main(){
  vec2 circle = (vUv - 0.5) * 2.0;
  float d = 1.0 - min(length(circle), 1.0);
  d *= d;
  gl_FragColor = vec4(force * d, 0.0, 1.0);
}
`;
    const poisson_frag = `
precision highp float;
uniform sampler2D pressure;
uniform sampler2D divergence;
uniform vec2 px;
varying vec2 uv;
void main(){
  float p0 = texture2D(pressure, uv + vec2(px.x * 2.0, 0.0)).r;
  float p1 = texture2D(pressure, uv - vec2(px.x * 2.0, 0.0)).r;
  float p2 = texture2D(pressure, uv + vec2(0.0, px.y * 2.0)).r;
  float p3 = texture2D(pressure, uv - vec2(0.0, px.y * 2.0)).r;
  float div = texture2D(divergence, uv).r;
  float newP = (p0 + p1 + p2 + p3) / 4.0 - div;
  gl_FragColor = vec4(newP);
}
`;
    const pressure_frag = `
precision highp float;
uniform sampler2D pressure;
uniform sampler2D velocity;
uniform vec2 px;
uniform float dt;
varying vec2 uv;
void main(){
  float step = 1.0;
  float p0 = texture2D(pressure, uv + vec2(px.x * step, 0.0)).r;
  float p1 = texture2D(pressure, uv - vec2(px.x * step, 0.0)).r;
  float p2 = texture2D(pressure, uv + vec2(0.0, px.y * step)).r;
  float p3 = texture2D(pressure, uv - vec2(0.0, px.y * step)).r;
  vec2 v = texture2D(velocity, uv).xy;
  vec2 gradP = vec2(p0 - p1, p2 - p3) * 0.5;
  v = v - gradP * dt;
  gl_FragColor = vec4(v, 0.0, 1.0);
}
`;
    const viscous_frag = `
precision highp float;
uniform sampler2D velocity;
uniform sampler2D velocity_new;
uniform float v;
uniform vec2 px;
uniform float dt;
varying vec2 uv;
void main(){
  vec2 old = texture2D(velocity, uv).xy;
  vec2 new0 = texture2D(velocity_new, uv + vec2(px.x * 2.0, 0.0)).xy;
  vec2 new1 = texture2D(velocity_new, uv - vec2(px.x * 2.0, 0.0)).xy;
  vec2 new2 = texture2D(velocity_new, uv + vec2(0.0, px.y * 2.0)).xy;
  vec2 new3 = texture2D(velocity_new, uv - vec2(0.0, px.y * 2.0)).xy;
  vec2 newv = 4.0 * old + v * dt * (new0 + new1 + new2 + new3);
  newv /= 4.0 * (1.0 + v * dt);
  gl_FragColor = vec4(newv, 0.0, 0.0);
}
`;

    class ShaderPass {
      scene = new THREE.Scene();
      camera = new THREE.Camera();
      material: THREE.RawShaderMaterial | null = null;
      plane: THREE.Mesh | null = null;
      constructor(private props: { material?: THREE.ShaderMaterialParameters; output?: THREE.WebGLRenderTarget | null }) {
        if (this.props.material) {
          this.material = new THREE.RawShaderMaterial(this.props.material);
          this.plane = new THREE.Mesh(new THREE.PlaneGeometry(2.0, 2.0), this.material);
          this.scene.add(this.plane);
        }
      }
      get uniforms() {
        return (this.props.material?.uniforms ?? {}) as Record<string, THREE.IUniform>;
      }
      set output(target: THREE.WebGLRenderTarget | null | undefined) {
        this.props.output = target;
      }
      get output(): THREE.WebGLRenderTarget | null | undefined {
        return this.props.output;
      }
      update() {
        Common.renderer.setRenderTarget(this.props.output ?? null);
        Common.renderer.render(this.scene, this.camera);
        Common.renderer.setRenderTarget(null);
      }
    }

    interface CellProps {
      cellScale: THREE.Vector2;
      boundarySpace: THREE.Vector2;
      fboSize: THREE.Vector2;
      dt: number;
      src: THREE.WebGLRenderTarget;
      dst: THREE.WebGLRenderTarget;
      dst_?: THREE.WebGLRenderTarget;
      cursor_size?: number;
      viscous?: number;
      src_p?: THREE.WebGLRenderTarget;
      src_v?: THREE.WebGLRenderTarget;
    }

    class Advection extends ShaderPass {
      line: THREE.LineSegments;
      constructor(simProps: CellProps) {
        super({
          material: {
            vertexShader: face_vert,
            fragmentShader: advection_frag,
            uniforms: {
              boundarySpace: { value: simProps.cellScale },
              px: { value: simProps.cellScale },
              fboSize: { value: simProps.fboSize },
              velocity: { value: simProps.src.texture },
              dt: { value: simProps.dt },
              isBFECC: { value: true },
            },
          },
          output: simProps.dst,
        });
        const boundaryG = new THREE.BufferGeometry();
        const vertices = new Float32Array([-1, -1, 0, -1, 1, 0, -1, 1, 0, 1, 1, 0, 1, 1, 0, 1, -1, 0, 1, -1, 0, -1, -1, 0]);
        boundaryG.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
        const boundaryM = new THREE.RawShaderMaterial({ vertexShader: line_vert, fragmentShader: advection_frag, uniforms: this.uniforms });
        this.line = new THREE.LineSegments(boundaryG, boundaryM);
        this.scene.add(this.line);
      }
      updateFrame(opts: { dt: number; isBounce: boolean; BFECC: boolean }) {
        this.uniforms.dt.value = opts.dt;
        this.line.visible = opts.isBounce;
        this.uniforms.isBFECC.value = opts.BFECC;
        super.update();
      }
    }

    class ExternalForce extends ShaderPass {
      mouse: THREE.Mesh;
      constructor(simProps: { cellScale: THREE.Vector2; cursor_size: number; dst: THREE.WebGLRenderTarget }) {
        super({ output: simProps.dst });
        const mouseM = new THREE.RawShaderMaterial({
          vertexShader: mouse_vert,
          fragmentShader: externalForce_frag,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
          uniforms: {
            px: { value: simProps.cellScale },
            force: { value: new THREE.Vector2(0, 0) },
            center: { value: new THREE.Vector2(0, 0) },
            scale: { value: new THREE.Vector2(simProps.cursor_size, simProps.cursor_size) },
          },
        });
        this.mouse = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mouseM);
        this.scene.add(this.mouse);
      }
      updateFrame(opts: { mouse_force: number; cursor_size: number; cellScale: THREE.Vector2 }) {
        const forceX = (Mouse.diff.x / 2) * opts.mouse_force;
        const forceY = (Mouse.diff.y / 2) * opts.mouse_force;
        const cursorSizeX = opts.cursor_size * opts.cellScale.x;
        const cursorSizeY = opts.cursor_size * opts.cellScale.y;
        const centerX = Math.min(Math.max(Mouse.coords.x, -1 + cursorSizeX + opts.cellScale.x * 2), 1 - cursorSizeX - opts.cellScale.x * 2);
        const centerY = Math.min(Math.max(Mouse.coords.y, -1 + cursorSizeY + opts.cellScale.y * 2), 1 - cursorSizeY - opts.cellScale.y * 2);
        const uniforms = (this.mouse.material as THREE.RawShaderMaterial).uniforms;
        (uniforms.force.value as THREE.Vector2).set(forceX, forceY);
        (uniforms.center.value as THREE.Vector2).set(centerX, centerY);
        (uniforms.scale.value as THREE.Vector2).set(opts.cursor_size, opts.cursor_size);
        super.update();
      }
    }

    class Viscous extends ShaderPass {
      output0: THREE.WebGLRenderTarget;
      output1: THREE.WebGLRenderTarget;
      constructor(simProps: { boundarySpace: THREE.Vector2; src: THREE.WebGLRenderTarget; dst_: THREE.WebGLRenderTarget; dst: THREE.WebGLRenderTarget; viscous: number; cellScale: THREE.Vector2; dt: number }) {
        super({
          material: {
            vertexShader: face_vert,
            fragmentShader: viscous_frag,
            uniforms: {
              boundarySpace: { value: simProps.boundarySpace },
              velocity: { value: simProps.src.texture },
              velocity_new: { value: simProps.dst_.texture },
              v: { value: simProps.viscous },
              px: { value: simProps.cellScale },
              dt: { value: simProps.dt },
            },
          },
          output: simProps.dst,
        });
        this.output0 = simProps.dst_;
        this.output1 = simProps.dst;
      }
      updateFrame(opts: { viscous: number; iterations: number; dt: number }) {
        let fboIn: THREE.WebGLRenderTarget;
        let fboOut: THREE.WebGLRenderTarget = this.output1;
        this.uniforms.v.value = opts.viscous;
        for (let i = 0; i < opts.iterations; i++) {
          if (i % 2 === 0) {
            fboIn = this.output0;
            fboOut = this.output1;
          } else {
            fboIn = this.output1;
            fboOut = this.output0;
          }
          this.uniforms.velocity_new.value = fboIn.texture;
          this.output = fboOut;
          this.uniforms.dt.value = opts.dt;
          super.update();
        }
        return fboOut;
      }
    }

    class Divergence extends ShaderPass {
      constructor(simProps: { boundarySpace: THREE.Vector2; src: THREE.WebGLRenderTarget; dst: THREE.WebGLRenderTarget; cellScale: THREE.Vector2; dt: number }) {
        super({
          material: {
            vertexShader: face_vert,
            fragmentShader: divergence_frag,
            uniforms: { boundarySpace: { value: simProps.boundarySpace }, velocity: { value: simProps.src.texture }, px: { value: simProps.cellScale }, dt: { value: simProps.dt } },
          },
          output: simProps.dst,
        });
      }
      updateFrame(vel: THREE.WebGLRenderTarget) {
        this.uniforms.velocity.value = vel.texture;
        super.update();
      }
    }

    class Poisson extends ShaderPass {
      output0: THREE.WebGLRenderTarget;
      output1: THREE.WebGLRenderTarget;
      constructor(simProps: { boundarySpace: THREE.Vector2; dst_: THREE.WebGLRenderTarget; src: THREE.WebGLRenderTarget; dst: THREE.WebGLRenderTarget; cellScale: THREE.Vector2 }) {
        super({
          material: {
            vertexShader: face_vert,
            fragmentShader: poisson_frag,
            uniforms: { boundarySpace: { value: simProps.boundarySpace }, pressure: { value: simProps.dst_.texture }, divergence: { value: simProps.src.texture }, px: { value: simProps.cellScale } },
          },
          output: simProps.dst,
        });
        this.output0 = simProps.dst_;
        this.output1 = simProps.dst;
      }
      updateFrame(iterations: number) {
        let pIn: THREE.WebGLRenderTarget;
        let pOut: THREE.WebGLRenderTarget = this.output1;
        for (let i = 0; i < iterations; i++) {
          if (i % 2 === 0) {
            pIn = this.output0;
            pOut = this.output1;
          } else {
            pIn = this.output1;
            pOut = this.output0;
          }
          this.uniforms.pressure.value = pIn.texture;
          this.output = pOut;
          super.update();
        }
        return pOut;
      }
    }

    class Pressure extends ShaderPass {
      constructor(simProps: { boundarySpace: THREE.Vector2; src_p: THREE.WebGLRenderTarget; src_v: THREE.WebGLRenderTarget; cellScale: THREE.Vector2; dt: number; dst: THREE.WebGLRenderTarget }) {
        super({
          material: {
            vertexShader: face_vert,
            fragmentShader: pressure_frag,
            uniforms: { boundarySpace: { value: simProps.boundarySpace }, pressure: { value: simProps.src_p.texture }, velocity: { value: simProps.src_v.texture }, px: { value: simProps.cellScale }, dt: { value: simProps.dt } },
          },
          output: simProps.dst,
        });
      }
      updateFrame(vel: THREE.WebGLRenderTarget, pressure: THREE.WebGLRenderTarget) {
        this.uniforms.velocity.value = vel.texture;
        this.uniforms.pressure.value = pressure.texture;
        super.update();
      }
    }

    interface SimOptions {
      iterations_poisson: number;
      iterations_viscous: number;
      mouse_force: number;
      resolution: number;
      cursor_size: number;
      viscous: number;
      isBounce: boolean;
      dt: number;
      isViscous: boolean;
      BFECC: boolean;
    }

    class Simulation {
      options: SimOptions = {
        iterations_poisson: 32,
        iterations_viscous: 32,
        mouse_force: 20,
        resolution: 0.5,
        cursor_size: 100,
        viscous: 30,
        isBounce: false,
        dt: 0.014,
        isViscous: false,
        BFECC: true,
      };
      fboSize = new THREE.Vector2();
      cellScale = new THREE.Vector2();
      boundarySpace = new THREE.Vector2();
      fbos: Record<string, THREE.WebGLRenderTarget> = {};
      advection!: Advection;
      externalForce!: ExternalForce;
      viscous!: Viscous;
      divergence!: Divergence;
      poisson!: Poisson;
      pressure!: Pressure;
      constructor(options: Partial<SimOptions>) {
        Object.assign(this.options, options);
        this.calcSize();
        this.createAllFBO();
        this.createShaderPass();
      }
      getFloatType() {
        const isIOS = /(iPad|iPhone|iPod)/i.test(navigator.userAgent);
        return isIOS ? THREE.HalfFloatType : THREE.FloatType;
      }
      createAllFBO() {
        const type = this.getFloatType();
        const opts = { type, depthBuffer: false, stencilBuffer: false, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, wrapS: THREE.ClampToEdgeWrapping, wrapT: THREE.ClampToEdgeWrapping };
        for (const key of ['vel_0', 'vel_1', 'vel_viscous0', 'vel_viscous1', 'div', 'pressure_0', 'pressure_1']) {
          this.fbos[key] = new THREE.WebGLRenderTarget(this.fboSize.x, this.fboSize.y, opts);
        }
      }
      createShaderPass() {
        this.advection = new Advection({ cellScale: this.cellScale, boundarySpace: this.boundarySpace, fboSize: this.fboSize, dt: this.options.dt, src: this.fbos.vel_0, dst: this.fbos.vel_1 });
        this.externalForce = new ExternalForce({ cellScale: this.cellScale, cursor_size: this.options.cursor_size, dst: this.fbos.vel_1 });
        this.viscous = new Viscous({ cellScale: this.cellScale, boundarySpace: this.boundarySpace, viscous: this.options.viscous, src: this.fbos.vel_1, dst: this.fbos.vel_viscous1, dst_: this.fbos.vel_viscous0, dt: this.options.dt });
        this.divergence = new Divergence({ cellScale: this.cellScale, boundarySpace: this.boundarySpace, src: this.fbos.vel_viscous0, dst: this.fbos.div, dt: this.options.dt });
        this.poisson = new Poisson({ cellScale: this.cellScale, boundarySpace: this.boundarySpace, src: this.fbos.div, dst: this.fbos.pressure_1, dst_: this.fbos.pressure_0 });
        this.pressure = new Pressure({ cellScale: this.cellScale, boundarySpace: this.boundarySpace, src_p: this.fbos.pressure_0, src_v: this.fbos.vel_viscous0, dst: this.fbos.vel_0, dt: this.options.dt });
      }
      calcSize() {
        const width = Math.max(1, Math.round(this.options.resolution * Common.width));
        const height = Math.max(1, Math.round(this.options.resolution * Common.height));
        this.cellScale.set(1 / width, 1 / height);
        this.fboSize.set(width, height);
      }
      resize() {
        this.calcSize();
        for (const key in this.fbos) this.fbos[key].setSize(this.fboSize.x, this.fboSize.y);
      }
      update() {
        this.boundarySpace.copy(this.options.isBounce ? new THREE.Vector2(0, 0) : this.cellScale);
        this.advection.updateFrame({ dt: this.options.dt, isBounce: this.options.isBounce, BFECC: this.options.BFECC });
        this.externalForce.updateFrame({ cursor_size: this.options.cursor_size, mouse_force: this.options.mouse_force, cellScale: this.cellScale });
        let vel = this.fbos.vel_1;
        if (this.options.isViscous) {
          vel = this.viscous.updateFrame({ viscous: this.options.viscous, iterations: this.options.iterations_viscous, dt: this.options.dt });
        }
        this.divergence.updateFrame(vel);
        const pressure = this.poisson.updateFrame(this.options.iterations_poisson);
        this.pressure.updateFrame(vel, pressure);
      }
    }

    class Output {
      simulation = new Simulation({});
      scene = new THREE.Scene();
      camera = new THREE.Camera();
      output: THREE.Mesh;
      constructor() {
        this.output = new THREE.Mesh(
          new THREE.PlaneGeometry(2, 2),
          new THREE.RawShaderMaterial({
            vertexShader: face_vert,
            fragmentShader: color_frag,
            transparent: true,
            depthWrite: false,
            uniforms: { velocity: { value: this.simulation.fbos.vel_0.texture }, boundarySpace: { value: new THREE.Vector2() }, palette: { value: paletteTex }, bgColor: { value: bgVec4 }, lightMode: { value: lightMode } },
          }),
        );
        this.scene.add(this.output);
      }
      resize() {
        this.simulation.resize();
      }
      render() {
        Common.renderer.setRenderTarget(null);
        Common.renderer.render(this.scene, this.camera);
      }
      update() {
        this.simulation.update();
        this.render();
      }
    }

    let rafId: number | null = null;
    let running = false;
    const lastUserInteraction = { value: performance.now() };

    Common.init(container);
    Mouse.init(container);
    Mouse.autoIntensity = autoIntensity;
    Mouse.takeoverDuration = takeoverDuration;
    Mouse.onInteract = () => {
      lastUserInteraction.value = performance.now();
      autoDriver.forceStop();
    };
    const autoDriver = new AutoDriver(Mouse, { get lastUserInteraction() { return lastUserInteraction.value; } }, autoDemo, autoSpeed, autoResumeDelay, autoRampDuration * 1000);

    // Note: position/overflow are already set by `LiquidEther.module.css` (`.container`); forcing
    // them here as inline styles would win over the stylesheet and break the absolute-fill layout.
    container.prepend(Common.renderer.domElement);
    const output = new Output();
    Object.assign(output.simulation.options, { mouse_force: mouseForce, cursor_size: cursorSize, isViscous, viscous, iterations_viscous: iterationsViscous, iterations_poisson: iterationsPoisson, dt, BFECC, resolution, isBounce });

    function render() {
      autoDriver.update();
      Mouse.update();
      Common.update();
      output.update();
    }
    function loop() {
      if (!running) return;
      render();
      rafId = requestAnimationFrame(loop);
    }
    function start() {
      if (running) return;
      running = true;
      loop();
    }
    function pause() {
      running = false;
      if (rafId) cancelAnimationFrame(rafId);
      rafId = null;
    }

    start();

    const onVisibility = () => {
      if (document.hidden) pause();
      else start();
    };
    document.addEventListener('visibilitychange', onVisibility);

    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries[0]?.isIntersecting && entries[0].intersectionRatio > 0;
        if (visible && !document.hidden) start();
        else pause();
      },
      { threshold: [0, 0.01, 0.1] },
    );
    io.observe(container);

    let resizeRaf: number | null = null;
    const ro = new ResizeObserver(() => {
      if (resizeRaf) cancelAnimationFrame(resizeRaf);
      resizeRaf = requestAnimationFrame(() => {
        Common.resize();
        output.resize();
      });
    });
    ro.observe(container);
    const onWindowResize = () => {
      Common.resize();
      output.resize();
    };
    window.addEventListener('resize', onWindowResize);

    return () => {
      pause();
      window.removeEventListener('resize', onWindowResize);
      document.removeEventListener('visibilitychange', onVisibility);
      io.disconnect();
      ro.disconnect();
      Mouse.dispose();
      const canvas = Common.renderer?.domElement;
      if (canvas?.parentNode) canvas.parentNode.removeChild(canvas);
      Common.renderer?.dispose();
      Common.renderer?.forceContextLoss();
    };
  }, [
    BFECC,
    cursorSize,
    dt,
    isBounce,
    isViscous,
    iterationsPoisson,
    iterationsViscous,
    mouseForce,
    resolution,
    viscous,
    colors,
    autoDemo,
    autoSpeed,
    autoIntensity,
    takeoverDuration,
    autoResumeDelay,
    autoRampDuration,
    backgroundColor,
    lightMode,
  ]);

  return <div ref={mountRef} className={`${styles.container} ${className}`} style={style} aria-hidden="true" />;
}
