import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { Card, Button, LoadingSkeleton } from '../components/common/UI';
import { scanAPI } from '../api/client';
import { Activity, FileText, TrendingUp } from 'lucide-react';

export const DashboardPage = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await scanAPI.listScans();
        const scans = Array.isArray(response.data) ? response.data : [];

        const computed = {
          total_scans: scans.length,
          total_nodules: scans.reduce((sum, scan) => sum + (Number(scan.nodule_count) || 0), 0),
          total_reports: scans.filter((scan) => Boolean(scan.has_report)).length,
        };

        setStats(computed);
      } catch (error) {
        if (error?.response?.status !== 401) {
          console.error('Failed to fetch stats:', error);
        }
        setStats({ total_scans: 0, total_nodules: 0, total_reports: 0 });
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  return (
    <MainLayout>
      <div className="page-enter">
        {/* Header */}
        <div className="mb-6 md:mb-8">
          <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold text-white mb-2">Dashboard</h1>
          <p className="text-gray-300 text-sm md:text-base">Welcome to LungAI Clinical Diagnosis System</p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6 mb-6 md:mb-8">
          {loading ? (
            <>
              <LoadingSkeleton className="h-32" />
              <LoadingSkeleton className="h-32" />
              <LoadingSkeleton className="h-32" />
            </>
          ) : (
            <>
              {/* Total Scans */}
              <Card>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Total Scans</p>
                    <p className="text-4xl font-semibold text-white mt-2">
                      {stats?.total_scans || 0}
                    </p>
                  </div>
                  <Activity size={36} className="text-gray-300 opacity-100" />
                </div>
              </Card>

              {/* Total Nodules */}
              <Card>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Nodules</p>
                    <p className="text-4xl font-semibold text-red-400 mt-2">
                      {stats?.total_nodules || 0}
                    </p>
                  </div>
                  <TrendingUp size={36} className="text-red-400 opacity-100" />
                </div>
              </Card>

              {/* Reports Generated */}
              <Card>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm">Reports</p>
                    <p className="text-4xl font-semibold text-green-400 mt-2">
                      {stats?.total_reports || 0}
                    </p>
                  </div>
                  <FileText size={36} className="text-green-400 opacity-100" />
                </div>
              </Card>
            </>
          )}
        </div>

        {/* Quick Actions */}
        <div className="card p-6 md:p-8 mt-6 md:mt-8 mb-6 md:mb-8">
          <h2 className="text-xl md:text-2xl font-semibold">Ready to analyze a new scan?</h2>
          <p className="text-gray-400 mt-2 text-sm md:text-base">
            Upload a CT scan to begin AI analysis
          </p>
          <Button
            variant="primary"
            size="lg"
            className="mt-4 w-full md:w-auto"
            onClick={() => navigate('/upload')}
          >
            Upload New Scan →
          </Button>
        </div>

        {/* Recent Activity */}
        <Card>
          <h2 className="text-xl font-bold text-white mb-4">Recent Activity</h2>
          <div className="flex flex-col items-center py-10 text-gray-400">
            <div className="text-4xl mb-2">🫁</div>
            <p>No scans uploaded yet</p>
            <p className="text-sm mt-2 text-slate-400">Your uploaded scans will appear here</p>
          </div>
        </Card>
      </div>
    </MainLayout>
  );
};
