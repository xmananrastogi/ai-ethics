import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, Filter, AlertCircle, CheckCircle, Clock, FileX, Plus } from 'lucide-react';
import { fetchCases } from '../api';
import type { CaseSummary } from '../api';

export default function Dashboard() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetchCases().then(data => {
      setCases(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const stats = [
    { name: 'Total Cases', value: cases.length, icon: Filter, color: 'text-blue-600', bg: 'bg-blue-100' },
    { name: 'Pending Review', value: cases.filter(c => ['PENDING', 'COMMITTEE_REVIEW', 'UNDER_REVIEW'].includes(c.status)).length, icon: Clock, color: 'text-amber-600', bg: 'bg-amber-100' },
    { name: 'Approved', value: cases.filter(c => c.status === 'AUTO_APPROVE').length, icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-100' },
    { name: 'Rejected', value: cases.filter(c => c.status === 'REJECTED').length, icon: FileX, color: 'text-rose-600', bg: 'bg-rose-100' },
  ];

  const filteredCases = cases.filter(c => 
    c.case_number.toLowerCase().includes(search.toLowerCase()) ||
    c.hospital_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.name} className="bg-white overflow-hidden rounded-xl shadow-sm border border-slate-200 p-6 transition-all hover:shadow-md">
            <div className="flex items-center">
              <div className={`flex-shrink-0 rounded-lg p-3 ${stat.bg}`}>
                <stat.icon className={`h-6 w-6 ${stat.color}`} aria-hidden="true" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-slate-500 truncate">{stat.name}</dt>
                  <dd className="text-2xl font-semibold text-slate-900">{stat.value}</dd>
                </dl>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Case Table */}
      <div className="bg-white shadow-sm rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-200 flex items-center justify-between">
          <h3 className="text-lg font-medium leading-6 text-slate-900">Active Cases</h3>
          <div className="flex items-center space-x-3">
            <div className="relative rounded-md shadow-sm">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-4 w-4 text-slate-400" />
              </div>
              <input
                type="text"
                className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-10 sm:text-sm border-slate-300 rounded-md py-2 border"
                placeholder="Search cases..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Link to="/cases/new" className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-all shadow-sm">
              <Plus className="h-4 w-4 mr-1.5" /> New Case
            </Link>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Case Number</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Relation</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Hospital</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
                <th scope="col" className="relative px-6 py-3"><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-slate-200">
              {loading ? (
                <tr><td colSpan={6} className="px-6 py-12 text-center text-sm text-slate-500">
                  <div className="flex flex-col items-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-3"></div>
                    Loading cases...
                  </div>
                </td></tr>
              ) : filteredCases.length === 0 ? (
                <tr><td colSpan={6} className="px-6 py-12 text-center">
                  <div className="flex flex-col items-center">
                    <AlertCircle className="h-10 w-10 text-slate-300 mb-3" />
                    <p className="text-sm font-medium text-slate-900">No cases found</p>
                    <p className="text-sm text-slate-500 mt-1">{search ? 'Try a different search term.' : 'Create your first case to get started.'}</p>
                    {!search && (
                      <Link to="/cases/new" className="mt-4 inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-all shadow-sm">
                        <Plus className="h-4 w-4 mr-1.5" /> New Case
                      </Link>
                    )}
                  </div>
                </td></tr>
              ) : (
                filteredCases.map((c) => {
                  const statusConfig: Record<string, { bg: string; text: string }> = {
                    'AUTO_APPROVE': { bg: 'bg-emerald-100', text: 'text-emerald-800' },
                    'COMMITTEE_REVIEW': { bg: 'bg-amber-100', text: 'text-amber-800' },
                    'REJECTED': { bg: 'bg-rose-100', text: 'text-rose-800' },
                    'UNDER_REVIEW': { bg: 'bg-blue-100', text: 'text-blue-800' },
                    'PENDING': { bg: 'bg-slate-100', text: 'text-slate-800' },
                    'NEEDS_INFO': { bg: 'bg-purple-100', text: 'text-purple-800' },
                  };
                  const sc = statusConfig[c.status] || { bg: 'bg-slate-100', text: 'text-slate-800' };
                  return (
                  <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">{c.case_number}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                        {c.relation_type.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">{c.hospital_name}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${sc.bg} ${sc.text}`}>
                        {c.status.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <Link to={`/cases/${c.id}`} className="text-blue-600 hover:text-blue-900">
                        Review &rarr;
                      </Link>
                    </td>
                  </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
