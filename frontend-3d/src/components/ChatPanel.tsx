import { useState, useRef, useEffect, useCallback } from 'react';
import { useAppStore } from '../store/useAppStore';
import { BODY_REGIONS, SYMPTOMS } from '../data/bodyData';
import { SymptomReport } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Streaming hızı (ms cinsinden karakter başına gecikme)
const STREAM_SPEED = 8; // Hızlı ama okunabilir

export function ChatPanel() {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const initialMessageSent = useRef(false);
  const isUserScrolledUp = useRef(false);
  
  const {
    messages,
    addMessage,
    updateLastMessage,
    isLoading,
    setIsLoading,
    isStreaming,
    setIsStreaming,
    getCurrentSymptomReport,
    selectedRegion,
    selectedSymptom,
    setCurrentStep,
    resetSymptomSelection,
    interactionMode,
    resetAll,
    useRag,
    setUseRag
  } = useAppStore();

  const symptomReport = getCurrentSymptomReport();
  const isDirectChatMode = interactionMode === 'direct_chat';

  // Kullanıcı scroll durumunu takip et
  const handleScroll = useCallback(() => {
    if (messagesContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
      // Eğer kullanıcı en alttan 100px'den fazla yukarıdaysa
      isUserScrolledUp.current = scrollHeight - scrollTop - clientHeight > 100;
    }
  }, []);

  // Akıllı auto-scroll - sadece kullanıcı yukarı scroll yapmadıysa
  const scrollToBottom = useCallback((force = false) => {
    if (force || !isUserScrolledUp.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  // Yeni mesaj geldiğinde scroll
  useEffect(() => {
    // Kullanıcı mesajı geldiğinde her zaman scroll yap
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.role === 'user') {
      scrollToBottom(true);
    }
  }, [messages.length]);

  // Streaming efekti ile mesaj göster
  const streamMessage = useCallback(async (fullContent: string, isEmergency?: boolean, contentEn?: string) => {
    setIsStreaming(true);

    // Boş mesaj ile başla - content_en dahil (drift önleme için)
    addMessage({
      role: 'assistant',
      content: '',
      content_en: contentEn,
      isEmergency
    });

    // Karakterleri kademeli olarak ekle
    let currentIndex = 0;
    const totalLength = fullContent.length;
    
    // Chunk boyutu - daha hızlı görünmesi için birkaç karakter birden
    const chunkSize = 3;
    
    while (currentIndex < totalLength) {
      const nextIndex = Math.min(currentIndex + chunkSize, totalLength);
      const currentContent = fullContent.slice(0, nextIndex);
      
      updateLastMessage(currentContent);
      currentIndex = nextIndex;
      
      // Scroll - her 50 karakterde bir kontrol et
      if (currentIndex % 50 === 0 || currentIndex >= totalLength) {
        scrollToBottom();
      }
      
      // Gecikme
      await new Promise(resolve => setTimeout(resolve, STREAM_SPEED));
    }
    
    setIsStreaming(false);
    scrollToBottom();
  }, [addMessage, updateLastMessage, setIsStreaming, scrollToBottom]);

  // Direkt chat modunda hoş geldin mesajı göster
  useEffect(() => {
    if (isDirectChatMode && messages.length === 0 && !initialMessageSent.current) {
      initialMessageSent.current = true;
      const welcomeMessage = `Merhaba! 👋 Ben sağlık asistanınızım.

Size yardımcı olmak için buradayım. Lütfen şikayetlerinizi kendi cümlelerinizle anlatın. Örneğin:

• "Başım çok ağrıyor, midem bulanıyor"
• "Dün akşamdan beri sırtımda ağrı var"  
• "Sol dizim şişti, hareket ettiremiyorum"
• "Bir haftadır öksürüğüm var, ateşim çıkıyor"

Ne kadar detay verirseniz, size o kadar doğru bilgi verebilirim. Şikayetiniz nedir?`;
      streamMessage(welcomeMessage);
    }
  }, [isDirectChatMode, streamMessage]);

  // 3D model modunda ilk mesajı gönder (symptom report ile) - sadece 1 kere
  useEffect(() => {
    if (!isDirectChatMode && symptomReport && messages.length === 0 && !initialMessageSent.current) {
      initialMessageSent.current = true;
      sendInitialMessage(symptomReport);
    }
  }, [symptomReport, isDirectChatMode]);

  // Başlangıç zamanı için Türkçe cümle oluştur
  const getOnsetMessage = (onsetId: string): string => {
    const onsetMessages: Record<string, string> = {
      'just_now': 'Az önce başladı.',
      'few_hours': 'Birkaç saat önce başladı.',
      'today': 'Bugün başladı.',
      '1_day': 'Yaklaşık 1 gündür var.',
      '2_3_days': '2-3 gündür devam ediyor.',
      '1_week': 'Yaklaşık 1 haftadır var.',
      'more_than_week': '1 haftadan uzun süredir devam ediyor.',
      'chronic': 'Kronik bir şikayetim, sürekli yaşıyorum.'
    };
    return onsetMessages[onsetId] || '';
  };

  // Tetikleyici için Türkçe cümle oluştur
  const getTriggerMessage = (triggerId: string): string => {
    const triggerMessages: Record<string, string> = {
      'injury': 'Bir darbe veya yaralanma sonrası oluştu.',
      'after_exercise': 'Egzersiz yaptıktan sonra ortaya çıktı.',
      'after_running': 'Koştuktan sonra başladı.',
      'after_eating': 'Yemek yedikten sonra başladı.',
      'stress': 'Stresli bir dönemde ortaya çıktı.',
      'morning': 'Genellikle sabahları daha belirgin.',
      'evening': 'Genellikle akşamları daha belirgin.',
      'unknown': 'Ne zaman veya neden başladığını bilmiyorum.'
    };
    return triggerMessages[triggerId] || '';
  };

  // Kırmızı bayraklar için Türkçe cümle oluştur
  const getRedFlagMessage = (flagId: string): string => {
    const flagMessages: Record<string, string> = {
      'cannot_bear_weight': 'Üzerine basamıyorum.',
      'severe_pain': 'Ağrı çok şiddetli.',
      'visible_deformity': 'Görünür bir şekil bozukluğu var.',
      'loss_of_consciousness': 'Bilinç kaybı yaşadım.',
      'difficulty_breathing': 'Nefes almakta zorlanıyorum.',
      'chest_pain': 'Göğsümde ağrı var.',
      'high_fever': 'Yüksek ateşim var.',
      'confusion': 'Bilinç bulanıklığı yaşıyorum.',
      'severe_bleeding': 'Şiddetli kanama var.',
      'numbness_spreading': 'Uyuşukluk yayılıyor.'
    };
    return flagMessages[flagId] || '';
  };

  // İlk otomatik mesaj
  const sendInitialMessage = async (report: SymptomReport) => {
    const region = BODY_REGIONS[report.region];
    const symptom = SYMPTOMS[report.symptom];

    // Kullanıcı mesajını oluştur
    let userMessage = `${region.name_tr} bölgemde ${symptom.name_tr.toLowerCase()} var.`;
    userMessage += ` Şiddeti 10 üzerinden ${report.severity}.`;
    userMessage += ` ${getOnsetMessage(report.onset)}`;
    if (report.trigger) userMessage += ` ${getTriggerMessage(report.trigger)}`;
    if (report.redFlags.length > 0) {
      const flagMessages = report.redFlags.map(f => getRedFlagMessage(f)).filter(Boolean);
      userMessage += ` ${flagMessages.join(' ')}`;
    }
    if (report.additionalNotes) userMessage += ` ${report.additionalNotes}`;

    addMessage({
      role: 'user',
      content: userMessage,
      symptomContext: report
    });

    // API'ye gönder
    await sendToAPI(userMessage, report);
  };

  // RAG kaynaklarını formatla
  const formatSources = (sources: Array<{title: string, source: string, category: string, relevance_score: number}>) => {
    if (!sources || sources.length === 0) return '';

    const sourceLines = sources
      .filter(s => s.relevance_score > 0.3) // Sadece yüksek ilgili kaynaklar
      .slice(0, 3) // Maksimum 3 kaynak
      .map(s => `• ${s.title} (${s.source})`)
      .join('\n');

    if (!sourceLines) return '';
    return `\n\n📚 **Kaynaklar:**\n${sourceLines}`;
  };

  // Yapısal context'i API'ye gönder
  const sendToAPI = async (userMessage: string, report?: SymptomReport) => {
    setIsLoading(true);

    try {
      // History'yi hazırla (content_en dahil - drift önleme için)
      const history = messages.slice(-10).map(m => ({
        role: m.role,
        content: m.content,
        content_en: m.content_en  // Backend'e geri gönder
      }));

      let responseText = '';
      let responseEn: string | undefined = undefined;  // Drift önleme için
      let isEmergency = false;

      if (useRag) {
        // RAG endpoint'ini kullan
        const ragBody = {
          message: userMessage,
          history,
          use_rag: true,
          max_sources: 5
        };

        const response = await fetch(`${API_URL}/rag/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(ragBody)
        });

        if (!response.ok) {
          throw new Error('RAG API hatası');
        }

        const data = await response.json();
        responseText = data.response;
        responseEn = data.response_en;  // İngilizce cevabı sakla (drift önleme)

        // Kaynakları ekle (varsa)
        if (data.rag_used && data.sources && data.sources.length > 0) {
          responseText += formatSources(data.sources);
        }
      } else {
        // Normal chat endpoint'ini kullan
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
        responseText = data.response;
        responseEn = data.response_en;  // Normal chat de response_en döner
        isEmergency = data.is_emergency;
      }

      // Streaming ile mesajı göster (content_en ile - drift önleme)
      await streamMessage(responseText, isEmergency, responseEn);

    } catch (error) {
      console.error('Chat error:', error);
      await streamMessage('❌ Bir hata oluştu. Lütfen tekrar deneyin.');
    } finally {
      setIsLoading(false);
    }
  };

  // Mesaj gönder
  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading || isStreaming) return;

    setInput('');
    addMessage({ role: 'user', content: text });
    scrollToBottom(true); // Kullanıcı mesajında her zaman scroll
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
                💬 Serbest yazım modu {useRag && '• 📚 RAG'}
              </p>
            ) : region && symptom ? (
              <p className="text-primary-100 text-sm">
                📍 {region.name_tr} • {symptom.icon} {symptom.name_tr} {useRag && '• 📚 RAG'}
              </p>
            ) : (
              <p className="text-primary-100 text-sm">
                {useRag ? '📚 RAG Modu (Bilgi Tabanı)' : '🤖 Normal Mod'}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* RAG Toggle */}
            <button
              onClick={() => setUseRag(!useRag)}
              className={`px-3 py-2 rounded-lg text-sm transition flex items-center gap-1 ${
                useRag
                  ? 'bg-emerald-500/30 hover:bg-emerald-500/40 border border-emerald-400/50'
                  : 'bg-white/20 hover:bg-white/30'
              }`}
              title={useRag ? "RAG Kapalı: Normal mod kullan" : "RAG Açık: Bilgi tabanı kullan"}
            >
              {useRag ? '📚' : '🤖'}
              <span className="hidden sm:inline">{useRag ? 'RAG' : 'Normal'}</span>
            </button>
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
      <div 
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-4"
      >
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
              {message.role === 'assistant' && !message.isEmergency && !isStreaming && message.content.length > 0 && (
                <div className="mt-3 pt-2 border-t border-slate-200 text-xs text-slate-500">
                  ⚠️ Bu bilgiler eğitim amaçlıdır, tıbbi tavsiye değildir.
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator - sadece API beklerken, streaming sırasında değil */}
        {isLoading && !isStreaming && (
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
            placeholder={isStreaming ? "Yanıt yazılıyor..." : "Sorunuzu yazın..."}
            rows={1}
            disabled={isStreaming}
            className="flex-1 px-4 py-3 border border-slate-200 rounded-xl resize-none
                       focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                       disabled:bg-slate-100 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading || isStreaming}
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
