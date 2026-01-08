import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Group, Mesh, Color } from 'three';
import { useAppStore } from '../store/useAppStore';
import { BodyRegion } from '../types';

// Ten rengi PBR materyali için renkler
const SKIN_COLOR = new Color('#e8beac'); // Doğal ten rengi

// Hit zone tanımları - her bölge için pozisyon ve boyut
const HIT_ZONES: Record<string, { position: [number, number, number]; scale: [number, number, number]; rotation?: [number, number, number] }> = {
  head: { position: [0, 1.65, 0], scale: [0.18, 0.22, 0.2] },
  neck: { position: [0, 1.42, 0], scale: [0.1, 0.08, 0.1] },
  chest: { position: [0, 1.18, 0.02], scale: [0.28, 0.18, 0.15] },
  abdomen: { position: [0, 0.92, 0.02], scale: [0.24, 0.15, 0.13] },
  back_upper: { position: [0, 1.18, -0.08], scale: [0.26, 0.18, 0.1] },
  back_lower: { position: [0, 0.85, -0.08], scale: [0.24, 0.12, 0.1] },
  left_shoulder: { position: [0.28, 1.32, 0], scale: [0.1, 0.08, 0.1] },
  right_shoulder: { position: [-0.28, 1.32, 0], scale: [0.1, 0.08, 0.1] },
  left_upper_arm: { position: [0.36, 1.12, 0], scale: [0.07, 0.15, 0.07], rotation: [0, 0, 0.2] },
  right_upper_arm: { position: [-0.36, 1.12, 0], scale: [0.07, 0.15, 0.07], rotation: [0, 0, -0.2] },
  left_forearm: { position: [0.42, 0.82, 0], scale: [0.055, 0.14, 0.055], rotation: [0, 0, 0.15] },
  right_forearm: { position: [-0.42, 0.82, 0], scale: [0.055, 0.14, 0.055], rotation: [0, 0, -0.15] },
  left_hand: { position: [0.46, 0.58, 0], scale: [0.05, 0.08, 0.03] },
  right_hand: { position: [-0.46, 0.58, 0], scale: [0.05, 0.08, 0.03] },
  left_hip: { position: [0.12, 0.72, 0], scale: [0.12, 0.08, 0.1] },
  right_hip: { position: [-0.12, 0.72, 0], scale: [0.12, 0.08, 0.1] },
  left_upper_leg: { position: [0.12, 0.48, 0], scale: [0.09, 0.18, 0.09] },
  right_upper_leg: { position: [-0.12, 0.48, 0], scale: [0.09, 0.18, 0.09] },
  left_knee: { position: [0.12, 0.28, 0.02], scale: [0.065, 0.06, 0.07] },
  right_knee: { position: [-0.12, 0.28, 0.02], scale: [0.065, 0.06, 0.07] },
  left_shin: { position: [0.12, 0.08, 0], scale: [0.055, 0.14, 0.055] },
  right_shin: { position: [-0.12, 0.08, 0], scale: [0.055, 0.14, 0.055] },
  left_foot: { position: [0.12, -0.12, 0.04], scale: [0.055, 0.04, 0.1] },
  right_foot: { position: [-0.12, -0.12, 0.04], scale: [0.055, 0.04, 0.1] },
};

// Hit Zone bileşeni - görünmez ama tıklanabilir
interface HitZoneProps {
  regionId: BodyRegion;
  position: [number, number, number];
  scale: [number, number, number];
  rotation?: [number, number, number];
  isSelected: boolean;
  isHovered: boolean;
  onClick: () => void;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
}

