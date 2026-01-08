import { RegionInfo, SymptomInfo, BodyRegion, SymptomType } from '../types';

// Vücut bölgeleri haritası
export const BODY_REGIONS: Record<BodyRegion, RegionInfo> = {
  head: {
    id: 'head',
    name_tr: 'Baş',
    name_en: 'Head',
    symptoms: ['pain', 'numbness', 'tingling', 'swelling', 'cut', 'rash'],
    position: [0, 1.7, 0],
    color: '#FFB6C1'
  },
  neck: {
    id: 'neck',
    name_tr: 'Boyun',
    name_en: 'Neck',
    symptoms: ['pain', 'stiffness', 'swelling', 'numbness'],
    position: [0, 1.5, 0],
    color: '#DDA0DD'
  },
  chest: {
    id: 'chest',
    name_tr: 'Göğüs',
    name_en: 'Chest',
    symptoms: ['pain', 'tightness', 'swelling', 'rash'],
    position: [0, 1.2, 0],
    color: '#87CEEB'
  },
  abdomen: {
    id: 'abdomen',
    name_tr: 'Karın',
    name_en: 'Abdomen',
    symptoms: ['pain', 'swelling', 'cramp', 'numbness'],
    position: [0, 0.9, 0],
    color: '#98FB98'
  },
  back_upper: {
    id: 'back_upper',
    name_tr: 'Üst Sırt',
    name_en: 'Upper Back',
    symptoms: ['pain', 'stiffness', 'numbness', 'cramp'],
    position: [0, 1.2, -0.15],
    color: '#DEB887'
  },
  back_lower: {
    id: 'back_lower',
    name_tr: 'Bel',
    name_en: 'Lower Back',
    symptoms: ['pain', 'stiffness', 'numbness', 'cramp', 'weakness'],
    position: [0, 0.85, -0.15],
    color: '#F0E68C'
  },
  left_shoulder: {
    id: 'left_shoulder',
    name_tr: 'Sol Omuz',
    name_en: 'Left Shoulder',
    symptoms: ['pain', 'stiffness', 'swelling', 'weakness'],
    position: [0.35, 1.35, 0],
    color: '#FFD700'
  },
  right_shoulder: {
    id: 'right_shoulder',
    name_tr: 'Sağ Omuz',
    name_en: 'Right Shoulder',
    symptoms: ['pain', 'stiffness', 'swelling', 'weakness'],
    position: [-0.35, 1.35, 0],
    color: '#FFD700'
  },
  left_upper_arm: {
    id: 'left_upper_arm',
    name_tr: 'Sol Üst Kol',
    name_en: 'Left Upper Arm',
    symptoms: ['pain', 'swelling', 'bruise', 'numbness', 'weakness'],
    position: [0.45, 1.1, 0],
    color: '#FF7F50'
  },
  right_upper_arm: {
    id: 'right_upper_arm',
    name_tr: 'Sağ Üst Kol',
    name_en: 'Right Upper Arm',
    symptoms: ['pain', 'swelling', 'bruise', 'numbness', 'weakness'],
    position: [-0.45, 1.1, 0],
    color: '#FF7F50'
  },
  left_forearm: {
    id: 'left_forearm',
    name_tr: 'Sol Ön Kol',
    name_en: 'Left Forearm',
    symptoms: ['pain', 'swelling', 'bruise', 'numbness', 'cut'],
    position: [0.55, 0.8, 0],
    color: '#20B2AA'
  },
  right_forearm: {
    id: 'right_forearm',
    name_tr: 'Sağ Ön Kol',
    name_en: 'Right Forearm',
    symptoms: ['pain', 'swelling', 'bruise', 'numbness', 'cut'],
    position: [-0.55, 0.8, 0],
    color: '#20B2AA'
  },
  left_hand: {
    id: 'left_hand',
    name_tr: 'Sol El',
    name_en: 'Left Hand',
    symptoms: ['pain', 'swelling', 'numbness', 'tingling', 'cut', 'burn'],
    position: [0.6, 0.5, 0],
    color: '#FF69B4'
  },
  right_hand: {
    id: 'right_hand',
    name_tr: 'Sağ El',
    name_en: 'Right Hand',
    symptoms: ['pain', 'swelling', 'numbness', 'tingling', 'cut', 'burn'],
    position: [-0.6, 0.5, 0],
    color: '#FF69B4'
  },
  left_hip: {
    id: 'left_hip',
    name_tr: 'Sol Kalça',
    name_en: 'Left Hip',
    symptoms: ['pain', 'stiffness', 'numbness', 'weakness'],
    position: [0.15, 0.65, 0],
    color: '#BA55D3'
  },
  right_hip: {
    id: 'right_hip',
    name_tr: 'Sağ Kalça',
    name_en: 'Right Hip',
    symptoms: ['pain', 'stiffness', 'numbness', 'weakness'],
    position: [-0.15, 0.65, 0],
    color: '#BA55D3'
  },
  left_upper_leg: {
    id: 'left_upper_leg',
    name_tr: 'Sol Üst Bacak',
    name_en: 'Left Upper Leg',
    symptoms: ['pain', 'swelling', 'cramp', 'numbness', 'bruise'],
    position: [0.15, 0.45, 0],
    color: '#4682B4'
  },
  right_upper_leg: {
    id: 'right_upper_leg',
    name_tr: 'Sağ Üst Bacak',
    name_en: 'Right Upper Leg',
    symptoms: ['pain', 'swelling', 'cramp', 'numbness', 'bruise'],
    position: [-0.15, 0.45, 0],
    color: '#4682B4'
  },
  left_knee: {
    id: 'left_knee',
    name_tr: 'Sol Diz',
    name_en: 'Left Knee',
    symptoms: ['pain', 'swelling', 'stiffness', 'weakness'],
    position: [0.15, 0.25, 0],
    color: '#32CD32'
  },
  right_knee: {
    id: 'right_knee',
    name_tr: 'Sağ Diz',
    name_en: 'Right Knee',
    symptoms: ['pain', 'swelling', 'stiffness', 'weakness'],
    position: [-0.15, 0.25, 0],
    color: '#32CD32'
  },
  left_shin: {
    id: 'left_shin',
    name_tr: 'Sol Kaval Kemiği',
    name_en: 'Left Shin (Tibia)',
    symptoms: ['pain', 'swelling', 'bruise', 'numbness', 'cramp'],
    position: [0.15, 0.1, 0],
    color: '#FF4500'
  },
  right_shin: {
    id: 'right_shin',
    name_tr: 'Sağ Kaval Kemiği',
    name_en: 'Right Shin (Tibia)',
    symptoms: ['pain', 'swelling', 'bruise', 'numbness', 'cramp'],
    position: [-0.15, 0.1, 0],
    color: '#FF4500'
  },
  left_foot: {
    id: 'left_foot',
    name_tr: 'Sol Ayak',
    name_en: 'Left Foot',
    symptoms: ['pain', 'swelling', 'numbness', 'tingling', 'cut', 'burn'],
    position: [0.15, -0.1, 0],
    color: '#8A2BE2'
  },
  right_foot: {
    id: 'right_foot',
    name_tr: 'Sağ Ayak',
    name_en: 'Right Foot',
    symptoms: ['pain', 'swelling', 'numbness', 'tingling', 'cut', 'burn'],
    position: [-0.15, -0.1, 0],
    color: '#8A2BE2'
  }
};

