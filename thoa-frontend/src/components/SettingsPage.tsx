import React from 'react';
import { Shield, Database, Eye, Lock, Server, FileCheck } from 'lucide-react';

export default function SettingsPage() {
  const systemConfig = [
    { label: 'Database', value: 'SQLite (SQLAlchemy 2.0)', icon: Database, status: 'active' },
    { label: 'PII Encryption', value: 'AES-256-GCM (Application Layer)', icon: Lock, status: 'active' },
    { label: 'OCR Engine', value: 'Tesseract 5.x + PIL Preprocessing', icon: Eye, status: 'active' },
    { label: 'Rule Engine', value: '18 THOA Rules (JSON-driven)', icon: FileCheck, status: 'active' },
    { label: 'API Framework', value: 'FastAPI + Uvicorn', icon: Server, status: 'active' },
    { label: 'Audit Trail', value: 'Append-only, Immutable', icon: Shield, status: 'active' },
  ];

  const thoaRuleCategories = [
    { category: 'Identity Verification', rules: ['ID-01: Donor Min Age', 'ID-03: Identity Proof', 'ID-04: Foreign National NOC', 'ID-05: Domicile Verification'], color: 'blue' },
    { category: 'Relationship Classification', rules: ['REL-01: Near Relative Check', 'REL-02: Near Relative Docs', 'REL-03: Genetic Certification', 'REL-04: Non-Relative Committee', 'REL-05: Non-Relative Consent', 'REL-06: Foreign National Committee'], color: 'indigo' },
    { category: 'Special Cases', rules: ['SPEC-03: Minor Recipient Guardian', 'SPEC-04: Medical Fitness (Form 4)'], color: 'purple' },
    { category: 'Commercialisation Safeguards', rules: ['COM-01: Financial Affidavit', 'COM-02: Police Verification', 'COM-03: Income Disparity Detection', 'COM-05: Section 18 Unauthorised Removal'], color: 'rose' },
  ];

  const complianceFramework = [
    { name: 'THOA 1994', status: 'Implemented', sections: 'Sections 3, 9(3), 18, 19' },
    { name: 'THOTA 2014 Rules', status: 'Implemented', sections: 'Rules 3, 19, 20' },
    { name: 'DPDP Act 2023', status: 'Compliant', sections: 'Data minimisation, PII encryption' },
    { name: 'WHO Guiding Principles', status: 'Advisory', sections: 'Informed consent, non-commercialisation' },
  ];

  return (
    <div className="space-y-6">
      {/* System Configuration */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">System Configuration</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {systemConfig.map((item) => (
            <div key={item.label} className="flex items-start p-4 bg-slate-50 rounded-lg border border-slate-100">
              <div className="p-2 bg-white rounded-lg shadow-sm mr-3">
                <item.icon className="h-5 w-5 text-slate-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900">{item.label}</p>
                <p className="text-xs text-slate-500 mt-0.5 truncate">{item.value}</p>
              </div>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                Active
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* THOA Rule Engine */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">THOA Rule Engine — 18 Automated Rules</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {thoaRuleCategories.map((cat) => (
            <div key={cat.category} className="p-4 bg-slate-50 rounded-lg border border-slate-100">
              <h4 className={`text-sm font-bold text-${cat.color}-700 mb-2`}>{cat.category}</h4>
              <ul className="space-y-1">
                {cat.rules.map((rule) => (
                  <li key={rule} className="text-xs text-slate-600 flex items-center">
                    <span className={`w-1.5 h-1.5 rounded-full bg-${cat.color}-400 mr-2 flex-shrink-0`}></span>
                    {rule}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Compliance Framework */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Compliance Framework</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Framework</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Sections Covered</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {complianceFramework.map((fw) => (
                <tr key={fw.name} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm font-medium text-slate-900">{fw.name}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      fw.status === 'Implemented' ? 'bg-emerald-100 text-emerald-800' :
                      fw.status === 'Compliant' ? 'bg-blue-100 text-blue-800' :
                      'bg-amber-100 text-amber-800'
                    }`}>{fw.status}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-500">{fw.sections}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Team Info */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Project Team</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex items-center p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-bold mr-3">MR</div>
            <div>
              <p className="text-sm font-medium text-slate-900">Manan Rastogi</p>
              <p className="text-xs text-slate-500">24BML0004 • Backend, Rule Engine, OCR</p>
            </div>
          </div>
          <div className="flex items-center p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="h-10 w-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold mr-3">AS</div>
            <div>
              <p className="text-sm font-medium text-slate-900">Avish Sharma</p>
              <p className="text-xs text-slate-500">24BML0025 • Frontend, Testing, Deployment</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