function HitZone({
  position,
  scale,
  rotation = [0, 0, 0],
  isSelected,
  isHovered,
  onClick,
  onPointerEnter,
  onPointerLeave,
}: Omit<HitZoneProps, 'regionId'>) {
  const meshRef = useRef<Mesh>(null);
  
  // Hover veya seçili olduğunda görünür yap
  const opacity = isSelected ? 0.4 : isHovered ? 0.25 : 0;
  const color = isSelected ? '#00ff88' : isHovered ? '#ffcc00' : '#ffffff';
  
  return (
    <mesh
      ref={meshRef}
      position={position}
      scale={scale}
      rotation={rotation}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      onPointerEnter={(e) => { 
        e.stopPropagation(); 
        document.body.style.cursor = 'pointer'; 
        onPointerEnter(); 
      }}
      onPointerLeave={(e) => { 
        e.stopPropagation(); 
        document.body.style.cursor = 'auto'; 
        onPointerLeave(); 
      }}
    >
      <sphereGeometry args={[1, 16, 12]} />
      <meshStandardMaterial
        color={color}
        transparent
        opacity={opacity}
        depthWrite={false}
        emissive={color}
        emissiveIntensity={isSelected ? 0.5 : isHovered ? 0.3 : 0}
      />
    </mesh>
  );
}

// Gerçekçi insan vücudu - tek mesh
function RealisticBody() {
  const bodyRef = useRef<Group>(null);

  return (
    <group ref={bodyRef}>
      {/* Baş */}
      <mesh position={[0, 1.65, 0]}>
        <sphereGeometry args={[0.12, 32, 24]} />
        <meshStandardMaterial
          color={SKIN_COLOR}
          roughness={0.6}
          metalness={0.0}
          envMapIntensity={0.5}
        />
      </mesh>
      
      {/* Boyun */}
      <mesh position={[0, 1.48, 0]}>
        <cylinderGeometry args={[0.05, 0.06, 0.12, 16]} />
        <meshStandardMaterial
          color={SKIN_COLOR}
          roughness={0.6}
          metalness={0.0}
        />
      </mesh>
      
      {/* Gövde - üst (göğüs) */}
      <mesh position={[0, 1.22, 0]}>
        <capsuleGeometry args={[0.16, 0.22, 8, 24]} />
        <meshStandardMaterial
          color={SKIN_COLOR}
          roughness={0.55}
          metalness={0.0}
          envMapIntensity={0.4}
        />
      </mesh>
      
      {/* Gövde - alt (karın) */}
      <mesh position={[0, 0.92, 0]}>
        <capsuleGeometry args={[0.14, 0.16, 8, 24]} />
        <meshStandardMaterial
          color={SKIN_COLOR}
          roughness={0.55}
          metalness={0.0}
        />
      </mesh>
      
      {/* Kalça bölgesi */}
      <mesh position={[0, 0.72, 0]}>
        <sphereGeometry args={[0.16, 24, 16]} />
        <meshStandardMaterial
          color={SKIN_COLOR}
          roughness={0.55}
          metalness={0.0}
        />
      </mesh>

      {/* Sol omuz */}
      <mesh position={[0.22, 1.32, 0]}>
        <sphereGeometry args={[0.065, 16, 12]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.6} />
      </mesh>
      
      {/* Sağ omuz */}
      <mesh position={[-0.22, 1.32, 0]}>
        <sphereGeometry args={[0.065, 16, 12]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.6} />
      </mesh>

      {/* Sol üst kol */}
      <mesh position={[0.32, 1.12, 0]} rotation={[0, 0, 0.25]}>
        <capsuleGeometry args={[0.045, 0.22, 6, 16]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.6} />
      </mesh>
      
      {/* Sağ üst kol */}
      <mesh position={[-0.32, 1.12, 0]} rotation={[0, 0, -0.25]}>
        <capsuleGeometry args={[0.045, 0.22, 6, 16]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.6} />
      </mesh>

      {/* Sol dirsek */}
      <mesh position={[0.38, 0.94, 0]}>
        <sphereGeometry args={[0.04, 12, 8]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.65} />
      </mesh>
      
      {/* Sağ dirsek */}
      <mesh position={[-0.38, 0.94, 0]}>
        <sphereGeometry args={[0.04, 12, 8]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.65} />
      </mesh>

      {/* Sol ön kol */}
      <mesh position={[0.42, 0.76, 0]} rotation={[0, 0, 0.15]}>
        <capsuleGeometry args={[0.035, 0.22, 6, 16]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.6} />
      </mesh>
      
      {/* Sağ ön kol */}
      <mesh position={[-0.42, 0.76, 0]} rotation={[0, 0, -0.15]}>
        <capsuleGeometry args={[0.035, 0.22, 6, 16]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.6} />
      </mesh>

      {/* Sol el */}
      <mesh position={[0.46, 0.56, 0]}>
        <boxGeometry args={[0.05, 0.08, 0.025]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.65} />
      </mesh>
      
      {/* Sağ el */}
      <mesh position={[-0.46, 0.56, 0]}>
        <boxGeometry args={[0.05, 0.08, 0.025]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.65} />
      </mesh>

      {/* Sol üst bacak */}
      <mesh position={[0.1, 0.48, 0]}>
        <capsuleGeometry args={[0.065, 0.3, 6, 16]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.55} />
      </mesh>
      
      {/* Sağ üst bacak */}
      <mesh position={[-0.1, 0.48, 0]}>
        <capsuleGeometry args={[0.065, 0.3, 6, 16]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.55} />
      </mesh>

      {/* Sol diz */}
      <mesh position={[0.1, 0.28, 0.015]}>
        <sphereGeometry args={[0.055, 12, 8]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.6} />
      </mesh>
      
      {/* Sağ diz */}
      <mesh position={[-0.1, 0.28, 0.015]}>
        <sphereGeometry args={[0.055, 12, 8]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.6} />
      </mesh>

      {/* Sol baldır */}
      <mesh position={[0.1, 0.06, 0]}>
        <capsuleGeometry args={[0.045, 0.28, 6, 16]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.55} />
      </mesh>
      
      {/* Sağ baldır */}
      <mesh position={[-0.1, 0.06, 0]}>
        <capsuleGeometry args={[0.045, 0.28, 6, 16]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.55} />
      </mesh>

      {/* Sol ayak */}
      <mesh position={[0.1, -0.14, 0.03]}>
        <boxGeometry args={[0.055, 0.04, 0.12]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.65} />
      </mesh>
      
      {/* Sağ ayak */}
      <mesh position={[-0.1, -0.14, 0.03]}>
        <boxGeometry args={[0.055, 0.04, 0.12]} />
        <meshStandardMaterial color={SKIN_COLOR} roughness={0.65} />
      </mesh>
    </group>
  );
}

