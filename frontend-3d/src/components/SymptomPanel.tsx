import { useAppStore } from '../store/useAppStore';
import { BODY_REGIONS, SYMPTOMS, ONSET_OPTIONS, TRIGGER_OPTIONS, RED_FLAGS } from '../data/bodyData';

export function SymptomPanel() {
  const {
    currentStep,
    setCurrentStep,
    selectedRegion,
    setSelectedRegion,
    selectedSymptom,
    setSelectedSymptom,
    severity,
    setSeverity,
    onset,
    setOnset,
    trigger,
    setTrigger,
    redFlags,
    toggleRedFlag,
    additionalNotes,
    setAdditionalNotes,
    resetSymptomSelection,
  } = useAppStore();

  const region = selectedRegion ? BODY_REGIONS[selectedRegion] : null;
  const availableSymptoms = region ? region.symptoms : [];

  // Geri dön
  const handleBack = () => {
    switch (currentStep) {
      case 'symptom_selection':
        setSelectedRegion(null);
        setCurrentStep('body_selection');
        break;
      case 'severity_selection':
        setSelectedSymptom(null);
        setCurrentStep('symptom_selection');
        break;
      case 'additional_info':
        setCurrentStep('severity_selection');
        break;
      case 'chat':
        resetSymptomSelection();
        setCurrentStep('body_selection');
        break;
    }
  };

  // İleri git
  const handleNext = () => {
    switch (currentStep) {
      case 'symptom_selection':
        if (selectedSymptom) setCurrentStep('severity_selection');
        break;
      case 'severity_selection':
        setCurrentStep('additional_info');
        break;
      case 'additional_info':
        if (onset) setCurrentStep('chat');
        break;
    }
  };

  // Render switch
  const renderContent = () => {
    switch (currentStep) {
      case 'welcome':
        return <WelcomePanel />;
      case 'body_selection':
        return <BodySelectionHint />;
      case 'symptom_selection':
        return (
          <SymptomSelection 
            region={region}
            availableSymptoms={availableSymptoms}
            selectedSymptom={selectedSymptom}
            onSelect={setSelectedSymptom}
          />
        );
      case 'severity_selection':
        return (
          <SeveritySelection
            severity={severity}
            onSeverityChange={setSeverity}
          />
        );
      case 'additional_info':
        return (
          <AdditionalInfo
            onset={onset}
            onOnsetChange={setOnset}
            trigger={trigger}
            onTriggerChange={setTrigger}
            redFlags={redFlags}
            onToggleRedFlag={toggleRedFlag}
            notes={additionalNotes}
            onNotesChange={setAdditionalNotes}
          />
        );
      default:
        return null;
    }
  };

  if (currentStep === 'chat') return null;

  return (
    <div className="bg-white rounded-2xl shadow-xl p-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        {currentStep !== 'welcome' && currentStep !== 'body_selection' && (
          <button 
            onClick={handleBack}
            className="flex items-center text-slate-500 hover:text-slate-700 transition"
          >
            <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Geri
          </button>
        )}
        <div className="flex-1" />
        {/* Step indicator */}
        <StepIndicator currentStep={currentStep} />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {renderContent()}
      </div>

      {/* Footer navigation */}
      {currentStep !== 'welcome' && currentStep !== 'body_selection' && (
        <div className="mt-6 pt-4 border-t">
          <button
            onClick={handleNext}
            disabled={
              (currentStep === 'symptom_selection' && !selectedSymptom) ||
              (currentStep === 'additional_info' && !onset)
            }
            className="w-full py-3 px-4 bg-primary-600 text-white rounded-xl font-medium
                       hover:bg-primary-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {currentStep === 'additional_info' ? 'Chatbot ile Görüş' : 'Devam Et'}
          </button>
        </div>
      )}
    </div>
  );
}

