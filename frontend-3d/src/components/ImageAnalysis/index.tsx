import { useState, useCallback } from 'react';
import { ImageUpload } from './ImageUpload';
import { AnalysisResult } from './AnalysisResult';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

interface AnalysisResponse {
  success: boolean;
  predictions: Prediction[];
  top_finding: string | null;
  top_finding_tr: string | null;
  has_positive_findings: boolean;
  heatmap_base64: string | null;
  overlay_base64: string | null;
  original_base64: string | null;
  model_info: ModelInfo;
  processing_time_ms: number;
  disclaimer: string;
  disclaimer_en: string;
  timestamp: string;
}

interface ImageAnalysisProps {
  onBack: () => void;
}

export function ImageAnalysis({ onBack }: ImageAnalysisProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileSelect = useCallback((file: File) => {
    setSelectedFile(file);
    setError(null);
    setResult(null);
  }, []);

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setError('Lutfen bir goruntu dosyasi secin.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('include_explanation', 'true');

      const response = await fetch(`${API_URL}/image/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Sunucu hatasi: ${response.status}`);
      }

      const data: AnalysisResponse = await response.json();
      setResult(data);
    } catch (err) {
      console.error('Analysis error:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Analiz sirasinda beklenmeyen bir hata olustu.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setResult(null);
    setError(null);
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-600 hover:text-slate-800 transition-colors mb-4"
        >
          <span>←</span>
          <span>Ana Sayfaya Don</span>
        </button>

        <div className="flex items-center gap-4">
          <div className="text-5xl">🩻</div>
          <div>
            <h2 className="text-2xl font-bold text-slate-800">
              Rontgen Goruntu Analizi
            </h2>
            <p className="text-slate-600">
              Yapay zeka destekli gogus rontgeni analizi
            </p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="bg-white rounded-2xl shadow-lg p-6">
        {!result ? (
          // Upload and Analyze view
          <div className="space-y-6">
            <ImageUpload
              onFileSelect={handleFileSelect}
              isLoading={isLoading}
              error={error}
            />

            {/* Analyze Button */}
            <div className="flex justify-center">
              <button
                onClick={handleAnalyze}
                disabled={!selectedFile || isLoading}
                className={`
                  px-8 py-4 rounded-xl font-bold text-lg transition-all
                  ${selectedFile && !isLoading
                    ? 'bg-primary-500 hover:bg-primary-600 text-white shadow-lg hover:shadow-xl'
                    : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  }
                `}
              >
                {isLoading ? (
                  <span className="flex items-center gap-3">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Analiz Ediliyor...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <span>🔬</span>
                    Analiz Et
                  </span>
                )}
              </button>
            </div>

            {/* Loading progress info */}
            {isLoading && (
              <div className="text-center text-sm text-slate-500">
                <p>Goruntu isleniyor ve analiz yapiliyor...</p>
                <p className="mt-1">Bu islem birkaç saniye surebilir.</p>
              </div>
            )}
          </div>
        ) : (
          // Results view
          <div className="space-y-6">
            <AnalysisResult
              predictions={result.predictions}
              topFinding={result.top_finding}
              topFindingTr={result.top_finding_tr}
              hasPositiveFindings={result.has_positive_findings}
              heatmapBase64={result.heatmap_base64}
              overlayBase64={result.overlay_base64}
              originalBase64={result.original_base64}
              modelInfo={result.model_info}
              processingTimeMs={result.processing_time_ms}
              disclaimer={result.disclaimer}
            />

            {/* New Analysis Button */}
            <div className="flex justify-center">
              <button
                onClick={handleReset}
                className="px-6 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-medium transition-colors"
              >
                Yeni Analiz Yap
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Supported Conditions Info */}
      <div className="mt-6 p-4 bg-slate-50 rounded-xl">
        <h3 className="font-bold text-slate-700 mb-3">Desteklenen Bulgular</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm text-slate-600">
          <div>• Atelektazi</div>
          <div>• Kardiyomegali</div>
          <div>• Konsolidasyon</div>
          <div>• Odem</div>
          <div>• Plevral Efuzyon</div>
          <div>• Amfizem</div>
          <div>• Fibrozis</div>
          <div>• Infiltrasyon</div>
          <div>• Kitle</div>
          <div>• Nodul</div>
          <div>• Pnomoni</div>
          <div>• Pnomotoraks</div>
        </div>
      </div>
    </div>
  );
}