// Semptom detayları
export const SYMPTOMS: Record<SymptomType, SymptomInfo> = {
  pain: {
    id: 'pain',
    name_tr: 'Ağrı',
    name_en: 'Pain',
    icon: '🤕'
  },
  swelling: {
    id: 'swelling',
    name_tr: 'Şişlik',
    name_en: 'Swelling',
    icon: '🔴'
  },
  numbness: {
    id: 'numbness',
    name_tr: 'Uyuşma',
    name_en: 'Numbness',
    icon: '😶'
  },
  tingling: {
    id: 'tingling',
    name_tr: 'Karıncalanma',
    name_en: 'Tingling',
    icon: '✨'
  },
  bruise: {
    id: 'bruise',
    name_tr: 'Morluk',
    name_en: 'Bruise',
    icon: '💜'
  },
  cut: {
    id: 'cut',
    name_tr: 'Kesik',
    name_en: 'Cut',
    icon: '🩹'
  },
  burn: {
    id: 'burn',
    name_tr: 'Yanık',
    name_en: 'Burn',
    icon: '🔥'
  },
  rash: {
    id: 'rash',
    name_tr: 'Döküntü',
    name_en: 'Rash',
    icon: '🔶'
  },
  stiffness: {
    id: 'stiffness',
    name_tr: 'Sertlik/Tutulma',
    name_en: 'Stiffness',
    icon: '🔒'
  },
  weakness: {
    id: 'weakness',
    name_tr: 'Güçsüzlük',
    name_en: 'Weakness',
    icon: '💫'
  },
  cramp: {
    id: 'cramp',
    name_tr: 'Kramp',
    name_en: 'Cramp',
    icon: '⚡'
  },
  bleeding: {
    id: 'bleeding',
    name_tr: 'Kanama',
    name_en: 'Bleeding',
    icon: '🩸'
  }
};

