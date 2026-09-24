import React, { useEffect, useState } from 'react';
import { fetchCases } from '../api';
import type { CaseSummary } from '../api';
import { BarChart3, TrendingUp, PieChart, Calendar } from 'lucide-react';

export default function Analytics() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCases().then(data => {
      setCases(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  // Compute real stats from case data
  const statusCounts: Record<string, number> = {};
  const relationCounts: Record<string, number> = {};
  const organCounts: Record<string, number> = {};
  const monthlyTrend: Record<string, number> = {};

  cases.forEach(c => {
    const status = c.status.replace(/_/g, ' ');
    statusCounts[status] = (statusCounts[status] || 0) + 1;

    const rel = c.relation_type.replace(/_/g, ' ');
    relationCounts[rel] = (relationCounts[rel] || 0) + 1;

    organCounts[c.organ_type] = (organCounts[c.organ_type] || 0) + 1;

    const month = new Date(c.created_at).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
    monthlyTrend[month] = (monthlyTrend[month] || 0) + 1;
  });

  const statusColors: Record<string, string> = {
    'AUTO APPROVE': 'bg-emerald-500',
    'COMMITTEE REVIEW': 'bg-amber-500',
    'REJECTED': 'bg-rose-500',
    'UNDER REVIEW': 'bg-blue-500',
    'PENDING': 'bg-slate-400',
    'NEEDS INFO': 'bg-purple-500',
  };

  const maxStatusCount = Math.max(...Object.values(statusCounts), 1);
  const maxRelCount = Math.max(...Object.values(relationCounts), 1);
  const maxOrganCount = Math.max(...Object.values(organCounts), 1);

  const complianceRate = cases.length > 0
    ? Math.round(((statusCounts['AUTO APPROVE'] || 0) / cases.length) * 100)
    : 0;

  const flaggedRate = cases.length > 0
    ? Math.round(((statusCounts['COMMITTEE REVIEW'] || 0) + (statusCounts['REJECTED'] || 0)) / cases.length * 100)
    : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500 font-medium">Total Cases</p>
              <p className="text-3xl font-bold text-slate-900 mt-1">{cases.length}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-lg">
              <BarChart3 className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500 font-medium">Auto-Approved</p>
              <p className="text-3xl font-bold text-emerald-600 mt-1">{complianceRate}%</p>
            </div>
            <div className="p-3 bg-emerald-100 rounded-lg">
              <TrendingUp className="h-6 w-6 text-emerald-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500 font-medium">Flagged / Rejected</p>
              <p className="text-3xl font-bold text-rose-600 mt-1">{flaggedRate}%</p>
            </div>
            <div className="p-3 bg-rose-100 rounded-lg">
              <PieChart className="h-6 w-6 text-rose-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500 font-medium">Relation Types</p>
              <p className="text-3xl font-bold text-slate-900 mt-1">{Object.keys(relationCounts).length}</p>
            </div>
            <div className="p-3 bg-indigo-100 rounded-lg">
              <Calendar className="h-6 w-6 text-indigo-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Distribution */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-semibold text-slate-900 mb-4 uppercase tracking-wider">Case Status Distribution</h3>
          <div className="space-y-3">
            {Object.entries(statusCounts).map(([status, count]) => (
              <div key={status}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600 font-medium">{status}</span>
                  <span className="text-slate-900 font-bold">{count}</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5">
                  <div
                    className={`h-2.5 rounded-full transition-all ${statusColors[status] || 'bg-slate-400'}`}
                    style={{ width: `${(count / maxStatusCount) * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
            {Object.keys(statusCounts).length === 0 && (
              <p className="text-sm text-slate-400 text-center py-4">No data yet</p>
            )}
          </div>
        </div>

        {/* Relation Type Breakdown */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-semibold text-slate-900 mb-4 uppercase tracking-wider">Relation Type Breakdown</h3>
          <div className="space-y-3">
            {Object.entries(relationCounts).map(([rel, count]) => (
              <div key={rel}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600 font-medium">{rel}</span>
                  <span className="text-slate-900 font-bold">{count}</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5">
                  <div
                    className="h-2.5 rounded-full bg-indigo-500 transition-all"
                    style={{ width: `${(count / maxRelCount) * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Organ Types */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-semibold text-slate-900 mb-4 uppercase tracking-wider">Organ Type Distribution</h3>
          <div className="space-y-3">
            {Object.entries(organCounts).map(([organ, count]) => (
              <div key={organ}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600 font-medium">{organ}</span>
                  <span className="text-slate-900 font-bold">{count}</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5">
                  <div
                    className="h-2.5 rounded-full bg-teal-500 transition-all"
                    style={{ width: `${(count / maxOrganCount) * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Monthly Trend */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-sm font-semibold text-slate-900 mb-4 uppercase tracking-wider">Monthly Case Intake</h3>
          <div className="space-y-3">
            {Object.entries(monthlyTrend).map(([month, count]) => (
              <div key={month}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-600 font-medium">{month}</span>
                  <span className="text-slate-900 font-bold">{count} case{count !== 1 ? 's' : ''}</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5">
                  <div
                    className="h-2.5 rounded-full bg-blue-500 transition-all"
                    style={{ width: `${(count / Math.max(...Object.values(monthlyTrend), 1)) * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
