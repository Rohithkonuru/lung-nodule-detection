import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { Card, Alert, ProgressBar } from '../components/common/UI';
import AnimatedButton from '../components/AnimatedButton';
import Loader from '../components/Loader';
import { scanAPI } from '../api/client';
import { Upload, FileText, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { motion, AnimatePresence } from 'framer-motion';

export const UploadScanPage = () => {
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [analyzing, setAnalyzing] = useState(false);
  const [scanId, setScanId] = useState(null);
  const navigate = useNavigate();

  const supportedFormats = ['.nii', '.nii.gz', '.mhd', '.jpg', '.png', '.dcm'];

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (nextFile) => {
    const fileName = nextFile.name.toLowerCase();
    const isSupported = supportedFormats.some((fmt) => fileName.endsWith(fmt));

    if (!isSupported) {
      toast.error(`Unsupported file format. Supported: ${supportedFormats.join(', ')}`);
      return;
    }

    if (nextFile.size > 500 * 1024 * 1024) {
      toast.error('File size exceeds 500MB limit');
      return;
    }

    setFile(nextFile);
    toast.success('File selected. Ready to upload.');
  };

  const formatError = (error) => {
    const msg =
      error?.formattedMessage ||
      error?.response?.data?.message ||
      error?.response?.data?.detail ||
      error?.message ||
      'Upload failed: Unknown error';

    if (typeof msg === 'string') return msg;
    try {
      return JSON.stringify(msg);
    } catch (err) {
      return 'Upload failed: Unknown error';
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setProgress(0);

    try {
      const progressInterval = setInterval(() => {
        setProgress((prev) => Math.min(prev + Math.random() * 28, 92));
      }, 450);

      const response = await scanAPI.uploadScan(formData);
      clearInterval(progressInterval);
      setProgress(100);

      if (!response.data || !response.data.id) {
        throw new Error('Invalid response: No scan ID received');
      }

      const uploadedScanId = response.data.id;
      setScanId(uploadedScanId);
      toast.success('Scan uploaded successfully. Starting AI analysis...');

      setAnalyzing(true);
      try {
        const analysis = await scanAPI.analyzeScan(uploadedScanId);
        console.log('Analysis complete:', analysis.data);
        toast.success('Analysis complete. Opening results.');
      } catch (analysisErr) {
        const analysisMsg = formatError(analysisErr);
        console.error('Analysis after upload failed:', analysisMsg, analysisErr);
        if (analysisMsg.toLowerCase().includes('invalid ct scan')) {
          toast.error(`${analysisMsg} Try a grayscale CT slice or .mhd/.nii scan.`);
        } else {
          toast.error(analysisMsg);
        }
        return;
      } finally {
        setAnalyzing(false);
      }

      navigate(`/results/${uploadedScanId}`);
    } catch (error) {
      toast.error(formatError(error));
    } finally {
      setUploading(false);
    }
  };

  const clearSelection = () => {
    setFile(null);
    setScanId(null);
    setProgress(0);
  };

  return (
    <MainLayout>
      <motion.div
        className="page-enter max-w-4xl mx-auto space-y-7"
        initial={{ opacity: 0, y: 22 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: 'easeOut' }}
      >
        <motion.section
          className="card rounded-3xl p-7 md:p-10"
          initial={{ opacity: 0, scale: 0.985 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3, delay: 0.05 }}
        >
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-gray-400 mb-3">AI Workflow</p>
            <h1 className="text-3xl md:text-4xl font-bold text-white mb-3">Upload CT Scan</h1>
            <p className="text-gray-300 max-w-2xl">
              Drop a lung CT image or volume and run instant AI-assisted nodule detection with clinical report generation.
            </p>
          </div>
        </motion.section>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.12 }}>
          <Alert
            type="info"
            title="Supported Formats"
            message="NIfTI (.nii, .nii.gz), MHD (.mhd), DICOM (.dcm), and common images (.jpg, .png). Max file size: 500MB."
          />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <Card className="space-y-6">
            <motion.div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            whileHover={{ scale: 1.01 }}
            className={`rounded-2xl p-10 text-center border-2 border-dashed transition-all duration-300 ${
              dragActive
                ? 'border-gray-500 bg-gray-800/80 shadow-md'
                : 'border-gray-700 bg-gray-900/85'
            }`}
          >
            <Upload size={50} className="mx-auto mb-4 text-gray-200" />
            <h3 className="text-xl font-semibold text-white mb-2">Drag and drop your scan</h3>
            <p className="text-gray-300 mb-6">or click to choose a file</p>
            <label htmlFor="file-input" className="inline-block cursor-pointer">
              <AnimatedButton as="span">Select File</AnimatedButton>
            </label>
            <input
              id="file-input"
              type="file"
              onChange={handleFileChange}
              accept={supportedFormats.join(',')}
              className="hidden"
            />
            </motion.div>

            <AnimatePresence>
              {file && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.25 }}
                  className="card rounded-2xl p-4 border border-gray-700"
                >
              <div className="flex items-center gap-3 mb-3">
                <FileText size={24} className="text-gray-300" />
                <div className="min-w-0">
                  <p className="font-semibold text-white truncate">{file.name}</p>
                  <p className="text-sm text-gray-300">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              </div>

              {uploading && (
                <div className="mt-4">
                  <div className="flex justify-between text-sm text-gray-300 mb-2">
                    <span>Uploading...</span>
                    <span>{Math.round(progress)}%</span>
                  </div>
                  <ProgressBar progress={progress} />
                </div>
              )}

              {scanId && (
                <div className="mt-4 p-3 rounded-xl bg-emerald-500/12 border border-emerald-400/35 text-emerald-100 text-sm">
                  Upload complete. Scan ID: {scanId}
                </div>
              )}

              <div className="flex flex-col sm:flex-row gap-3 mt-5">
                <AnimatedButton
                  onClick={handleUpload}
                  disabled={uploading || analyzing || scanId}
                  className="flex-1"
                >
                  <Sparkles size={18} />
                  {uploading ? 'Uploading...' : 'Upload And Analyze'}
                </AnimatedButton>
                <AnimatedButton
                  onClick={clearSelection}
                  disabled={uploading || analyzing}
                  variant="ghost"
                  className="flex-1"
                >
                  Clear Selection
                </AnimatedButton>
              </div>

                  <AnimatePresence>
                    {analyzing && (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.2 }}
                        className="mt-8 rounded-2xl border border-gray-700 bg-gray-900/85 p-6"
                      >
                        <Loader />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card className="rounded-2xl">
          <h3 className="font-semibold text-white mb-3">Tips For Best Results</h3>
          <ul className="space-y-2 text-sm text-gray-300">
            <li>• Use full or partial lung CT studies for clinically meaningful output.</li>
            <li>• Grayscale slices and volumetric files produce the most reliable detection confidence.</li>
            <li>• Processing time scales with image size and model queue load.</li>
            <li>• Natural photos are blocked by the domain guard to prevent false analyses.</li>
          </ul>
          </Card>
        </motion.div>
      </motion.div>
    </MainLayout>
  );
};
