import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileText, CheckCircle, AlertCircle, ArrowRight, ArrowLeft, X, Plus } from 'lucide-react';
import { createCase, uploadDocument, triggerScreening } from '../api';
import type { CaseCreatePayload } from '../api';

const RELATION_TYPES = [
  { value: 'SPOUSE', label: 'Spouse' },
  { value: 'PARENT_CHILD', label: 'Parent / Child' },
  { value: 'SIBLING', label: 'Sibling' },
  { value: 'GRANDPARENT_GRANDCHILD', label: 'Grandparent / Grandchild' },
  { value: 'NON_RELATIVE', label: 'Non-Relative (Requires Auth Committee)' },
  { value: 'FOREIGN_NATIONAL', label: 'Foreign National' },
];

const ORGAN_TYPES = ['KIDNEY', 'LIVER', 'HEART', 'LUNG', 'PANCREAS', 'INTESTINE'];

const DOCUMENT_TYPES = [
  { value: 'FORM_1', label: 'Form 1 — Near-Relative Donor Consent' },
  { value: 'FORM_3', label: 'Form 3 — Non-Relative Donor Consent' },
  { value: 'FORM_4', label: 'Form 4 — Medical Fitness Certificate' },
  { value: 'FORM_11', label: 'Form 11 — Joint Application' },
  { value: 'IDENTITY_PROOF', label: 'Identity Proof (Aadhaar / Passport)' },
  { value: 'DNA_REPORT', label: 'DNA Test Report' },
  { value: 'FINANCIAL_AFFIDAVIT', label: 'Financial Affidavit (No Commercial Dealing)' },
  { value: 'POLICE_VERIFICATION', label: 'Police Verification Report' },
  { value: 'MEDICAL_REPORT', label: 'Medical Report' },
  { value: 'OTHER', label: 'Other Supporting Document' },
];

interface UploadedFile {
  file: File;
  docType: string;
  status: 'pending' | 'uploading' | 'done' | 'error';
  docId?: string;
}

