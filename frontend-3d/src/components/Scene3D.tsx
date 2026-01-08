import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment, PerspectiveCamera, ContactShadows, Lightformer } from '@react-three/drei';
import { Suspense } from 'react';
import { RealisticHumanModel } from './RealisticHumanModel';
import { useAppStore } from '../store/useAppStore';
import { BODY_REGIONS } from '../data/bodyData';

function LoadingFallback() {
  return (
    <mesh>
      <capsuleGeometry args={[0.1, 0.5, 8, 16]} />
      <meshStandardMaterial color="#e8beac" wireframe />
    </mesh>
  );
}

// Stüdyo tarzı ışıklandırma
function StudioLighting() {
  return (
    <>
      {/* Ana ışık - yumuşak dolgu */}
      <ambientLight intensity={0.3} />
      
      {/* Key light - ana aydınlatma */}
      <directionalLight 
        position={[3, 4, 5]} 
        intensity={1.2}
        color="#fff5eb"
        castShadow
        shadow-mapSize={[1024, 1024]}
      />
      
      {/* Fill light - gölgeleri yumuşatma */}
      <directionalLight 
        position={[-4, 2, 3]} 
        intensity={0.6}
        color="#e8f4ff"
      />
      
      {/* Rim/Back light - kenar aydınlatma */}
      <directionalLight 
        position={[0, 3, -4]} 
        intensity={0.5}
        color="#ffeedd"
      />
      
      {/* Üstten yumuşak ışık */}
      <pointLight 
        position={[0, 5, 0]} 
        intensity={0.4}
        color="#ffffff"
      />
      
      {/* Ten rengini ön plana çıkaran sıcak ışık */}
      <spotLight
        position={[2, 3, 2]}
        angle={0.5}
        penumbra={1}
        intensity={0.5}
        color="#ffddcc"
      />
    </>
  );
}

export function Scene3D() {
  const { hoveredRegion, selectedRegion } = useAppStore();
  
  const displayRegion = hoveredRegion || selectedRegion;
  const regionName = displayRegion ? BODY_REGIONS[displayRegion].name_tr : null;

  return (
    <div className="relative w-full h-full min-h-[400px] bg-gradient-to-b from-slate-900 via-slate-850 to-slate-800 rounded-2xl overflow-hidden shadow-2xl">
      {/* Bölge ismi tooltip */}
      {regionName && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10 bg-white/95 backdrop-blur-md px-5 py-2.5 rounded-full shadow-xl border border-white/20">
          <span className="text-slate-800 font-semibold text-lg">{regionName}</span>
        </div>
      )}
      
      {/* Yardım metni */}
      <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-10 text-white/70 text-sm font-medium">
        🎯 Ağrıyan bölgeye tıklayın • 🔄 Döndürmek için sürükleyin
      </div>

      <Canvas shadows dpr={[1, 2]}>
        <PerspectiveCamera makeDefault position={[0, 0.5, 3.5]} fov={45} />
        
        {/* Profesyonel stüdyo ışıklandırma */}
        <StudioLighting />
        
        {/* HDRI Ortam - ten rengini gerçekçi gösterir */}
        <Environment 
          preset="studio" 
          background={false}
          environmentIntensity={0.8}
        />
        
        {/* Zemin gölgesi */}
        <ContactShadows
          position={[0, -0.65, 0]}
          opacity={0.4}
          scale={2}
          blur={2.5}
          far={1}
          color="#1a1a2e"
        />
        
        {/* 3D Model */}
        <Suspense fallback={<LoadingFallback />}>
          <RealisticHumanModel />
        </Suspense>
        
        {/* Kontroller */}
        <OrbitControls 
          enablePan={false}
          enableZoom={true}
          minDistance={1.2}
          maxDistance={3.5}
          minPolarAngle={Math.PI / 5}
          maxPolarAngle={Math.PI * 4 / 5}
          autoRotate={false}
          enableDamping={true}
          dampingFactor={0.05}
        />
      </Canvas>
    </div>
  );
}
