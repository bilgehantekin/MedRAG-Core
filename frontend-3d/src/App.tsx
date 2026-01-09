import { Scene3D } from './components/Scene3D';
import { SymptomPanel } from './components/SymptomPanel';
import { ChatPanel } from './components/ChatPanel';
import { useAppStore } from './store/useAppStore';

function App() {
  const { currentStep, interactionMode, setInteractionMode, setCurrentStep } = useAppStore();
  const showChat = currentStep === 'chat';
  const showWelcome = currentStep === 'welcome' && interactionMode === null;

  // 3D model ile başla
  const handleModelMode = () => {
    setInteractionMode('model');
    setCurrentStep('body_selection');
  };

  // Direkt chat ile başla
  const handleDirectChatMode = () => {
    setInteractionMode('direct_chat');
    setCurrentStep('chat');
  };

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
        {showWelcome ? (
          // Başlangıç ekranı - mod seçimi
          <div className="h-[calc(100vh-140px)] flex items-center justify-center">
            <div className="max-w-3xl w-full">
              <div className="text-center mb-10">
                <h2 className="text-3xl font-bold text-slate-800 mb-3">
                  Hoş Geldiniz! 👋
                </h2>
                <p className="text-lg text-slate-600">
                  Şikayetinizi nasıl anlatmak istersiniz?
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* 3D Model ile */}
                <button
                  onClick={handleModelMode}
                  className="group bg-white rounded-2xl shadow-lg p-8 hover:shadow-xl transition-all duration-300 border-2 border-transparent hover:border-primary-500 text-left"
                >
                  <div className="text-6xl mb-4 group-hover:scale-110 transition-transform">
                    🧍
                  </div>
                  <h3 className="text-xl font-bold text-slate-800 mb-2">
                    3D Model ile Göster
                  </h3>
                  <p className="text-slate-600 mb-4">
                    İnteraktif 3D insan modeli üzerinde şikayetinizin olduğu bölgeyi seçerek başlayın.
                  </p>
                  <ul className="text-sm text-slate-500 space-y-1">
                    <li>✓ Bölge seçimi</li>
                    <li>✓ Semptom türü seçimi</li>
                    <li>✓ Şiddet ve süre belirleme</li>
                    <li>✓ Yapılandırılmış bilgi girişi</li>
                  </ul>
                  <div className="mt-4 text-primary-600 font-medium group-hover:translate-x-2 transition-transform">
                    Başla →
                  </div>
                </button>

                {/* Direkt Chat ile */}
                <button
                  onClick={handleDirectChatMode}
                  className="group bg-white rounded-2xl shadow-lg p-8 hover:shadow-xl transition-all duration-300 border-2 border-transparent hover:border-primary-500 text-left"
                >
                  <div className="text-6xl mb-4 group-hover:scale-110 transition-transform">
                    💬
                  </div>
                  <h3 className="text-xl font-bold text-slate-800 mb-2">
                    Direkt Yazarak Anlat
                  </h3>
                  <p className="text-slate-600 mb-4">
                    Chatbot'a doğrudan yazarak şikayetlerinizi kendi cümlelerinizle anlatın.
                  </p>
                  <ul className="text-sm text-slate-500 space-y-1">
                    <li>✓ Serbest yazım</li>
                    <li>✓ Doğal dil ile anlatım</li>
                    <li>✓ Hızlı başlangıç</li>
                    <li>✓ Sorulu cevaplı diyalog</li>
                  </ul>
                  <div className="mt-4 text-primary-600 font-medium group-hover:translate-x-2 transition-transform">
                    Başla →
                  </div>
                </button>
              </div>

              <div className="mt-8 text-center text-sm text-slate-500">
                Her iki yöntemde de AI destekli sağlık asistanımız size yardımcı olacak.
              </div>
            </div>
          </div>
        ) : showChat ? (
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