// Step indicator component
function StepIndicator({ currentStep }: { currentStep: string }) {
  const steps = [
    { id: 'body_selection', label: '1' },
    { id: 'symptom_selection', label: '2' },
    { id: 'severity_selection', label: '3' },
    { id: 'additional_info', label: '4' },
  ];

  const currentIndex = steps.findIndex(s => s.id === currentStep);

  return (
    <div className="flex items-center gap-2">
      {steps.map((step, index) => (
        <div
          key={step.id}
          className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
            ${index <= currentIndex 
              ? 'bg-primary-600 text-white' 
              : 'bg-slate-200 text-slate-500'}`}
        >
          {step.label}
        </div>
      ))}
    </div>
  );
}

// Welcome panel
function WelcomePanel() {
  const { setCurrentStep } = useAppStore();

  return (
    <div className="text-center py-8">
      <div className="text-6xl mb-4">🏥</div>
      <h2 className="text-2xl font-bold text-slate-800 mb-3">3D Sağlık Asistanı</h2>
      <p className="text-slate-600 mb-6">
        3D insan modeli üzerinde ağrıyan bölgeyi seçerek 
        size özel sağlık bilgisi alın.
      </p>
      <button
        onClick={() => setCurrentStep('body_selection')}
        className="py-3 px-8 bg-primary-600 text-white rounded-xl font-medium
                   hover:bg-primary-700 transition shadow-lg shadow-primary-600/30"
      >
        Başla
      </button>
      <div className="mt-8 p-4 bg-amber-50 rounded-xl border border-amber-200">
        <p className="text-amber-800 text-sm">
          ⚠️ Bu uygulama eğitim amaçlıdır ve tıbbi tavsiye yerine geçmez. 
          Acil durumlarda <strong>112</strong>'yi arayın.
        </p>
      </div>
    </div>
  );
}

// Body selection hint
function BodySelectionHint() {
  return (
    <div className="text-center py-8">
      <div className="text-5xl mb-4">👆</div>
      <h3 className="text-xl font-semibold text-slate-800 mb-3">Bölge Seçin</h3>
      <p className="text-slate-600">
        Sol taraftaki 3D model üzerinde ağrıyan veya şikayetinizin olduğu bölgeye tıklayın.
      </p>
      <div className="mt-6 grid grid-cols-2 gap-2 text-sm text-slate-500">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-yellow-400"></span>
          Üzerine gelinen
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-green-400"></span>
          Seçilen
        </div>
      </div>
    </div>
  );
}

// Symptom selection
function SymptomSelection({ 
  region, 
  availableSymptoms, 
  selectedSymptom, 
  onSelect 
}: {
  region: typeof BODY_REGIONS[keyof typeof BODY_REGIONS] | null;
  availableSymptoms: string[];
  selectedSymptom: string | null;
  onSelect: (symptom: any) => void;
}) {
  if (!region) return null;

  return (
    <div>
      <div className="mb-4 p-3 bg-primary-50 rounded-xl">
        <span className="text-primary-800 font-medium">📍 {region.name_tr}</span>
      </div>
      <h3 className="text-lg font-semibold text-slate-800 mb-4">Belirtinizi Seçin</h3>
      <div className="grid grid-cols-2 gap-3">
        {availableSymptoms.map((symptomId) => {
          const symptom = SYMPTOMS[symptomId as keyof typeof SYMPTOMS];
          if (!symptom) return null;
          
          const isSelected = selectedSymptom === symptomId;
          
          return (
            <button
              key={symptomId}
              onClick={() => onSelect(symptomId)}
              className={`p-4 rounded-xl border-2 transition text-left
                ${isSelected 
                  ? 'border-primary-500 bg-primary-50' 
                  : 'border-slate-200 hover:border-slate-300'}`}
            >
              <span className="text-2xl">{symptom.icon}</span>
              <div className="mt-2 font-medium text-slate-800">{symptom.name_tr}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// Severity selection
function SeveritySelection({ 
  severity, 
  onSeverityChange 
}: {
  severity: number;
  onSeverityChange: (value: any) => void;
}) {
  const getSeverityLabel = (value: number) => {
    if (value <= 2) return 'Hafif';
    if (value <= 4) return 'Orta';
    if (value <= 6) return 'Belirgin';
    if (value <= 8) return 'Şiddetli';
    return 'Çok şiddetli';
  };

  const getSeverityColor = (value: number) => {
    if (value <= 2) return 'text-green-600';
    if (value <= 4) return 'text-yellow-600';
    if (value <= 6) return 'text-orange-500';
    if (value <= 8) return 'text-red-500';
    return 'text-red-700';
  };

  return (
    <div>
      <h3 className="text-lg font-semibold text-slate-800 mb-6">Şiddet Derecesi</h3>
      
      <div className="text-center mb-8">
        <div className={`text-5xl font-bold ${getSeverityColor(severity)}`}>
          {severity}
        </div>
        <div className={`text-lg font-medium ${getSeverityColor(severity)}`}>
          {getSeverityLabel(severity)}
        </div>
      </div>

      <input
        type="range"
        min="0"
        max="10"
        value={severity}
        onChange={(e) => onSeverityChange(Number(e.target.value))}
        className="w-full h-3 bg-gradient-to-r from-green-400 via-yellow-400 via-orange-400 to-red-500 
                   rounded-lg appearance-none cursor-pointer"
      />
      
      <div className="flex justify-between text-sm text-slate-500 mt-2">
        <span>0 - Yok</span>
        <span>10 - Dayanılmaz</span>
      </div>
    </div>
  );
}

// Additional info
function AdditionalInfo({
  onset,
  onOnsetChange,
  trigger,
  onTriggerChange,
  redFlags,
  onToggleRedFlag,
  notes,
  onNotesChange
}: {
  onset: string | null;
  onOnsetChange: (value: any) => void;
  trigger: string | null;
  onTriggerChange: (value: any) => void;
  redFlags: string[];
  onToggleRedFlag: (flag: any) => void;
  notes: string;
  onNotesChange: (value: string) => void;
}) {
  return (
    <div className="space-y-6">
      {/* Başlangıç zamanı */}
      <div>
        <h4 className="font-medium text-slate-800 mb-3">Ne zamandır var? *</h4>
        <div className="grid grid-cols-2 gap-2">
          {ONSET_OPTIONS.map((option) => (
            <button
              key={option.id}
              onClick={() => onOnsetChange(option.id)}
              className={`py-2 px-3 rounded-lg text-sm border transition
                ${onset === option.id 
                  ? 'border-primary-500 bg-primary-50 text-primary-700' 
                  : 'border-slate-200 hover:border-slate-300'}`}
            >
              {option.name_tr}
            </button>
          ))}
        </div>
      </div>

      {/* Tetikleyici */}
      <div>
        <h4 className="font-medium text-slate-800 mb-3">Tetikleyici (opsiyonel)</h4>
        <div className="grid grid-cols-2 gap-2">
          {TRIGGER_OPTIONS.map((option) => (
            <button
              key={option.id}
              onClick={() => onTriggerChange(trigger === option.id ? null : option.id)}
              className={`py-2 px-3 rounded-lg text-sm border transition
                ${trigger === option.id 
                  ? 'border-primary-500 bg-primary-50 text-primary-700' 
                  : 'border-slate-200 hover:border-slate-300'}`}
            >
              {option.name_tr}
            </button>
          ))}
        </div>
      </div>

      {/* Kırmızı bayraklar */}
      <div>
        <h4 className="font-medium text-slate-800 mb-3">
          🚨 Acil belirtiler (varsa seçin)
        </h4>
        <div className="space-y-2">
          {RED_FLAGS.slice(0, 6).map((flag) => (
            <label
              key={flag.id}
              className={`flex items-center p-3 rounded-lg border cursor-pointer transition
                ${redFlags.includes(flag.id) 
                  ? 'border-red-500 bg-red-50' 
                  : 'border-slate-200 hover:border-slate-300'}`}
            >
              <input
                type="checkbox"
                checked={redFlags.includes(flag.id)}
                onChange={() => onToggleRedFlag(flag.id)}
                className="sr-only"
              />
              <span className={`w-5 h-5 rounded border-2 mr-3 flex items-center justify-center
                ${redFlags.includes(flag.id) 
                  ? 'border-red-500 bg-red-500 text-white' 
                  : 'border-slate-300'}`}>
                {redFlags.includes(flag.id) && '✓'}
              </span>
              <span className="text-sm">{flag.name_tr}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Ek notlar */}
      <div>
        <h4 className="font-medium text-slate-800 mb-3">Ek notlar (opsiyonel)</h4>
        <textarea
          value={notes}
          onChange={(e) => onNotesChange(e.target.value)}
          placeholder="Başka belirtmek istediğiniz bir şey var mı?"
          className="w-full p-3 border border-slate-200 rounded-lg resize-none h-20
                     focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
      </div>
    </div>
  );
}
