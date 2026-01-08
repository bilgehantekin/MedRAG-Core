import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Mesh, Group } from 'three';
import { useAppStore } from '../store/useAppStore';
import { BodyRegion } from '../types';
import { BODY_REGIONS } from '../data/bodyData';

interface BodyPartProps {
  regionId: BodyRegion;
  position: [number, number, number];
  scale: [number, number, number];
  isSelected: boolean;
  isHovered: boolean;
  onClick: () => void;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
}

function BodyPart(props: BodyPartProps) {
  const { regionId, position, scale, isSelected, isHovered, onClick, onPointerEnter, onPointerLeave } = props;
  const meshRef = useRef<Mesh>(null);
  const region = BODY_REGIONS[regionId];
  
  const baseColor = region.color;
  const selectedColor = '#00ff88';
  const hoverColor = '#ffff00';
  
  const currentColor = isSelected ? selectedColor : isHovered ? hoverColor : baseColor;
  const emissiveIntensity = isSelected ? 0.5 : isHovered ? 0.3 : 0;

  return (
    <mesh
      ref={meshRef}
      position={position}
      scale={scale}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      onPointerEnter={(e) => { e.stopPropagation(); document.body.style.cursor = 'pointer'; onPointerEnter(); }}
      onPointerLeave={(e) => { e.stopPropagation(); document.body.style.cursor = 'auto'; onPointerLeave(); }}
    >
      <sphereGeometry args={[0.08, 16, 16]} />
      <meshStandardMaterial 
        color={currentColor}
        emissive={currentColor}
        emissiveIntensity={emissiveIntensity}
        transparent
        opacity={isSelected ? 1 : isHovered ? 0.9 : 0.7}
      />
    </mesh>
  );
}

