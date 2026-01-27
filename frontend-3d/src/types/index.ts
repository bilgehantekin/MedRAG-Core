// Vücut bölgeleri
export type BodyRegion = 
  | 'head'
  | 'neck'
  | 'chest'
  | 'abdomen'
  | 'back_upper'
  | 'back_lower'
  | 'left_shoulder'
  | 'right_shoulder'
  | 'left_upper_arm'
  | 'right_upper_arm'
  | 'left_forearm'
  | 'right_forearm'
  | 'left_hand'
  | 'right_hand'
  | 'left_hip'
  | 'right_hip'
  | 'left_upper_leg'
  | 'right_upper_leg'
  | 'left_knee'
  | 'right_knee'
  | 'left_shin'  // sol kaval kemiği (tibia)
  | 'right_shin'
  | 'left_foot'
  | 'right_foot';

// Bölge detayları
export interface RegionInfo {
  id: BodyRegion;
  name_tr: string;
  name_en: string;
  symptoms: SymptomType[];
  position: [number, number, number]; // 3D pozisyon
  color: string;
}

// Semptom türleri
export type SymptomType =
  | 'pain'
  | 'swelling'
  | 'numbness'
  | 'tingling'
  | 'bruise'
  | 'cut'
  | 'burn'
  | 'rash'
  | 'stiffness'
  | 'tightness'
  | 'weakness'
  | 'cramp'
  | 'bleeding';

// Semptom detayları
export interface SymptomInfo {
  id: SymptomType;
  name_tr: string;
  name_en: string;
  icon: string;
}

// Şiddet seviyesi
export type SeverityLevel = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;

// Başlangıç zamanı
export type OnsetTime = 
  | 'just_now'
  | 'few_hours'
  | 'today'
  | '1_day'
  | '2_3_days'
  | '1_week'
  | 'more_than_week'
  | 'chronic';

// Tetikleyici
export type Trigger = 
  | 'injury'
  | 'after_exercise'
  | 'after_running'
  | 'after_eating'
  | 'stress'
  | 'morning'
  | 'evening'
  | 'unknown';

// Kırmızı bayraklar (acil durumlar)
export type RedFlag = 
  | 'cannot_bear_weight'
  | 'severe_pain'
  | 'visible_deformity'
  | 'loss_of_consciousness'
  | 'difficulty_breathing'
  | 'chest_pain'
  | 'high_fever'
  | 'confusion'
  | 'severe_bleeding'
  | 'numbness_spreading';

// Kullanıcı semptom raporu
export interface SymptomReport {
  region: BodyRegion;
  symptom: SymptomType;
  severity: SeverityLevel;
  onset: OnsetTime;
  trigger?: Trigger;
  redFlags: RedFlag[];
  additionalNotes?: string;
}

// Chat mesajı
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  content_en?: string;  // İngilizce versiyon (drift önleme için)
  timestamp: Date;
  symptomContext?: SymptomReport;
  isEmergency?: boolean;
  imageUrl?: string;  // İlaç görseli için base64 URL
}

// Etkileşim modu
export type InteractionMode = 
  | 'model'      // 3D model ile bölge seçerek
  | 'direct_chat'; // Direkt chatbot ile yazarak

// Uygulama aşaması
export type AppStep = 
  | 'welcome'
  | 'body_selection'
  | 'symptom_selection'
  | 'severity_selection'
  | 'additional_info'
  | 'chat';
