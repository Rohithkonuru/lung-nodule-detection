import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { Alert, LoadingSkeleton, Spinner } from '../components/common/UI';
import { analysisAPI, reportAPI, scanAPI } from '../api/client';
import { Download } from 'lucide-react';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';

const toFiniteNumber = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const toPercent = (value) => {
  const parsed = toFiniteNumber(value);
  return parsed <= 1 ? parsed * 100 : parsed;
};

const getDetectionScore = (detection) => {
  return toFiniteNumber(
    detection?.confidence ??
      detection?.score ??
      detection?.confidence_score ??
      detection?.probability,
    0
  );
};

const getDetectionSize = (detection) => {
  return toFiniteNumber(
    detection?.size_mm ??
      detection?.diameter_mm ??
      detection?.diameter,
    0
  );
};

const deriveRiskLevel = (apiRiskLevel, nodules, confidencePercent) => {
  if (typeof apiRiskLevel === 'string' && apiRiskLevel.trim()) {
    const normalized = apiRiskLevel.trim().toLowerCase();
    return normalized.charAt(0).toUpperCase() + normalized.slice(1);
  }

  if (nodules >= 3 || confidencePercent >= 80) return 'High';
  if (nodules >= 1 || confidencePercent >= 45) return 'Medium';
  return 'Low';
};

const parseReportText = (reportText) => {
  if (!reportText || typeof reportText !== 'string') {
    return {
      notes: 'No clinical notes available.',
      recommendations: [],
    };
  }

  const lines = reportText.split('\n').map((line) => line.trim());
  const notes = [];
  const recommendations = [];
  let inRecommendations = false;

  for (const line of lines) {
    if (!line) continue;
    if (/^={3,}$/.test(line) || /^-{3,}$/.test(line)) continue;
    if (/^clinical report$/i.test(line)) continue;

    if (/^recommendations:\s*$/i.test(line)) {
      inRecommendations = true;
      continue;
    }

    if (inRecommendations) {
      if (/^[-\u2022]\s*/.test(line)) {
        recommendations.push(line.replace(/^[-\u2022]\s*/, '').trim());
      }
      continue;
    }

    notes.push(line.replace(/^summary:\s*/i, '').trim());
  }

  return {
    notes: notes.join(' ').trim() || 'No clinical notes available.',
    recommendations,
  };
};