// Başlangıç zamanı seçenekleri
export const ONSET_OPTIONS = [
  { id: 'just_now', name_tr: 'Az önce', name_en: 'Just now' },
  { id: 'few_hours', name_tr: 'Birkaç saat önce', name_en: 'Few hours ago' },
  { id: 'today', name_tr: 'Bugün', name_en: 'Today' },
  { id: '1_day', name_tr: '1 gün', name_en: '1 day' },
  { id: '2_3_days', name_tr: '2-3 gün', name_en: '2-3 days' },
  { id: '1_week', name_tr: '1 hafta', name_en: '1 week' },
  { id: 'more_than_week', name_tr: '1 haftadan fazla', name_en: 'More than a week' },
  { id: 'chronic', name_tr: 'Kronik (sürekli)', name_en: 'Chronic' }
];

// Tetikleyici seçenekleri
export const TRIGGER_OPTIONS = [
  { id: 'injury', name_tr: 'Darbe/Yaralanma', name_en: 'Injury' },
  { id: 'after_exercise', name_tr: 'Egzersiz sonrası', name_en: 'After exercise' },
  { id: 'after_running', name_tr: 'Koşu sonrası', name_en: 'After running' },
  { id: 'after_eating', name_tr: 'Yemek sonrası', name_en: 'After eating' },
  { id: 'stress', name_tr: 'Stres', name_en: 'Stress' },
  { id: 'morning', name_tr: 'Sabahları', name_en: 'In the morning' },
  { id: 'evening', name_tr: 'Akşamları', name_en: 'In the evening' },
  { id: 'unknown', name_tr: 'Bilmiyorum', name_en: 'Unknown' }
];

// Kırmızı bayraklar
export const RED_FLAGS = [
  { id: 'cannot_bear_weight', name_tr: 'Üzerine basamıyorum', name_en: 'Cannot bear weight' },
  { id: 'severe_pain', name_tr: 'Çok şiddetli ağrı', name_en: 'Severe pain' },
  { id: 'visible_deformity', name_tr: 'Görünür şekil bozukluğu', name_en: 'Visible deformity' },
  { id: 'loss_of_consciousness', name_tr: 'Bilinç kaybı', name_en: 'Loss of consciousness' },
  { id: 'difficulty_breathing', name_tr: 'Nefes almada zorluk', name_en: 'Difficulty breathing' },
  { id: 'chest_pain', name_tr: 'Göğüs ağrısı', name_en: 'Chest pain' },
  { id: 'high_fever', name_tr: 'Yüksek ateş', name_en: 'High fever' },
  { id: 'confusion', name_tr: 'Konfüzyon/Bilinç bulanıklığı', name_en: 'Confusion' },
  { id: 'severe_bleeding', name_tr: 'Şiddetli kanama', name_en: 'Severe bleeding' },
  { id: 'numbness_spreading', name_tr: 'Yayılan uyuşma', name_en: 'Spreading numbness' }
];