// Ana bileşen
export function RealisticHumanModel() {
  const groupRef = useRef<Group>(null);
  const store = useAppStore();

  // Hafif sallanma animasyonu (hover yoksa)
  useFrame((state) => {
    if (groupRef.current && !store.hoveredRegion) {
      groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.3) * 0.15;
    }
  });

  const handleRegionClick = (regionId: BodyRegion) => {
    store.setSelectedRegion(regionId);
    store.setCurrentStep('symptom_selection');
  };

  // Hit zone listesi
  const hitZoneList = useMemo(() => {
    return Object.entries(HIT_ZONES).map(([id, zone]) => ({
      id: id as BodyRegion,
      ...zone,
    }));
  }, []);

  return (
    <group ref={groupRef} position={[0, -0.7, 0]}>
      {/* Gerçekçi vücut modeli */}
      <RealisticBody />
      
      {/* Görünmez hit zone'lar (bölge seçimi için) */}
      {hitZoneList.map((zone) => (
        <HitZone
          key={zone.id}
          position={zone.position}
          scale={zone.scale}
          rotation={zone.rotation}
          isSelected={store.selectedRegion === zone.id}
          isHovered={store.hoveredRegion === zone.id}
          onClick={() => handleRegionClick(zone.id)}
          onPointerEnter={() => store.setHoveredRegion(zone.id)}
          onPointerLeave={() => store.setHoveredRegion(null)}
        />
      ))}
    </group>
  );
}