export const ReportPage = () => {
  const { scanId } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [scanMeta, setScanMeta] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const hasFetchedRef = useRef(false);
  const previewUrlRef = useRef('');

  const formatError = (error, fallback = 'Failed to load report') => {
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

  const isAnalyzeRequiredError = (error) => {
    const msg = formatError(error, '').toLowerCase();
    return msg.includes('analyze scan before generating report');
  };

  const generateWithAnalyzeFallback = async () => {
    try {
      const generated = await reportAPI.generateReport(scanId);
      setReport(generated.data);
      toast.success('Report generated successfully');
      return true;
    } catch (genErr) {
      if (isAnalyzeRequiredError(genErr)) {
        try {
          toast('No analysis found. Running analysis before report generation...');
          await analysisAPI.analyze(scanId);
          const generatedAfterAnalyze = await reportAPI.generateReport(scanId);
          setReport(generatedAfterAnalyze.data);
          toast.success('Analysis complete and report generated');
          return true;
        } catch (analyzeErr) {
          toast.error(formatError(analyzeErr, 'Analysis failed before report generation'));
          return false;
        }
      }

      toast.error(formatError(genErr, 'Failed to generate report'));
      return false;
    }
  };

  const loadSupplementaryData = async () => {
    const [resultsResponse, previewResponse] = await Promise.allSettled([
      analysisAPI.getResults(scanId),
      scanAPI.getScanPreview(scanId, true),
    ]);

    if (resultsResponse.status === 'fulfilled') {
      setAnalysisData(resultsResponse.value?.data || null);
    }

    if (previewResponse.status === 'fulfilled' && previewResponse.value?.data) {
      const objectUrl = window.URL.createObjectURL(previewResponse.value.data);
      if (previewUrlRef.current) {
        window.URL.revokeObjectURL(previewUrlRef.current);
      }
      previewUrlRef.current = objectUrl;
      setPreviewUrl(objectUrl);
    }
  };

  useEffect(() => {
    hasFetchedRef.current = false;
  }, [scanId]);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        window.URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = '';
      }
    };
  }, []);

  useEffect(() => {
    const fetchReport = async () => {
      setLoading(true);
      try {
        const scanResponse = await scanAPI.getScan(scanId);
        setScanMeta(scanResponse?.data || null);
        const hasReport = Boolean(scanResponse?.data?.has_report);
        let reportReady = false;

        if (hasReport) {
          try {
            const response = await reportAPI.getReport(scanId);
            setReport(response.data);
            reportReady = true;
          } catch (reportError) {
            if (reportError?.response?.status === 404) {
              reportReady = await generateWithAnalyzeFallback();
            } else {
              throw reportError;
            }
          }
        } else {
          reportReady = await generateWithAnalyzeFallback();
        }

        if (reportReady) {
          await loadSupplementaryData();
        }
      } catch (error) {
        if (error?.response?.status === 404) {
          const reportReady = await generateWithAnalyzeFallback();
          if (reportReady) {
            await loadSupplementaryData();
          }
        } else {
          toast.error(formatError(error, 'Failed to load report'));
        }
      } finally {
        setLoading(false);
      }
    };

    if (scanId && !hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchReport();
    } else {
      setLoading(false);
    }
  }, [scanId]);

  const handleDownloadReport = async () => {
    setDownloading(true);
    try {
      const response = await reportAPI.downloadReport(scanId);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `report_${scanId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
      toast.success('PDF report downloaded');
    } catch (error) {
      toast.error(formatError(error, 'Download failed'));
    } finally {
      setDownloading(false);
    }
  };

  const detections = useMemo(() => {
    return Array.isArray(analysisData?.detections) ? analysisData.detections : [];
  }, [analysisData]);

  const totalNodules = useMemo(() => {
    return toFiniteNumber(analysisData?.total_detections, toFiniteNumber(scanMeta?.nodule_count, detections.length));
  }, [analysisData, scanMeta, detections.length]);

  const confidencePercent = useMemo(() => {
    const sourceValue = analysisData?.avg_confidence ?? analysisData?.history?.[0]?.confidence_score ?? 0;
    const asPercent = toPercent(sourceValue);
    return Math.max(0, Math.min(100, asPercent));
  }, [analysisData]);

  const riskLevel = useMemo(() => {
    return deriveRiskLevel(analysisData?.risk_level, totalNodules, confidencePercent);
  }, [analysisData, totalNodules, confidencePercent]);

  const riskBadgeClassName = useMemo(() => {
    const classes = {
      low: 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/30',
      medium: 'bg-amber-500/20 text-amber-300 border border-amber-400/30',
      high: 'bg-rose-500/20 text-rose-300 border border-rose-400/30',
    };
    return classes[riskLevel.toLowerCase()] || classes.medium;
  }, [riskLevel]);

  const parsedReport = useMemo(() => parseReportText(report?.report_text), [report]);

  return (
    <MainLayout>
      <motion.div
        className="page-enter animate-fade-in max-w-6xl mx-auto space-y-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.42, ease: 'easeOut' }}
      >
        <motion.section
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-2"
          initial={{ opacity: 0, scale: 0.985 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
        >
          <div>
            <h1 className="text-3xl font-semibold text-white">Clinical Report</h1>
            <p className="text-gray-400 text-sm">Scan ID: {scanId}</p>
          </div>
          <button
            type="button"
            className="btn-apple inline-flex items-center justify-center gap-2 w-full sm:w-auto disabled:cursor-not-allowed disabled:opacity-60"
            onClick={handleDownloadReport}
            disabled={downloading || !report}
          >
            {downloading ? (
              <>
                <Spinner size="sm" />
                Downloading...
              </>
            ) : (
              <>
                <Download size={18} />
                Download PDF
              </>
            )}
          </button>
        </motion.section>

        {loading ? (
          <motion.div className="space-y-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <LoadingSkeleton className="h-28 rounded-2xl" />
              <LoadingSkeleton className="h-28 rounded-2xl" />
              <LoadingSkeleton className="h-28 rounded-2xl" />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <LoadingSkeleton className="h-80 rounded-2xl" />
              <LoadingSkeleton className="h-80 rounded-2xl" />
            </div>
            <LoadingSkeleton className="h-44 rounded-2xl" />
          </motion.div>
        ) : report ? (
          <motion.div className="space-y-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <motion.div
              className="grid grid-cols-1 md:grid-cols-3 gap-4"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="card">
                <p className="text-gray-400 text-sm mb-2">Total Nodules</p>
                <h2 className="text-3xl font-bold text-white">{totalNodules}</h2>
                <p className="text-xs text-gray-500 mt-2">
                  Report #{report.id} - {report.created_date ? new Date(report.created_date).toLocaleDateString() : 'No date'}
                </p>
              </div>

              <div className="card">
                <p className="text-gray-400 text-sm mb-2">Risk Level</p>
                <div className="flex items-center gap-2">
                  <h2 className="text-3xl font-bold text-white">{riskLevel}</h2>
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${riskBadgeClassName}`}>
                    {riskLevel} Risk
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-2">Based on current detection profile</p>
              </div>

              <div className="card">
                <p className="text-gray-400 text-sm mb-2">Confidence</p>
                <h2 className="text-3xl font-bold text-white">{confidencePercent.toFixed(1)}%</h2>
                <p className="text-xs text-gray-500 mt-2">Average model certainty</p>
              </div>
            </motion.div>

            <motion.div
              className="grid grid-cols-1 lg:grid-cols-2 gap-6"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.04 }}
            >
              <div className="card">
                <h3 className="mb-3 font-semibold text-lg">CT Scan</h3>
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt={`CT scan ${scanId}`}
                    className="rounded-xl w-full max-h-[440px] object-contain bg-gray-950/60 border border-gray-700"
                  />
                ) : (
                  <div className="rounded-xl h-72 w-full bg-gray-950/60 border border-gray-700 flex items-center justify-center text-gray-400 text-sm">
                    Scan preview unavailable
                  </div>
                )}
              </div>

              <div className="card">
                <h3 className="mb-3 font-semibold text-lg">Detected Nodules</h3>
                {detections.length > 0 ? (
                  <div className="divide-y divide-gray-700">
                    {detections.map((detection, idx) => {
                      const detectionScorePercent = toPercent(getDetectionScore(detection));
                      const sizeMm = getDetectionSize(detection);
                      return (
                        <div key={`${idx}-${detectionScorePercent}`} className="flex justify-between items-center py-3">
                          <div>
                            <p className="text-gray-100 font-medium">Nodule {idx + 1}</p>
                            <p className="text-xs text-gray-400">{sizeMm > 0 ? `${sizeMm.toFixed(1)} mm` : 'Size not reported'}</p>
                          </div>
                          <span className="text-white font-semibold">{detectionScorePercent.toFixed(2)}%</span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-gray-400 text-sm leading-relaxed">
                    No explicit nodules were returned for this scan in the latest analysis result.
                  </p>
                )}
              </div>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
              <div className="card">
                <h3 className="mb-3 font-semibold text-lg">Clinical Notes</h3>
                <p className="text-gray-300 leading-relaxed text-sm md:text-base">{parsedReport.notes}</p>

                {parsedReport.recommendations.length > 0 && (
                  <div className="mt-5">
                    <h4 className="text-sm font-semibold text-gray-100 mb-2">Recommendations</h4>
                    <ul className="space-y-2">
                      {parsedReport.recommendations.map((rec, idx) => (
                        <li key={`${idx}-${rec.slice(0, 24)}`} className="text-gray-300 text-sm flex gap-2">
                          <span className="text-gray-500">-</span>
                          <span>{rec}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </motion.div>

            <Alert
              type="info"
              title="Medical Disclaimer"
              message="This AI-generated report is for clinical decision support only and should not be considered a substitute for professional medical judgment."
            />

            <motion.div
              className="flex flex-col sm:flex-row gap-3"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.16 }}
            >
              <button type="button" className="btn-secondary w-full sm:w-auto" onClick={() => navigate('/history')}>
                View History
              </button>
              <button type="button" className="btn-primary w-full sm:w-auto" onClick={() => navigate('/upload')}>
                Upload New Scan
              </button>
            </motion.div>
          </motion.div>
        ) : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="card text-center w-full max-w-xl mx-auto">
              <div className="flex flex-col items-center py-6 text-gray-400">
                <p className="text-slate-200 mb-3 text-lg font-semibold">Report not available yet.</p>
                <p className="text-sm text-slate-400 mb-8">Please make sure the scan has been analyzed first.</p>
              </div>
              <button type="button" className="btn-secondary w-full sm:w-auto" onClick={() => navigate('/history')}>
                Go To History
              </button>
            </div>
          </motion.div>
        )}
      </motion.div>
    </MainLayout>
  );
};
