import { create } from 'zustand';
import { 
  BodyRegion, 
  SymptomType, 
  SeverityLevel, 
  OnsetTime, 
  Trigger, 
  RedFlag, 
  ChatMessage, 
  AppStep,
  SymptomReport,
  InteractionMode 
} from '../types';

interface AppState {
  // Etkileşim modu
  interactionMode: InteractionMode | null;
  setInteractionMode: (mode: InteractionMode | null) => void;

  // Uygulama aşaması
  currentStep: AppStep;
  setCurrentStep: (step: AppStep) => void;

  // 3D model seçimi
  selectedRegion: BodyRegion | null;
  setSelectedRegion: (region: BodyRegion | null) => void;
  hoveredRegion: BodyRegion | null;
  setHoveredRegion: (region: BodyRegion | null) => void;

  // Semptom bilgileri
  selectedSymptom: SymptomType | null;
  setSelectedSymptom: (symptom: SymptomType | null) => void;
  severity: SeverityLevel;
  setSeverity: (level: SeverityLevel) => void;
  onset: OnsetTime | null;
  setOnset: (onset: OnsetTime | null) => void;
  trigger: Trigger | null;
  setTrigger: (trigger: Trigger | null) => void;
  redFlags: RedFlag[];
  toggleRedFlag: (flag: RedFlag) => void;
  additionalNotes: string;
  setAdditionalNotes: (notes: string) => void;

  // Chat
  messages: ChatMessage[];
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  updateLastMessage: (content: string) => void;
  clearMessages: () => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  isStreaming: boolean;
  setIsStreaming: (streaming: boolean) => void;

  // Geçerli semptom raporu
  getCurrentSymptomReport: () => SymptomReport | null;
  
  // Reset
  resetSymptomSelection: () => void;
  resetAll: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  // Etkileşim modu
  interactionMode: null,
  setInteractionMode: (mode) => set({ interactionMode: mode }),

  // Uygulama aşaması
  currentStep: 'welcome',
  setCurrentStep: (step) => set({ currentStep: step }),

  // 3D model seçimi
  selectedRegion: null,
  setSelectedRegion: (region) => set({ selectedRegion: region }),
  hoveredRegion: null,
  setHoveredRegion: (region) => set({ hoveredRegion: region }),

  // Semptom bilgileri
  selectedSymptom: null,
  setSelectedSymptom: (symptom) => set({ selectedSymptom: symptom }),
  severity: 5,
  setSeverity: (level) => set({ severity: level }),
  onset: null,
  setOnset: (onset) => set({ onset: onset }),
  trigger: null,
  setTrigger: (trigger) => set({ trigger: trigger }),
  redFlags: [],
  toggleRedFlag: (flag) => set((state) => ({
    redFlags: state.redFlags.includes(flag)
      ? state.redFlags.filter(f => f !== flag)
      : [...state.redFlags, flag]
  })),
  additionalNotes: '',
  setAdditionalNotes: (notes) => set({ additionalNotes: notes }),

  // Chat
  messages: [],
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, {
      ...message,
      id: crypto.randomUUID(),
      timestamp: new Date()
    }]
  })),
  updateLastMessage: (content) => set((state) => {
    const newMessages = [...state.messages];
    if (newMessages.length > 0) {
      newMessages[newMessages.length - 1] = {
        ...newMessages[newMessages.length - 1],
        content
      };
    }
    return { messages: newMessages };
  }),
  clearMessages: () => set({ messages: [] }),
  isLoading: false,
  setIsLoading: (loading) => set({ isLoading: loading }),
  isStreaming: false,
  setIsStreaming: (streaming) => set({ isStreaming: streaming }),

  // Geçerli semptom raporu
  getCurrentSymptomReport: () => {
    const state = get();
    if (!state.selectedRegion || !state.selectedSymptom || !state.onset) {
      return null;
    }
    return {
      region: state.selectedRegion,
      symptom: state.selectedSymptom,
      severity: state.severity,
      onset: state.onset,
      trigger: state.trigger ?? undefined,
      redFlags: state.redFlags,
      additionalNotes: state.additionalNotes || undefined
    };
  },

  // Reset fonksiyonları
  resetSymptomSelection: () => set({
    selectedRegion: null,
    selectedSymptom: null,
    severity: 5,
    onset: null,
    trigger: null,
    redFlags: [],
    additionalNotes: ''
  }),
  
  resetAll: () => set({
    interactionMode: null,
    currentStep: 'welcome',
    selectedRegion: null,
    hoveredRegion: null,
    selectedSymptom: null,
    severity: 5,
    onset: null,
    trigger: null,
    redFlags: [],
    additionalNotes: '',
    messages: [],
    isLoading: false,
    isStreaming: false
  })
}));