export function HumanModel() {
  const groupRef = useRef<Group>(null);
  const store = useAppStore();

  useFrame((state) => {
    if (groupRef.current && !store.hoveredRegion) {
      groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.3) * 0.2;
    }
  });

  const handleRegionClick = (regionId: BodyRegion) => {
    store.setSelectedRegion(regionId);
    store.setCurrentStep('symptom_selection');
  };

  const bodyParts = [
    { id: 'head' as BodyRegion, position: [0, 1.65, 0] as [number, number, number], scale: [1.8, 1.8, 1.8] as [number, number, number] },
    { id: 'neck' as BodyRegion, position: [0, 1.45, 0] as [number, number, number], scale: [1, 0.8, 1] as [number, number, number] },
    { id: 'chest' as BodyRegion, position: [0, 1.2, 0.05] as [number, number, number], scale: [2.5, 1.5, 1.5] as [number, number, number] },
    { id: 'abdomen' as BodyRegion, position: [0, 0.9, 0.05] as [number, number, number], scale: [2, 1.5, 1.5] as [number, number, number] },
    { id: 'left_shoulder' as BodyRegion, position: [0.25, 1.35, 0] as [number, number, number], scale: [1.2, 1, 1] as [number, number, number] },
    { id: 'right_shoulder' as BodyRegion, position: [-0.25, 1.35, 0] as [number, number, number], scale: [1.2, 1, 1] as [number, number, number] },
    { id: 'left_upper_arm' as BodyRegion, position: [0.35, 1.1, 0] as [number, number, number], scale: [0.8, 1.5, 0.8] as [number, number, number] },
    { id: 'right_upper_arm' as BodyRegion, position: [-0.35, 1.1, 0] as [number, number, number], scale: [0.8, 1.5, 0.8] as [number, number, number] },
    { id: 'left_forearm' as BodyRegion, position: [0.4, 0.8, 0] as [number, number, number], scale: [0.7, 1.3, 0.7] as [number, number, number] },
    { id: 'right_forearm' as BodyRegion, position: [-0.4, 0.8, 0] as [number, number, number], scale: [0.7, 1.3, 0.7] as [number, number, number] },
    { id: 'left_hand' as BodyRegion, position: [0.45, 0.55, 0] as [number, number, number], scale: [0.8, 0.8, 0.5] as [number, number, number] },
    { id: 'right_hand' as BodyRegion, position: [-0.45, 0.55, 0] as [number, number, number], scale: [0.8, 0.8, 0.5] as [number, number, number] },
    { id: 'left_hip' as BodyRegion, position: [0.1, 0.68, 0] as [number, number, number], scale: [1.2, 1, 1] as [number, number, number] },
    { id: 'right_hip' as BodyRegion, position: [-0.1, 0.68, 0] as [number, number, number], scale: [1.2, 1, 1] as [number, number, number] },
    { id: 'left_upper_leg' as BodyRegion, position: [0.12, 0.45, 0] as [number, number, number], scale: [0.9, 1.8, 0.9] as [number, number, number] },
    { id: 'right_upper_leg' as BodyRegion, position: [-0.12, 0.45, 0] as [number, number, number], scale: [0.9, 1.8, 0.9] as [number, number, number] },
    { id: 'left_knee' as BodyRegion, position: [0.12, 0.22, 0.03] as [number, number, number], scale: [0.8, 0.8, 0.8] as [number, number, number] },
    { id: 'right_knee' as BodyRegion, position: [-0.12, 0.22, 0.03] as [number, number, number], scale: [0.8, 0.8, 0.8] as [number, number, number] },
    { id: 'left_shin' as BodyRegion, position: [0.12, 0, 0] as [number, number, number], scale: [0.7, 1.5, 0.7] as [number, number, number] },
    { id: 'right_shin' as BodyRegion, position: [-0.12, 0, 0] as [number, number, number], scale: [0.7, 1.5, 0.7] as [number, number, number] },
    { id: 'left_foot' as BodyRegion, position: [0.12, -0.2, 0.05] as [number, number, number], scale: [0.8, 0.5, 1.2] as [number, number, number] },
    { id: 'right_foot' as BodyRegion, position: [-0.12, -0.2, 0.05] as [number, number, number], scale: [0.8, 0.5, 1.2] as [number, number, number] },
  ];

  return (
    <group ref={groupRef} position={[0, -0.5, 0]}>
      <mesh position={[0, 0.95, 0]}>
        <capsuleGeometry args={[0.15, 0.8, 8, 16]} />
        <meshStandardMaterial color="#2a3f5f" transparent opacity={0.3} />
      </mesh>
      <mesh position={[0, 1.65, 0]}>
        <sphereGeometry args={[0.12, 16, 16]} />
        <meshStandardMaterial color="#2a3f5f" transparent opacity={0.3} />
      </mesh>
      <mesh position={[0.12, 0.2, 0]}>
        <capsuleGeometry args={[0.05, 0.6, 8, 16]} />
        <meshStandardMaterial color="#2a3f5f" transparent opacity={0.3} />
      </mesh>
      <mesh position={[-0.12, 0.2, 0]}>
        <capsuleGeometry args={[0.05, 0.6, 8, 16]} />
        <meshStandardMaterial color="#2a3f5f" transparent opacity={0.3} />
      </mesh>
      <mesh position={[0.35, 0.95, 0]} rotation={[0, 0, Math.PI / 6]}>
        <capsuleGeometry args={[0.03, 0.5, 8, 16]} />
        <meshStandardMaterial color="#2a3f5f" transparent opacity={0.3} />
      </mesh>
      <mesh position={[-0.35, 0.95, 0]} rotation={[0, 0, -Math.PI / 6]}>
        <capsuleGeometry args={[0.03, 0.5, 8, 16]} />
        <meshStandardMaterial color="#2a3f5f" transparent opacity={0.3} />
      </mesh>
      {bodyParts.map((part) => (
        <BodyPart
          key={part.id}
          regionId={part.id}
          position={part.position}
          scale={part.scale}
          isSelected={store.selectedRegion === part.id}
          isHovered={store.hoveredRegion === part.id}
          onClick={() => handleRegionClick(part.id)}
          onPointerEnter={() => store.setHoveredRegion(part.id)}
          onPointerLeave={() => store.setHoveredRegion(null)}
        />
      ))}
    </group>
  );
}
