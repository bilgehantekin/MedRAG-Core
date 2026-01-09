import { useState, useRef, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { BODY_REGIONS, SYMPTOMS, ONSET_OPTIONS, TRIGGER_OPTIONS, RED_FLAGS } from '../data/bodyData';
import { SymptomReport } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function ChatPanel() {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const initialMessageSent = useRef(false); // Çift mesaj gönderimini önlemek için
  
  const {
    messages,
    addMessage,
    isLoading,
    setIsLoading,
    getCurrentSymptomReport,
    selectedRegion,
    selectedSymptom,
    setCurrentStep,
    resetSymptomSelection,
    interactionMode,
    resetAll
  } = useAppStore();

  const symptomReport = getCurrentSymptomReport();
  const isDirectChatMode = interactionMode === 'direct_chat';

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Direkt chat modunda hoş geldin mesajı göster
  useEffect(() => {
    if (isDirectChatMode && messages.length === 0 && !initialMessageSent.current) {
      initialMessageSent.current = true;
      addMessage({
        role: 'assistant',
        content: `Merhaba! 👋 Ben sağlık asistanınızım.

Size yardımcı olmak için buradayım. Lütfen şikayetlerinizi kendi cümlelerinizle anlatın. Örneğin:

• "Başım çok ağrıyor, midem bulanıyor"
• "Dün akşamdan beri sırtımda ağrı var"  
• "Sol dizim şişti, hareket ettiremiyorum"
• "Bir haftadır öksürüğüm var, ateşim çıkıyor"

Ne kadar detay verirseniz, size o kadar doğru bilgi verebilirim. Şikayetiniz nedir?`
      });
    }
  }, [isDirectChatMode]);

  // 3D model modunda ilk mesajı gönder (symptom report ile) - sadece 1 kere
  useEffect(() => {
    if (!isDirectChatMode && symptomReport && messages.length === 0 && !initialMessageSent.current) {
      initialMessageSent.current = true;
      sendInitialMessage(symptomReport);
    }
  }, [symptomReport, isDirectChatMode]);

  // İlk otomatik mesaj
  const sendInitialMessage = async (report: SymptomReport) => {
    const region = BODY_REGIONS[report.region];
    const symptom = SYMPTOMS[report.symptom];
    const onset = ONSET_OPTIONS.find(o => o.id === report.onset);
    const trigger = report.trigger ? TRIGGER_OPTIONS.find(t => t.id === report.trigger) : null;
    const flags = report.redFlags.map(f => RED_FLAGS.find(r => r.id === f)?.name_tr).filter(Boolean);

    // Kullanıcı mesajını oluştur
    let userMessage = `${region.name_tr} bölgemde ${symptom.name_tr.toLowerCase()} var.`;
    userMessage += ` Şiddeti 10 üzerinden ${report.severity}.`;
    userMessage += ` ${onset?.name_tr || ''} başladı.`;
    if (trigger) userMessage += ` ${trigger.name_tr} sonrası ortaya çıktı.`;
    if (flags.length > 0) userMessage += ` Ayrıca: ${flags.join(', ')}.`;
    if (report.additionalNotes) userMessage += ` ${report.additionalNotes}`;

    addMessage({
      role: 'user',
      content: userMessage,
      symptomContext: report
    });

    // API'ye gönder
    await sendToAPI(userMessage, report);
  };

  // Yapısal context'i API'ye gönder
  const sendToAPI = async (userMessage: string, report?: SymptomReport) => {
    setIsLoading(true);

    try {
      // History'yi hazırla
      const history = messages.slice(-10).map(m => ({
        role: m.role,
        content: m.content
      }));

      // Body oluştur - yapısal context ile
      const body: any = {
        message: userMessage,
        history
      };

      // Eğer symptom report varsa, context olarak ekle
      if (report) {
        body.symptom_context = {
          region: report.region,
          region_name_tr: BODY_REGIONS[report.region].name_tr,
          region_name_en: BODY_REGIONS[report.region].name_en,
          symptom: report.symptom,
          symptom_name_tr: SYMPTOMS[report.symptom].name_tr,
          symptom_name_en: SYMPTOMS[report.symptom].name_en,
          severity_0_10: report.severity,
          onset: report.onset,
          trigger: report.trigger || null,
          red_flags: report.redFlags
        };
      }

      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        throw new Error('API hatası');
      }

      const data = await response.json();

      addMessage({
        role: 'assistant',
        content: data.response,
        isEmergency: data.is_emergency
      });

    } catch (error) {
      console.error('Chat error:', error);
      addMessage({
        role: 'assistant',
        content: '❌ Bir hata oluştu. Lütfen tekrar deneyin.'
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Mesaj gönder
  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    setInput('');
    addMessage({ role: 'user', content: text });
    await sendToAPI(text);
  };

  // Enter ile gönder
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Yeni şikayet
  const handleNewComplaint = () => {
    initialMessageSent.current = false; // Yeni şikayet için ref'i sıfırla
    if (isDirectChatMode) {
      // Direkt chat modunda: sadece mesajları temizle ve yeni hoş geldin mesajı göster
      resetSymptomSelection();
      useAppStore.getState().clearMessages();
    } else {
      // 3D model modunda: başa dön
      resetSymptomSelection();
      setCurrentStep('body_selection');
    }
  };

  // Ana sayfaya dön
  const handleBackToHome = () => {
    initialMessageSent.current = false;
    resetAll();
  };

  // Mesaj formatla
  const formatMessage = (text: string) => {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/^### (.*$)/gm, '<h4 class="font-semibold text-lg mt-3 mb-2">$1</h4>')
      .replace(/^## (.*$)/gm, '<h3 class="font-bold text-xl mt-4 mb-2">$1</h3>')
      .replace(/^[•\-\*] (.*$)/gm, '<div class="flex items-start gap-2 my-1"><span class="text-primary-500">•</span><span>$1</span></div>')
      .replace(/^(\d+)\. (.*$)/gm, '<div class="flex items-start gap-2 my-1"><span class="font-medium text-primary-600">$1.</span><span>$2</span></div>')
      .replace(/^(⚠️.*?)$/gm, '<div class="bg-amber-50 p-2 rounded-lg text-amber-800 my-2">$1</div>')
      .replace(/\n(?!<)/g, '<br/>');
  };

  const region = selectedRegion ? BODY_REGIONS[selectedRegion] : null;
  const symptom = selectedSymptom ? SYMPTOMS[selectedSymptom] : null;

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl shadow-xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 bg-gradient-to-r from-primary-600 to-primary-700 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-lg">🏥 Sağlık Asistanı</h2>
            {isDirectChatMode ? (
              <p className="text-primary-100 text-sm">
                💬 Serbest yazım modu
              </p>
            ) : region && symptom ? (
              <p className="text-primary-100 text-sm">
                📍 {region.name_tr} • {symptom.icon} {symptom.name_tr}
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleNewComplaint}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm transition"
              title={isDirectChatMode ? "Sohbeti sıfırla" : "Yeni şikayet"}
            >
              {isDirectChatMode ? '🔄 Sıfırla' : '+ Yeni Şikayet'}
            </button>
            <button
              onClick={handleBackToHome}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm transition"
              title="Ana sayfaya dön"
            >
              🏠 Ana Sayfa
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                message.role === 'user'
                  ? 'bg-primary-600 text-white'
                  : message.isEmergency
                  ? 'bg-red-50 border border-red-200'
                  : 'bg-slate-100'
              }`}
            >
              {message.role === 'assistant' && (
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xl">🏥</span>
                  <span className="font-medium text-slate-700">Sağlık Asistanı</span>
                </div>
              )}
              <div 
                className={message.role === 'user' ? '' : 'text-slate-700'}
                dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }}
              />
              {message.role === 'assistant' && !message.isEmergency && (
                <div className="mt-3 pt-2 border-t border-slate-200 text-xs text-slate-500">
                  ⚠️ Bu bilgiler eğitim amaçlıdır, tıbbi tavsiye değildir.
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-slate-100 rounded-2xl px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="text-xl">🏥</span>
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t bg-slate-50">
        <div className="flex gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Sorunuzu yazın..."
            rows={1}
            className="flex-1 px-4 py-3 border border-slate-200 rounded-xl resize-none
                       focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="px-5 py-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700
                       disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
