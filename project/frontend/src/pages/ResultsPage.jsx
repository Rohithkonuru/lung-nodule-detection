import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { Card, Badge, Alert, LoadingSkeleton, Spinner } from '../components/common/UI';
import AnimatedButton from '../components/AnimatedButton';
import Loader from '../components/Loader';
import { analysisAPI, scanAPI } from '../api/client';
import { RefreshCw, ScanLine } from 'lucide-react';
import toast from 'react-hot-toast';
import { motion, AnimatePresence } from 'framer-motion';

export const ResultsPage = () => {
  const { scanId } = useParams();
  const navigate = useNavigate();
  const [results, setResults] = useState(null);
  const [scan, setScan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentSlice, setCurrentSlice] = useState(0);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const hasFetchedRef = useRef(false);

  const formatError = (error, fallback = 'Failed to fetch results') => {
    const msg =
      error?.formattedMessage ||
      error?.response?.data?.message ||
      error?.response?.data?.detail ||
      error?.message ||
      fallback;
    if (typeof msg === 'string') return msg;
    try {
      return JSON.stringify(msg);
    } catch (err) {
      return fallback;
    }
  };

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [scanRes, resultsRes] = await Promise.all([
          scanAPI.getScan(scanId),
          analysisAPI.getResults(scanId),
        ]);
        setScan(scanRes.data);
        setResults(resultsRes.data);

        setPreviewLoading(true);
        try {
          const previewRes = await scanAPI.getScanPreview(scanId, true);
          const blobUrl = URL.createObjectURL(previewRes.data);
          setPreviewUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return blobUrl;
          });
        } catch (previewErr) {
          console.warn('Preview rendering failed:', previewErr);
          setPreviewUrl('');
        } finally {
          setPreviewLoading(false);
        }
      } catch (error) {
        toast.error(formatError(error, 'Failed to fetch results'));
      } finally {
        setLoading(false);
      }
    };

    if (scanId && !hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchData();
    } else {
      setLoading(false);
    }
  }, [scanId]);

  const handleReanalyze = async () => {
    setReanalyzing(true);
    try {
      await analysisAPI.analyze(scanId);
      const refreshed = await analysisAPI.getResults(scanId);
      setResults(refreshed.data);

      setPreviewLoading(true);
      try {
        const previewRes = await scanAPI.getScanPreview(scanId, true);
        const blobUrl = URL.createObjectURL(previewRes.data);
        setPreviewUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return blobUrl;
        });
      } finally {
        setPreviewLoading(false);
      }

      toast.success('Re-analysis complete');
    } catch (error) {
      toast.error(formatError(error, 'Re-analysis failed'));
    } finally {
      setReanalyzing(false);
    }
  };

  const getRiskLevel = (confidence) => {
    if (confidence >= 0.8) return { level: 'High', color: 'danger' };
    if (confidence >= 0.6) return { level: 'Medium', color: 'warning' };
    return { level: 'Low', color: 'gray' };
  };

  const detections = results?.detections || [];
  const highRiskCount = detections.filter((d) => (d.confidence || 0) >= 0.8).length;

  return (
    <MainLayout>
      <motion.div
        className="page-enter space-y-6 md:space-y-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        <motion.section
          className="card rounded-3xl p-4 md:p-6 lg:p-8"
          initial={{ opacity: 0, scale: 0.985 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
        >
          <p className="text-xs uppercase tracking-[0.2em] text-gray-400 mb-3">AI Analyze</p>
          <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold text-white mb-2">Analysis Results</h1>
          <p className="text-gray-300">Scan ID: {scanId}</p>
        </motion.section>

        {loading ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Card className="p-4 md:p-6">
              <div className="animate-pulse space-y-4">
                <div className="h-6 bg-gray-700 rounded w-1/3"></div>
                <div className="h-40 bg-gray-800 rounded"></div>
                <div className="h-4 bg-gray-800 rounded w-2/3"></div>
              </div>
            </Card>
          </motion.div>
        ) : !results ? (
          <Alert
            type="error"
            title="No Results Available"
            message="The analysis results could not be loaded. Please upload and analyze a new scan."
          />
        ) : (
          <motion.div className="grid grid-cols-1 xl:grid-cols-3 gap-4 md:gap-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <motion.div className="xl:col-span-2 space-y-4 md:space-y-6" initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.08 }}>
              <Card>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-bold text-white">CT Visual Review</h2>
                  <span className="text-xs rounded-full px-3 py-1 bg-gray-800 text-gray-100 border border-gray-700">
                    Live Overlay
                  </span>
                </div>

                <div className="bg-gray-900/90 rounded-2xl h-96 flex items-center justify-center mb-4 overflow-hidden border border-gray-700 relative">
                  {previewLoading ? (
                    <Loader label="Rendering CT slice..." />
                  ) : previewUrl ? (
                    <img
                      src={previewUrl}
                      alt={`CT scan preview ${scanId}`}
                      className="w-full max-w-[500px] rounded-xl max-h-full object-contain"
                    />
                  ) : (
                    <div className="text-center text-slate-300">
                      <ScanLine size={34} className="mx-auto mb-2 text-slate-200" />
                      <p className="text-lg">Preview unavailable</p>
                      <p className="text-sm mt-2">This scan format does not support inline preview yet.</p>
                    </div>
                  )}
                </div>

                {scan?.num_slices && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm text-gray-300">
                      <span>Slice Navigation</span>
                      <span>
                        Slice {currentSlice + 1} / {scan.num_slices}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max={scan.num_slices - 1 || 0}
                      value={currentSlice}
                      onChange={(e) => setCurrentSlice(parseInt(e.target.value, 10))}
                      className="w-full accent-gray-200"
                    />
                  </div>
                )}
              </Card>

              {detections.length > 0 ? (
                <Card>
                  <h2 className="text-xl font-bold text-white mb-4">Detected Nodules</h2>
                  <div className="space-y-3">
                    <AnimatePresence>
                      {detections.map((det, idx) => (
                        <motion.div
                          key={idx}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -8 }}
                          transition={{ delay: idx * 0.04 }}
                          className="p-4 rounded-xl bg-gray-900/85 border border-gray-700"
                        >
                        <div className="flex justify-between items-start mb-2">
                          <span className="font-semibold text-white">Nodule {idx + 1}</span>
                          <Badge variant={getRiskLevel(det.confidence).color} size="sm">
                            {getRiskLevel(det.confidence).level} Risk
                          </Badge>
                        </div>
                        <div className="text-sm text-slate-300 space-y-1">
                          <p>Size: {(det.size_mm || 0).toFixed(2)} mm</p>
                          <p>Confidence: {((det.confidence || 0) * 100).toFixed(1)}%</p>
                          <p>
                            Location: ({det.center?.[2] ?? 0}, {det.center?.[1] ?? 0}, {det.center?.[0] ?? 0})
                          </p>
                        </div>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                </Card>
              ) : (
                <Card>
                  <div className="flex flex-col items-center py-10 text-gray-400">
                    <div className="text-4xl mb-2">🫁</div>
                    <p>No nodules detected</p>
                  </div>
                </Card>
              )}
            </motion.div>

            <motion.div className="space-y-4 md:space-y-6" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.12 }}>
              <Card>
                <h3 className="font-bold text-white mb-4">Summary</h3>
                <div className="space-y-4">
                  <div>
                    <p className="text-gray-400 text-sm">Total Nodules</p>
                    <p className="text-4xl font-semibold text-white">{results?.total_detections || 0}</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-sm">Analysis Confidence</p>
                    <p className="text-2xl font-semibold text-gray-100">
                      {((results?.avg_confidence || 0) * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-sm">Processing Time</p>
                    <p className="text-lg font-semibold text-gray-100">
                      {results?.processing_time ? `${results.processing_time} sec` : 'N/A'}
                    </p>
                  </div>
                </div>
              </Card>

              {highRiskCount > 0 && (
                <Alert
                  type="warning"
                  title="High Risk Nodules"
                  message={`${highRiskCount} high-confidence nodule(s) detected. Clinical review recommended.`}
                />
              )}

              <Card className="space-y-3">
                <AnimatedButton className="w-full" onClick={() => navigate(`/reports/${scanId}`)}>
                  View Clinical Report
                </AnimatedButton>
                <AnimatedButton
                  variant="ghost"
                  className="w-full"
                  onClick={handleReanalyze}
                  disabled={reanalyzing}
                >
                  {reanalyzing ? (
                    <>
                      <Spinner size="sm" />
                      Re-analyzing...
                    </>
                  ) : (
                    <>
                      <RefreshCw size={18} />
                      Re-analyze
                    </>
                  )}
                </AnimatedButton>
              </Card>

              <Card className="text-center">
                <div className="text-3xl mb-2">✓</div>
                <p className="text-slate-200">Analysis Complete</p>
                <p className="text-xs text-slate-400 mt-2">Results are ready for report generation.</p>
              </Card>

              <LoadingSkeleton className="h-14" />
            </motion.div>
          </motion.div>
        )}
      </motion.div>
    </MainLayout>
  );
};
