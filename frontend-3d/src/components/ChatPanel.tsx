import { useState, useRef, useEffect, useCallback } from 'react';
import { useAppStore } from '../store/useAppStore';
import { BODY_REGIONS, SYMPTOMS } from '../data/bodyData';
import { SymptomReport } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Image analysis response type
interface ImageAnalysisResponse {
  success: boolean;
  drug_name?: string;
  active_ingredients?: string[];
  dosage_form?: string;
  strength?: string;
  manufacturer?: string;
  explanation?: string;
  confidence?: string;
  warnings?: string[];
  disclaimer?: string;
  error?: string;
  processing_time_ms?: number;
}

export function ChatPanel() {
  const [input, setInput] = useState('');
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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
      isUserScrolledUp.current = scrollHeight - scrollTop - clientHeight > 100;
    }
  }, []);

  // Akıllı auto-scroll
  const scrollToBottom = useCallback((force = false) => {
    if (force || !isUserScrolledUp.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  // Yeni mesaj geldiğinde scroll
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.role === 'user') {
      scrollToBottom(true);
    }
  }, [messages.length]);

  // Streaming sırasında son mesaj içeriği değiştiğinde auto-scroll
  useEffect(() => {
    if (isStreaming) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage?.role === 'assistant') {
        // Streaming sırasında her zaman aşağı kay (kullanıcı yukarı kaydırmadıysa)
        scrollToBottom();
      }
    }
  }, [messages[messages.length - 1]?.content, isStreaming, scrollToBottom]);

  // Mesajı anında göster (streaming olmadan)
  const showMessage = useCallback((content: string, isEmergency?: boolean, contentEn?: string) => {
    addMessage({
      role: 'assistant',
      content: content,
      content_en: contentEn,
      isEmergency
    });
    scrollToBottom();
  }, [addMessage, scrollToBottom]);

  // Direkt chat modunda hoş geldin mesajı
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
      showMessage(welcomeMessage);
    }
  }, [isDirectChatMode, showMessage, messages.length]);

  // 3D model modunda ilk mesajı gönder
  useEffect(() => {
    if (!isDirectChatMode && symptomReport && messages.length === 0 && !initialMessageSent.current) {
      initialMessageSent.current = true;
      sendInitialMessage(symptomReport);
    }
  }, [symptomReport, isDirectChatMode]);

  // Başlangıç zamanı için Türkçe cümle
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

  // Tetikleyici için Türkçe cümle
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

  // Kırmızı bayraklar için Türkçe cümle
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

    await sendToAPI(userMessage, report);
  };

  // RAG kaynaklarını formatla
  const formatSources = (sources: Array<{title: string, source: string, category: string, relevance_score: number}>) => {
    if (!sources || sources.length === 0) return '';

    const sourceLines = sources
      .filter(s => s.relevance_score > 0.3)
      .slice(0, 3)
      .map(s => `• ${s.title} (${s.source})`)
      .join('\n');

    if (!sourceLines) return '';
    return `\n\n📚 **Kaynaklar:**\n${sourceLines}`;
  };

  // SSE Streaming ile API'ye gönder
  const sendToAPIWithStreaming = async (userMessage: string) => {
    setIsLoading(true);
    // isStreaming'i henüz true yapmıyoruz - loading animasyonu gösterilecek
    let streamingStarted = false;

    try {
      const history = messages.slice(-10).map(m => ({
        role: m.role,
        content: m.content,
        content_en: m.content_en
      }));

      const ragBody = {
        message: userMessage,
        history,
        use_rag: true,
        max_sources: 5
      };

      const response = await fetch(`${API_URL}/rag/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(ragBody)
      });

      if (!response.ok) {
        throw new Error('Streaming API hatası');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Stream reader yok');
      }

      let fullContent = '';
      let sources: any[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'chunk') {
                // İlk chunk geldiğinde streaming moduna geç
                if (!streamingStarted) {
                  streamingStarted = true;
                  setIsStreaming(true);
                  // Streaming başladığında scroll durumunu sıfırla - aşağı kaymayı garantile
                  isUserScrolledUp.current = false;
                  // Boş assistant mesajı ekle (streaming için)
                  addMessage({
                    role: 'assistant',
                    content: '',
                    isEmergency: false
                  });
                }
                fullContent = data.content;
                updateLastMessage(fullContent);
                scrollToBottom();
              } else if (data.type === 'done') {
                sources = data.sources || [];
                // Not: data.response_en gelecekte content_en güncellemesi için kullanılabilir

                // Kaynakları ekle
                if (data.rag_used && sources.length > 0) {
                  const sourcesText = formatSources(sources);
                  fullContent += sourcesText;
                  updateLastMessage(fullContent);
                }

                // content_en güncelle (store'a kaydet)
                // Not: updateLastMessage sadece content güncelliyor
                // content_en için ayrı bir store action gerekebilir
              } else if (data.type === 'error') {
                updateLastMessage(`❌ Hata: ${data.message}`);
              }
            } catch (e) {
              // JSON parse hatası - atla
            }
          }
        }
      }

    } catch (error) {
      console.error('Streaming error:', error);
      // Eğer streaming başlamadıysa (boş mesaj henüz eklenmemişse), yeni mesaj ekle
      // Streaming başladıysa, mevcut boş mesajı güncelle
      if (streamingStarted) {
        updateLastMessage('❌ Bir hata oluştu. Lütfen tekrar deneyin.');
      } else {
        showMessage('❌ Bir hata oluştu. Lütfen tekrar deneyin.');
      }
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
      // Streaming bitince son halini göster - force ile scroll
      scrollToBottom(true);
    }
  };

  // Normal (non-streaming) API çağrısı
  const sendToAPINormal = async (userMessage: string, report?: SymptomReport) => {
    setIsLoading(true);

    try {
      const history = messages.slice(-10).map(m => ({
        role: m.role,
        content: m.content,
        content_en: m.content_en
      }));

      let responseText = '';
      let responseEn: string | undefined = undefined;
      let isEmergency = false;

      if (useRag) {
        const ragBody = {
          message: userMessage,
          history,
          use_rag: true,
          max_sources: 5
        };

        const response = await fetch(`${API_URL}/rag/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(ragBody)
        });

        if (!response.ok) throw new Error('RAG API hatası');

        const data = await response.json();
        responseText = data.response;
        responseEn = data.response_en;

        if (data.rag_used && data.sources?.length > 0) {
          responseText += formatSources(data.sources);
        }
      } else {
        const body: any = { message: userMessage, history };

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
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });

        if (!response.ok) throw new Error('API hatası');

        const data = await response.json();
        responseText = data.response;
        responseEn = data.response_en;
        isEmergency = data.is_emergency;
      }

      showMessage(responseText, isEmergency, responseEn);

    } catch (error) {
      console.error('Chat error:', error);
      showMessage('❌ Bir hata oluştu. Lütfen tekrar deneyin.');
    } finally {
      setIsLoading(false);
    }
  };

  // API'ye gönder - RAG modunda streaming, normal modda standart
  const sendToAPI = async (userMessage: string, report?: SymptomReport) => {
    if (useRag) {
      await sendToAPIWithStreaming(userMessage);
    } else {
      await sendToAPINormal(userMessage, report);
    }
  };

  // Resim seçme
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      const validTypes = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp'];
      if (!validTypes.includes(file.type)) {
        alert('Lütfen geçerli bir resim dosyası seçin (JPEG, PNG, WebP)');
        return;
      }

      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        alert('Dosya boyutu 10MB\'dan küçük olmalıdır');
        return;
      }

      setSelectedImage(file);

      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  // Resmi iptal et
  const handleCancelImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Resmi analiz et
  const analyzeImage = async () => {
    if (!selectedImage || isAnalyzingImage) return;

    setIsAnalyzingImage(true);

    // Add user message with image (and optional question)
    const userQuestion = input.trim();
    const messageContent = userQuestion
      ? `📷 İlaç görseli yüklendi\n\n"${userQuestion}"`
      : `📷 İlaç görseli yüklendi: ${selectedImage.name}`;

    addMessage({
      role: 'user',
      content: messageContent,
      imageUrl: imagePreview || undefined
    });
    setInput(''); // Clear input after adding message
    scrollToBottom(true);

    try {
      // Convert to base64
      const reader = new FileReader();
      const base64Promise = new Promise<string>((resolve) => {
        reader.onloadend = () => {
          const base64 = (reader.result as string).split(',')[1];
          resolve(base64);
        };
        reader.readAsDataURL(selectedImage);
      });

      const base64Data = await base64Promise;

      // Send to API with optional user question
      const userQuestion = input.trim() || undefined;
      const response = await fetch(`${API_URL}/vision/analyze-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_base64: base64Data,
          format: selectedImage.type.split('/')[1] || 'jpeg',
          user_question: userQuestion
        })
      });

      if (!response.ok) {
        throw new Error('API hatası');
      }

      const data: ImageAnalysisResponse = await response.json();

      // Format response
      let responseText = '';

      if (data.success && data.drug_name) {
        responseText = `**📦 İlaç Tespit Edildi: ${data.drug_name}**\n\n`;

        if (data.active_ingredients && data.active_ingredients.length > 0) {
          responseText += `**Etken Madde:** ${data.active_ingredients.join(', ')}\n`;
        }

        if (data.dosage_form) {
          responseText += `**Form:** ${data.dosage_form}\n`;
        }

        if (data.strength) {
          responseText += `**Doz:** ${data.strength}\n`;
        }

        if (data.manufacturer) {
          responseText += `**Üretici:** ${data.manufacturer}\n`;
        }

        if (data.explanation) {
          responseText += `\n**Açıklama:**\n${data.explanation}\n`;
        }

        if (data.warnings && data.warnings.length > 0) {
          responseText += `\n**⚠️ Uyarılar:**\n`;
          data.warnings.forEach(w => {
            responseText += `• ${w}\n`;
          });
        }

        if (data.confidence) {
          responseText += `\n_Güven: ${data.confidence}_`;
        }
      } else {
        responseText = data.error || 'İlaç görselinden bilgi alınamadı. Lütfen daha net bir görsel deneyin.';
      }

      showMessage(responseText);

    } catch (error) {
      console.error('Image analysis error:', error);
      showMessage('❌ Görsel analizi sırasında bir hata oluştu. Lütfen tekrar deneyin.');
    } finally {
      setIsAnalyzingImage(false);
      handleCancelImage();
    }
  };

  // Mesaj gönder
  const handleSend = async () => {
    // If image is selected, analyze it instead
    if (selectedImage) {
      await analyzeImage();
      return;
    }

    const text = input.trim();
    if (!text || isLoading || isStreaming) return;

    setInput('');
    addMessage({ role: 'user', content: text });
    scrollToBottom(true);
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
    initialMessageSent.current = false;
    if (isDirectChatMode) {
      resetSymptomSelection();
      useAppStore.getState().clearMessages();
    } else {
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
                  {isStreaming && message === messages[messages.length - 1] && (
                    <span className="inline-block w-2 h-4 bg-primary-500 animate-pulse ml-1"></span>
                  )}
                </div>
              )}
              {/* Show image if present */}
              {message.imageUrl && (
                <div className="mb-2">
                  <img
                    src={message.imageUrl}
                    alt="Yüklenen ilaç görseli"
                    className="max-w-[200px] rounded-lg border border-white/20"
                  />
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

      {/* Image Preview */}
      {imagePreview && (
        <div className="px-4 py-2 border-t bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="relative">
              <img
                src={imagePreview}
                alt="Seçilen görsel"
                className="w-16 h-16 object-cover rounded-lg border border-slate-200"
              />
              <button
                onClick={handleCancelImage}
                className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full
                           flex items-center justify-center text-xs hover:bg-red-600"
              >
                ✕
              </button>
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-700">İlaç görseli seçildi</p>
              <p className="text-xs text-slate-500">Göndermek için butona tıklayın</p>
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t bg-slate-50">
        <div className="flex gap-3">
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/jpg,image/webp"
            onChange={handleImageSelect}
            className="hidden"
          />

          {/* Image upload button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || isStreaming || isAnalyzingImage}
            className="px-3 py-3 bg-slate-200 text-slate-600 rounded-xl hover:bg-slate-300
                       disabled:opacity-50 disabled:cursor-not-allowed transition"
            title="İlaç görseli yükle"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </button>

          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? "Yanıt yazılıyor..." : imagePreview ? "İlaç hakkında soru sorun (opsiyonel)..." : "Sorunuzu yazın veya ilaç görseli yükleyin..."}
            rows={1}
            disabled={isStreaming || isAnalyzingImage}
            className="flex-1 px-4 py-3 border border-slate-200 rounded-xl resize-none
                       focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                       disabled:bg-slate-100 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSend}
            disabled={(!input.trim() && !selectedImage) || isLoading || isStreaming || isAnalyzingImage}
            className="px-5 py-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700
                       disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {isAnalyzingImage ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
