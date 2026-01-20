import { useState } from 'react';

interface Prediction {
  label: string;
  label_tr: string;
  confidence: number;
  confidence_pct: string;
  explanation: string;
  is_positive: boolean;
}

interface ModelInfo {
  name: string;
  version: string;
  dataset: string;
  device: string;
  input_size: number;
}

interface AnalysisResultProps {
  predictions: Prediction[];
  topFinding: string | null;
  topFindingTr: string | null;
  hasPositiveFindings: boolean;
  heatmapBase64: string | null;
  overlayBase64: string | null;
  originalBase64: string | null;
  modelInfo: ModelInfo;
  processingTimeMs: number;
  disclaimer: string;
}

export function AnalysisResult({
  predictions,
  topFinding,
  topFindingTr,
  hasPositiveFindings,
  heatmapBase64,
  overlayBase64,
  originalBase64,
  modelInfo,
  processingTimeMs,
  disclaimer,
}: AnalysisResultProps) {
  const [activeTab, setActiveTab] = useState<'original' | 'heatmap' | 'overlay'>('overlay');

  const getConfidenceColor = (confidence: number, isPositive: boolean) => {
    if (!isPositive) return 'bg-slate-100 text-slate-600';
    if (confidence >= 0.7) return 'bg-red-100 text-red-700';
    if (confidence >= 0.5) return 'bg-orange-100 text-orange-700';
    return 'bg-yellow-100 text-yellow-700';
  };

  const getConfidenceBarColor = (confidence: number, isPositive: boolean) => {
    if (!isPositive) return 'bg-slate-300';
    if (confidence >= 0.7) return 'bg-red-500';
    if (confidence >= 0.5) return 'bg-orange-500';
    return 'bg-yellow-500';
  };

  return (
    <div className="space-y-6">
      {/* Disclaimer - Always on top */}
      <div className="p-4 bg-amber-50 border border-amber-300 rounded-xl">
        <div className="flex items-start gap-3">
          <span className="text-2xl">⚠️</span>
          <p className="text-sm text-amber-800">{disclaimer}</p>
        </div>
      </div>

      {/* Main Result Card */}
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        {/* Header */}
        <div className={`p-4 ${hasPositiveFindings ? 'bg-orange-500' : 'bg-green-500'} text-white`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-3xl">
                {hasPositiveFindings ? '🔍' : '✅'}
              </span>
              <div>
                <h3 className="text-lg font-bold">
                  {hasPositiveFindings
                    ? `Bulgu Tespit Edildi: ${topFindingTr}`
                    : 'Belirgin Bulgu Tespit Edilmedi'}
                </h3>
                <p className="text-sm opacity-90">
                  Islem suresi: {processingTimeMs}ms
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Image Visualization */}
        {(originalBase64 || heatmapBase64 || overlayBase64) && (
          <div className="p-4 bg-slate-50 border-b">
            {/* Tab buttons */}
            <div className="flex gap-2 mb-4">
              {originalBase64 && (
                <button
                  onClick={() => setActiveTab('original')}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    activeTab === 'original'
                      ? 'bg-primary-500 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Orijinal
                </button>
              )}
              {heatmapBase64 && (
                <button
                  onClick={() => setActiveTab('heatmap')}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    activeTab === 'heatmap'
                      ? 'bg-primary-500 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Isi Haritasi
                </button>
              )}
              {overlayBase64 && (
                <button
                  onClick={() => setActiveTab('overlay')}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    activeTab === 'overlay'
                      ? 'bg-primary-500 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Birlesik Gorunum
                </button>
              )}
            </div>

            {/* Image display */}
            <div className="flex justify-center">
              <img
                src={
                  activeTab === 'original'
                    ? originalBase64!
                    : activeTab === 'heatmap'
                    ? heatmapBase64!
                    : overlayBase64!
                }
                alt={activeTab}
                className="max-h-80 rounded-lg shadow-md"
              />
            </div>

            {/* Legend */}
            {activeTab !== 'original' && (
              <div className="mt-4 flex items-center justify-center gap-4 text-xs text-slate-500">
                <div className="flex items-center gap-1">
                  <div className="w-4 h-4 bg-blue-500 rounded"></div>
                  <span>Dusuk dikkat</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-4 h-4 bg-green-500 rounded"></div>
                  <span>Orta dikkat</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-4 h-4 bg-yellow-500 rounded"></div>
                  <span>Yuksek dikkat</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-4 h-4 bg-red-500 rounded"></div>
                  <span>Cok yuksek dikkat</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Predictions List */}
        <div className="p-4">
          <h4 className="font-bold text-slate-700 mb-3">Analiz Sonuclari</h4>
          <div className="space-y-3">
            {predictions.map((pred, idx) => (
              <div
                key={pred.label}
                className={`p-3 rounded-lg border ${
                  pred.is_positive ? 'border-orange-200 bg-orange-50' : 'border-slate-200 bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-800">
                      {idx + 1}. {pred.label_tr}
                    </span>
                    {pred.is_positive && (
                      <span className="px-2 py-0.5 bg-orange-500 text-white text-xs rounded-full">
                        Bulgu
                      </span>
                    )}
                  </div>
                  <span className={`px-2 py-1 rounded-full text-sm font-medium ${getConfidenceColor(pred.confidence, pred.is_positive)}`}>
                    {pred.confidence_pct}
                  </span>
                </div>

                {/* Confidence bar */}
                <div className="h-2 bg-slate-200 rounded-full overflow-hidden mb-2">
                  <div
                    className={`h-full transition-all ${getConfidenceBarColor(pred.confidence, pred.is_positive)}`}
                    style={{ width: `${pred.confidence * 100}%` }}
                  />
                </div>

                {/* Explanation */}
                {pred.explanation && pred.is_positive && (
                  <p className="text-sm text-slate-600 mt-2">
                    {pred.explanation}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Model Info */}
        <div className="p-4 bg-slate-50 border-t">
          <details className="text-sm text-slate-500">
            <summary className="cursor-pointer hover:text-slate-700">
              Model Bilgisi
            </summary>
            <div className="mt-2 space-y-1 pl-4">
              <p>Model: {modelInfo.name} ({modelInfo.version})</p>
              <p>Egitim verisi: {modelInfo.dataset}</p>
              <p>Cihaz: {modelInfo.device}</p>
              <p>Girdi boyutu: {modelInfo.input_size}x{modelInfo.input_size}</p>
            </div>
          </details>
        </div>
      </div>

      {/* Recommendation */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl">
        <div className="flex items-start gap-3">
          <span className="text-2xl">👨‍⚕️</span>
          <div>
            <p className="font-medium text-blue-800 mb-1">Doktorunuza Danisin</p>
            <p className="text-sm text-blue-700">
              Bu analiz sadece on bilgilendirme amaclidir. Sonuclar ne olursa olsun,
              kesin tani ve tedavi icin bir saglik profesyoneline basvurunuz.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
