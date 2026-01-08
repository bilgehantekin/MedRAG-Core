import { Scene3D } from './components/Scene3D';
import { SymptomPanel } from './components/SymptomPanel';
import { ChatPanel } from './components/ChatPanel';
import { useAppStore } from './store/useAppStore';

function App() {
  const { currentStep } = useAppStore();
  const showChat = currentStep === 'chat';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 to-slate-200">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-3xl">🏥</span>
              <div>
                <h1 className="text-xl font-bold text-slate-800">3D Sağlık Asistanı</h1>
                <p className="text-sm text-slate-500">Etkileşimli sağlık bilgilendirme</p>
              </div>
            </div>
            <div className="text-sm text-slate-500">
              v2.0 • 3D + AI
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {showChat ? (
          // Chat görünümü - tam genişlik
          <div className="h-[calc(100vh-140px)]">
            <ChatPanel />
          </div>
        ) : (
          // Seçim görünümü - 3D + Panel
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[calc(100vh-140px)]">
            {/* Sol: 3D Scene */}
            <div className="h-full">
              <Scene3D />
            </div>

            {/* Sağ: Symptom Panel */}
            <div className="h-full overflow-hidden">
              <SymptomPanel />
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="fixed bottom-0 left-0 right-0 bg-white/80 backdrop-blur-sm border-t py-2">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-slate-500">
          ⚠️ Bu uygulama eğitim amaçlıdır, tıbbi tavsiye yerine geçmez. Acil durumlarda <strong>112</strong>'yi arayın.
        </div>
      </footer>
    </div>
  );
}

export default App;
