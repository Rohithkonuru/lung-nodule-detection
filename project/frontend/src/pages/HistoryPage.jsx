import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { Card, Button, Badge } from '../components/common/UI';
import { scanAPI } from '../api/client';
import { Eye, Download, Trash2, Calendar } from 'lucide-react';
import toast from 'react-hot-toast';

export const HistoryPage = ({ view = 'history' }) => {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const viewConfig = {
    history: {
      title: 'Scan History',
      subtitle: 'All your uploaded and analyzed CT scans',
      empty: 'No scans yet',
      action: 'Upload Your First Scan',
      totalLabel: 'Total Scans',
    },
    results: {
      title: 'Results',
      subtitle: 'Scans with completed AI analysis',
      empty: 'No analysis results yet',
      action: 'Upload And Analyze',
      totalLabel: 'Total Results',
    },
    reports: {
      title: 'Reports',
      subtitle: 'Scans with generated clinical reports',
      empty: 'No reports available yet',
      action: 'Generate First Report',
      totalLabel: 'Total Reports',
    },
  };

  const currentView = viewConfig[view] || viewConfig.history;

  const filteredScans = scans.filter((scan) => {
    if (view === 'results') {
      return scan.status === 'completed';
    }
    if (view === 'reports') {
      return Boolean(scan.has_report);
    }
    return true;
  });

  useEffect(() => {
    const fetchScans = async () => {
      try {
        const response = await scanAPI.listScans();
        setScans(response.data);
      } catch (error) {
        const errorMsg = error?.formattedMessage || 
                        error?.response?.data?.message || 
                        'Failed to load scan history';
        toast.error(errorMsg);
        console.error(error);
      } finally {
        setLoading(false);
      }
    };

    fetchScans();
  }, []);

  const handleDelete = async (scanId) => {
    if (!window.confirm('Are you sure you want to delete this scan?')) return;

    try {
      await scanAPI.deleteScan(scanId);
      setScans((prev) => prev.filter((s) => s.id !== scanId));
      toast.success('Scan deleted');
    } catch (error) {
      const errorMsg = error?.formattedMessage || 
                      error?.response?.data?.message || 
                      'Failed to delete scan';
      toast.error(errorMsg);
    }
  };

  const getStatusBadge = (status) => {
    const statuses = {
      completed: { label: 'Completed', color: 'success' },
      processing: { label: 'Processing', color: 'warning' },
      failed: { label: 'Failed', color: 'danger' },
    };
    return statuses[status] || { label: 'Unknown', color: 'gray' };
  };

  return (
    <MainLayout>
      <div className="page-enter">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">{currentView.title}</h1>
          <p className="text-gray-300">{currentView.subtitle}</p>
        </div>

        {/* Scans Table */}
        {loading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-700 rounded w-1/3"></div>
            <div className="h-40 bg-gray-800 rounded"></div>
            <div className="h-40 bg-gray-800 rounded"></div>
          </div>
        ) : filteredScans.length > 0 ? (
          <Card className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-700 bg-gray-900/80">
                  <th className="px-6 py-3 text-left text-sm font-semibold text-slate-200">
                    Scan ID
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-slate-200">
                    Upload Date
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-slate-200">
                    File Name
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-slate-200">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-slate-200">
                    Nodules
                  </th>
                  <th className="px-6 py-3 text-left text-sm font-semibold text-slate-200">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredScans.map((scan) => {
                  const statusInfo = getStatusBadge(scan.status);
                  return (
                    <tr
                      key={scan.id}
                      className="border-b border-gray-700 hover:bg-gray-800/80 transition-colors"
                    >
                      <td className="px-6 py-4 text-sm font-mono text-slate-300">
                        {String(scan.id)}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-300 flex items-center gap-2">
                        <Calendar size={16} className="text-slate-400" />
                        {scan.upload_date ? new Date(scan.upload_date).toLocaleString() : 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-300">
                        {scan.file_name}
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={statusInfo.color} size="sm">
                          {statusInfo.label}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-sm font-semibold text-slate-100">
                        {scan.nodule_count || 0}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex gap-2">
                          <button
                            onClick={() => navigate(`/results/${scan.id}`)}
                            className="p-2 hover:bg-gray-800 rounded-md transition-colors"
                            title="View Results"
                          >
                            <Eye size={18} className="text-gray-200" />
                          </button>
                          {scan.has_report && (
                            <button
                              onClick={() => navigate(`/reports/${scan.id}`)}
                              className="p-2 hover:bg-gray-800 rounded-md transition-colors"
                              title="Download Report"
                            >
                              <Download size={18} className="text-gray-200" />
                            </button>
                          )}
                          <button
                            onClick={() => handleDelete(scan.id)}
                            className="p-2 hover:bg-red-500/10 rounded-md transition-colors"
                            title="Delete Scan"
                          >
                            <Trash2 size={18} className="text-red-400" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        ) : (
          <Card className="text-center w-full max-w-md mx-auto p-4 md:p-6">
            <div className="flex flex-col items-center py-6 text-gray-400">
              <div className="text-4xl mb-2">🫁</div>
              <p className="text-slate-300 mb-1">{currentView.empty}</p>
            </div>
            <Button
              variant="primary"
              className="w-full md:w-auto"
              onClick={() => navigate('/upload')}
            >
              {currentView.action}
            </Button>
          </Card>
        )}

        {/* Stats */}
        {!loading && filteredScans.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-8">
            <Card>
              <p className="text-gray-400 text-sm">{currentView.totalLabel}</p>
              <p className="text-3xl font-semibold text-white mt-2">{filteredScans.length}</p>
            </Card>
            <Card>
              <p className="text-gray-400 text-sm">Completed</p>
              <p className="text-3xl font-semibold text-green-400 mt-2">
                {filteredScans.filter((s) => s.status === 'completed').length}
              </p>
            </Card>
            <Card>
              <p className="text-gray-400 text-sm">Total Nodules</p>
              <p className="text-3xl font-semibold text-red-400 mt-2">
                {filteredScans.reduce((sum, s) => sum + (s.nodule_count || 0), 0)}
              </p>
            </Card>
          </div>
        )}
      </div>
    </MainLayout>
  );
};