export default function CreateCaseWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [error, setError] = useState('');
  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 1: Case details
  const [relationType, setRelationType] = useState('');
  const [hospitalName, setHospitalName] = useState('');
  const [organType, setOrganType] = useState('');
  const [donorName, setDonorName] = useState('');
  const [donorAge, setDonorAge] = useState('');
  const [donorGender, setDonorGender] = useState('');
  const [donorAadhaar, setDonorAadhaar] = useState('');
  const [recipientName, setRecipientName] = useState('');
  const [recipientAge, setRecipientAge] = useState('');
  const [recipientGender, setRecipientGender] = useState('');
  const [recipientAadhaar, setRecipientAadhaar] = useState('');

  // Step 2: Documents
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedDocType, setSelectedDocType] = useState(DOCUMENT_TYPES[0].value);

  // Step 3: Screening
  const [screeningStatus, setScreeningStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');

  const handleCreateCase = async () => {
    setError('');
    if (!relationType || !hospitalName || !organType || !donorName || !donorAge || !donorAadhaar || !recipientName || !recipientAge || !recipientAadhaar) {
      setError('All required fields must be filled.');
      return;
    }
    setSubmitting(true);
    try {
      const payload: CaseCreatePayload = {
        relation_type: relationType,
        hospital_name: hospitalName,
        organ_type: organType,
        donor: {
          full_name: donorName,
          age: parseInt(donorAge),
          gender: donorGender || undefined,
          aadhaar_number: donorAadhaar,
        },
        recipient: {
          full_name: recipientName,
          age: parseInt(recipientAge),
          gender: recipientGender || undefined,
          aadhaar_number: recipientAadhaar,
        },
      };
      const created = await createCase(payload);
      setCreatedCaseId(created.id);
      setStep(2);
    } catch (e: any) {
      setError(e.message || 'Failed to create case');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const newFiles = Array.from(e.target.files).map((f) => ({
      file: f,
      docType: selectedDocType,
      status: 'pending' as const,
    }));
    setFiles((prev) => [...prev, ...newFiles]);
    e.target.value = '';
  };

  const handleRemoveFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleUploadAll = async () => {
    if (!createdCaseId || files.length === 0) return;
    setSubmitting(true);
    setError('');

    const updated = [...files];
    for (let i = 0; i < updated.length; i++) {
      if (updated[i].status === 'done') continue;
      updated[i] = { ...updated[i], status: 'uploading' };
      setFiles([...updated]);
      try {
        const result = await uploadDocument(createdCaseId, updated[i].file, updated[i].docType);
        updated[i] = { ...updated[i], status: 'done', docId: result.document_id };
      } catch (e: any) {
        updated[i] = { ...updated[i], status: 'error' };
        setError(`Failed to upload ${updated[i].file.name}: ${e.message}`);
      }
      setFiles([...updated]);
    }
    setSubmitting(false);

    if (updated.every((f) => f.status === 'done')) {
      setStep(3);
    }
  };

  const handleTriggerScreening = async () => {
    if (!createdCaseId) return;
    setScreeningStatus('running');
    try {
      await triggerScreening(createdCaseId);
      setScreeningStatus('done');
      setTimeout(() => navigate(`/cases/${createdCaseId}`), 1500);
    } catch (e: any) {
      setScreeningStatus('error');
      setError(e.message || 'Screening failed');
    }
  };

  const stepLabels = ['Case Details', 'Upload Documents', 'Run Screening'];

  return (
    <div className="max-w-4xl mx-auto">
      {/* Progress Steps */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {stepLabels.map((label, idx) => {
            const stepNum = idx + 1;
            const active = step === stepNum;
            const completed = step > stepNum;
            return (
              <div key={label} className="flex-1 flex items-center">
                <div className="flex items-center">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
                    completed ? 'bg-emerald-500 text-white' : active ? 'bg-blue-600 text-white ring-4 ring-blue-100' : 'bg-slate-200 text-slate-500'
                  }`}>
                    {completed ? <CheckCircle className="h-5 w-5" /> : stepNum}
                  </div>
                  <span className={`ml-3 text-sm font-medium ${active ? 'text-blue-700' : completed ? 'text-emerald-700' : 'text-slate-400'}`}>
                    {label}
                  </span>
                </div>
                {idx < stepLabels.length - 1 && (
                  <div className={`flex-1 mx-4 h-0.5 ${step > stepNum ? 'bg-emerald-400' : 'bg-slate-200'}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-start">
          <AlertCircle className="h-5 w-5 text-rose-500 mt-0.5 mr-3 flex-shrink-0" />
          <p className="text-sm text-rose-700">{error}</p>
        </div>
      )}

      {/* Step 1: Case Details */}
      {step === 1 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
            <h3 className="text-lg font-semibold text-slate-900">New Transplant Case</h3>
            <p className="text-sm text-slate-500 mt-1">Enter the donor, recipient, and case details as per THOA requirements.</p>
          </div>

          <div className="p-6 space-y-6">
            {/* Case Info */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Relation Type <span className="text-rose-500">*</span></label>
                <select value={relationType} onChange={(e) => setRelationType(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                  <option value="">Select...</option>
                  {RELATION_TYPES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Hospital <span className="text-rose-500">*</span></label>
                <input type="text" value={hospitalName} onChange={(e) => setHospitalName(e.target.value)} placeholder="e.g. AIIMS Delhi" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Organ <span className="text-rose-500">*</span></label>
                <select value={organType} onChange={(e) => setOrganType(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                  <option value="">Select...</option>
                  {ORGAN_TYPES.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              </div>
            </div>

            {/* Donor */}
            <div>
              <h4 className="text-sm font-semibold text-slate-800 mb-3 flex items-center">
                <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs flex items-center justify-center font-bold mr-2">D</span>
                Donor Details
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Full Name <span className="text-rose-500">*</span></label>
                  <input type="text" value={donorName} onChange={(e) => setDonorName(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Age <span className="text-rose-500">*</span></label>
                    <input type="number" min="1" max="120" value={donorAge} onChange={(e) => setDonorAge(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Gender</label>
                    <select value={donorGender} onChange={(e) => setDonorGender(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                      <option value="">—</option>
                      <option value="M">Male</option>
                      <option value="F">Female</option>
                      <option value="O">Other</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Aadhaar Number <span className="text-rose-500">*</span></label>
                  <input type="text" maxLength={12} value={donorAadhaar} onChange={(e) => setDonorAadhaar(e.target.value.replace(/\D/g, ''))} placeholder="12-digit Aadhaar" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono" />
                </div>
              </div>
            </div>

            {/* Recipient */}
            <div>
              <h4 className="text-sm font-semibold text-slate-800 mb-3 flex items-center">
                <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 text-xs flex items-center justify-center font-bold mr-2">R</span>
                Recipient Details
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Full Name <span className="text-rose-500">*</span></label>
                  <input type="text" value={recipientName} onChange={(e) => setRecipientName(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Age <span className="text-rose-500">*</span></label>
                    <input type="number" min="1" max="120" value={recipientAge} onChange={(e) => setRecipientAge(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Gender</label>
                    <select value={recipientGender} onChange={(e) => setRecipientGender(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                      <option value="">—</option>
                      <option value="M">Male</option>
                      <option value="F">Female</option>
                      <option value="O">Other</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Aadhaar Number <span className="text-rose-500">*</span></label>
                  <input type="text" maxLength={12} value={recipientAadhaar} onChange={(e) => setRecipientAadhaar(e.target.value.replace(/\D/g, ''))} placeholder="12-digit Aadhaar" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono" />
                </div>
              </div>
            </div>
          </div>

          <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-end">
            <button onClick={handleCreateCase} disabled={submitting} className="inline-flex items-center px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-200 disabled:opacity-50 transition-all">
              {submitting ? 'Creating...' : 'Create Case & Continue'}
              <ArrowRight className="ml-2 h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Document Upload */}
      {step === 2 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
            <h3 className="text-lg font-semibold text-slate-900">Upload THOA Documents</h3>
            <p className="text-sm text-slate-500 mt-1">Attach the required legal forms for this transplant case. Supported: PDF, JPG, PNG (max 10MB each).</p>
          </div>

          <div className="p-6 space-y-5">
            {/* File picker row */}
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-slate-700 mb-1">Document Type</label>
                <select value={selectedDocType} onChange={(e) => setSelectedDocType(e.target.value)} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                  {DOCUMENT_TYPES.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
                </select>
              </div>
              <button onClick={() => fileInputRef.current?.click()} className="inline-flex items-center px-4 py-2 border-2 border-dashed border-slate-300 rounded-lg text-sm font-medium text-slate-600 hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-all">
                <Plus className="h-4 w-4 mr-1.5" /> Add File
              </button>
              <input ref={fileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" onChange={handleAddFile} />
            </div>

            {/* Drag-drop zone */}
            {files.length === 0 && (
              <div
                className="border-2 border-dashed border-slate-300 rounded-xl p-12 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition-all"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-10 w-10 mx-auto text-slate-300 mb-3" />
                <p className="text-sm font-medium text-slate-600">Click to browse or drag files here</p>
                <p className="text-xs text-slate-400 mt-1">PDF, JPG, PNG — max 10MB per file</p>
              </div>
            )}

            {/* File list */}
            {files.length > 0 && (
              <div className="space-y-2">
                {files.map((f, idx) => (
                  <div key={idx} className={`flex items-center justify-between px-4 py-3 rounded-lg border ${
                    f.status === 'done' ? 'bg-emerald-50 border-emerald-200' :
                    f.status === 'error' ? 'bg-rose-50 border-rose-200' :
                    f.status === 'uploading' ? 'bg-blue-50 border-blue-200' :
                    'bg-white border-slate-200'
                  }`}>
                    <div className="flex items-center">
                      <FileText className={`h-5 w-5 mr-3 ${f.status === 'done' ? 'text-emerald-500' : f.status === 'error' ? 'text-rose-500' : 'text-slate-400'}`} />
                      <div>
                        <p className="text-sm font-medium text-slate-900">{f.file.name}</p>
                        <p className="text-xs text-slate-500">{DOCUMENT_TYPES.find(d => d.value === f.docType)?.label} — {(f.file.size / 1024).toFixed(0)} KB</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {f.status === 'done' && <CheckCircle className="h-5 w-5 text-emerald-500" />}
                      {f.status === 'uploading' && <div className="h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />}
                      {f.status === 'error' && <AlertCircle className="h-5 w-5 text-rose-500" />}
                      {f.status === 'pending' && (
                        <button onClick={() => handleRemoveFile(idx)} className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600">
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-between">
            <button onClick={() => setStep(3)} className="text-sm text-slate-500 hover:text-slate-700 font-medium">
              Skip uploads →
            </button>
            <button onClick={handleUploadAll} disabled={submitting || files.length === 0} className="inline-flex items-center px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-200 disabled:opacity-50 transition-all">
              {submitting ? 'Uploading...' : `Upload ${files.filter(f => f.status === 'pending').length} File(s) & Continue`}
              <ArrowRight className="ml-2 h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Trigger Screening */}
      {step === 3 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
            <h3 className="text-lg font-semibold text-slate-900">Run THOA Compliance Screening</h3>
            <p className="text-sm text-slate-500 mt-1">The rule engine will evaluate uploaded documents against all applicable THOA sections.</p>
          </div>

          <div className="p-8 text-center space-y-6">
            {screeningStatus === 'idle' && (
              <>
                <div className="w-20 h-20 mx-auto rounded-full bg-blue-100 flex items-center justify-center">
                  <FileText className="h-10 w-10 text-blue-600" />
                </div>
                <div>
                  <p className="text-lg font-medium text-slate-900">Case is ready for screening</p>
                  <p className="text-sm text-slate-500 mt-1">{files.filter(f => f.status === 'done').length} document(s) attached. Click below to run the THOA rule engine.</p>
                </div>
                <button onClick={handleTriggerScreening} className="inline-flex items-center px-6 py-3 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 focus:ring-4 focus:ring-emerald-200 transition-all">
                  Run Screening Engine
                  <ArrowRight className="ml-2 h-4 w-4" />
                </button>
              </>
            )}

            {screeningStatus === 'running' && (
              <>
                <div className="w-20 h-20 mx-auto rounded-full bg-blue-50 flex items-center justify-center">
                  <div className="h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
                <div>
                  <p className="text-lg font-medium text-slate-900">Screening in progress...</p>
                  <p className="text-sm text-slate-500 mt-1">Running OCR extraction and THOA rule evaluation. This may take a moment.</p>
                </div>
              </>
            )}

            {screeningStatus === 'done' && (
              <>
                <div className="w-20 h-20 mx-auto rounded-full bg-emerald-100 flex items-center justify-center">
                  <CheckCircle className="h-10 w-10 text-emerald-600" />
                </div>
                <div>
                  <p className="text-lg font-medium text-slate-900">Screening Complete</p>
                  <p className="text-sm text-slate-500 mt-1">Redirecting you to the case review page...</p>
                </div>
              </>
            )}

            {screeningStatus === 'error' && (
              <>
                <div className="w-20 h-20 mx-auto rounded-full bg-rose-100 flex items-center justify-center">
                  <AlertCircle className="h-10 w-10 text-rose-600" />
                </div>
                <div>
                  <p className="text-lg font-medium text-slate-900">Screening Failed</p>
                  <p className="text-sm text-rose-600 mt-1">{error}</p>
                </div>
                <button onClick={() => navigate(`/cases/${createdCaseId}`)} className="inline-flex items-center px-5 py-2.5 border border-slate-300 text-sm font-medium rounded-lg hover:bg-slate-50 transition-all">
                  View Case Anyway →
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
