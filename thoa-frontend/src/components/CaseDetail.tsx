import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, CheckCircle2, Info, FileText, Activity, Image, Upload, Download } from 'lucide-react';
import { fetchCaseDetails, fetchAuditLogs, submitDecision, fetchDocuments, getDocumentFileUrl } from '../api';
import type { CaseDetail, AuditLog, CaseDocument } from '../api';

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [decision, setDecision] = useState<string>('');
  const [comment, setComment] = useState('');
  const [overrideJustification, setOverrideJustification] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [documents, setDocuments] = useState<CaseDocument[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  // HITL States
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  
  // Websocket state
  const [wsStatus, setWsStatus] = useState<string>('');

  useEffect(() => {
    if (id) {
      Promise.all([fetchCaseDetails(id), fetchAuditLogs(id), fetchDocuments(id)]).then(([detail, logs, docs]) => {
        setCaseDetail(detail);
        setAuditLogs(logs);
        setDocuments(docs);
        if (docs.length > 0) setSelectedDocId(docs[0].id);
        setLoading(false);
      });

      // Connect WebSocket
      const ws = new WebSocket(`ws://127.0.0.1:8000/cases/ws/${id}`);
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.event === 'screening_started') {
            setWsStatus(data.message);
        } else if (data.event === 'document_uploaded') {
            setWsStatus(`Document ${data.filename} uploaded and processed.`);
            fetchDocuments(id).then(setDocuments);
        }
      };
      return () => ws.close();
    }
  }, [id]);

  const handleHITLSubmit = async (field: string, originalValue: string) => {
    try {
      await fetch(`http://127.0.0.1:8000/cases/${id}/corrections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field_name: field, original_text: originalValue, corrected_text: editValue })
      });
      alert('Correction saved to Training Data table. The AI will learn from this!');
      setEditingField(null);
    } catch (e) {
      console.error("Failed to submit correction");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !decision) return;
    
    if (decision === 'OVERRIDE' && overrideJustification.length < 20) {
      alert("Override requires a detailed justification (min 20 chars).");
      return;
    }
    
    setSubmitting(true);
    await submitDecision(id, decision, comment, decision === 'OVERRIDE' ? overrideJustification : undefined);
    setSubmitting(false);
    navigate('/');
  };

  if (loading || !caseDetail) {
    return <div className="p-8 text-center text-slate-500">Loading case details...</div>;
  }

  const hasCriticalFlags = caseDetail.explanations.some(e => e.needs_legal_verification);

  return (
    <div className="h-full flex flex-col -m-8">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-8 py-4 flex items-center justify-between z-10 shadow-sm">
        <div className="flex items-center">
          <Link to="/" className="mr-4 p-2 rounded-full hover:bg-slate-100 text-slate-500">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-slate-900">{caseDetail.case_number}</h2>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                caseDetail.status === 'AUTO_APPROVE' ? 'bg-emerald-100 text-emerald-800' :
                caseDetail.status === 'REJECTED' ? 'bg-rose-100 text-rose-800' :
                caseDetail.status === 'COMMITTEE_REVIEW' ? 'bg-amber-100 text-amber-800' :
                caseDetail.status === 'UNDER_REVIEW' ? 'bg-blue-100 text-blue-800' :
                'bg-slate-100 text-slate-800'
              }`}>
                {caseDetail.status.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-sm text-slate-500">
              {caseDetail.relation_type.replace('_', ' ')} • {caseDetail.hospital_name}
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-right">
            <p className="text-sm font-medium text-slate-900">Donor: {caseDetail.donor.full_name} ({caseDetail.donor.age})</p>
            <p className="text-sm text-slate-500">Recipient: {caseDetail.recipient.full_name} ({caseDetail.recipient.age})</p>
          </div>
          <a
            href={`http://127.0.0.1:8000/cases/${id}/report`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-3 py-2 bg-slate-800 text-white text-sm font-medium rounded-lg hover:bg-slate-700 transition-all shadow-sm"
          >
            <Download className="h-4 w-4 mr-1.5" /> PDF Report
          </a>
        </div>
      </div>

      {/* Split View */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Panel: Compliance & Controls */}
        <div className="w-1/2 flex flex-col bg-slate-50 border-r border-slate-200 overflow-y-auto">
          
          <div className="p-6 space-y-6">
            {/* System Recommendation */}
            <div className={`p-4 rounded-xl border ${hasCriticalFlags ? 'bg-amber-50 border-amber-200' : 'bg-emerald-50 border-emerald-200'}`}>
              <div className="flex items-start">
                {hasCriticalFlags ? 
                  <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" /> : 
                  <CheckCircle2 className="h-5 w-5 text-emerald-600 mt-0.5" />
                }
                <div className="ml-3">
                  <h3 className={`text-sm font-medium ${hasCriticalFlags ? 'text-amber-800' : 'text-emerald-800'}`}>
                    {hasCriticalFlags ? 'Anomalies Detected (Pending Committee Review)' : 'Documentation Complete (Ready for Approval)'}
                  </h3>
                  <p className={`mt-1 text-sm ${hasCriticalFlags ? 'text-amber-700' : 'text-emerald-700'}`}>
                    The screening engine evaluated this case against THOA rules. Please review the flags below.
                  </p>
                </div>
              </div>
            </div>

            {/* Rule Flags */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
                <h3 className="text-sm font-semibold text-slate-800 flex items-center">
                  <Info className="h-4 w-4 mr-2 text-slate-500" /> Compliance Report
                </h3>
              </div>
              <div className="divide-y divide-slate-100">
                {caseDetail.explanations.length === 0 ? (
                  <div className="p-4 text-sm text-slate-500 text-center">No anomalies detected.</div>
                ) : (
                  caseDetail.explanations.map((exp, idx) => (
                    <div key={idx} className="p-4">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-semibold px-2 py-1 bg-slate-100 text-slate-700 rounded-md">
                          {exp.rule_code}
                        </span>
                        {exp.needs_legal_verification && (
                          <span className="text-xs font-medium text-rose-600 flex items-center">
                            <AlertTriangle className="h-3 w-3 mr-1" /> Legal Verification Required
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-900 font-medium mb-1">{exp.rule_description}</p>
                      <div className="mt-2 text-xs text-slate-600 bg-slate-50 p-2 rounded border border-slate-100">
                        <span className="font-semibold text-slate-700">Evidence:</span> {exp.evidence}
                      </div>
                      <div className="mt-2 text-xs text-blue-700 font-medium">
                        &rarr; Suggested Action: {exp.next_step}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Extracted Data & HITL */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-800 mb-4 flex items-center justify-between">
                <span>Extracted Data (OCR/VLM)</span>
                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">HITL Enabled</span>
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center text-sm border-b pb-2">
                    <span className="text-slate-500">Donor Aadhaar:</span>
                    {editingField === 'donor_aadhaar' ? (
                        <div className="flex gap-2">
                            <input autoFocus value={editValue} onChange={e => setEditValue(e.target.value)} className="border rounded px-2 py-1 text-xs" />
                            <button onClick={() => handleHITLSubmit('donor_aadhaar', 'xxxx-xxxx-1234')} className="bg-emerald-500 text-white px-2 py-1 rounded text-xs">Save</button>
                            <button onClick={() => setEditingField(null)} className="text-xs text-slate-400">Cancel</button>
                        </div>
                    ) : (
                        <div className="flex gap-2 items-center">
                            <span className="font-medium text-slate-900 bg-yellow-100 px-1 rounded cursor-crosshair group relative" title="Highlighted on document">
                                xxxx-xxxx-1234
                            </span>
                            <button onClick={() => {setEditingField('donor_aadhaar'); setEditValue('xxxx-xxxx-1234');}} className="text-xs text-blue-500 hover:underline">Fix Typo</button>
                        </div>
                    )}
                </div>
                <div className="flex justify-between items-center text-sm border-b pb-2">
                    <span className="text-slate-500">Donor Age:</span>
                    {editingField === 'donor_age' ? (
                        <div className="flex gap-2">
                            <input autoFocus value={editValue} onChange={e => setEditValue(e.target.value)} className="border rounded px-2 py-1 text-xs" />
                            <button onClick={() => handleHITLSubmit('donor_age', caseDetail.donor.age.toString())} className="bg-emerald-500 text-white px-2 py-1 rounded text-xs">Save</button>
                            <button onClick={() => setEditingField(null)} className="text-xs text-slate-400">Cancel</button>
                        </div>
                    ) : (
                        <div className="flex gap-2 items-center">
                            <span className="font-medium text-slate-900 bg-yellow-100 px-1 rounded cursor-crosshair" title="Highlighted on document">
                                {caseDetail.donor.age}
                            </span>
                            <button onClick={() => {setEditingField('donor_age'); setEditValue(caseDetail.donor.age.toString());}} className="text-xs text-blue-500 hover:underline">Fix Typo</button>
                        </div>
                    )}
                </div>
              </div>
            </div>

            {/* Decision Form */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-800 mb-4">Submit Committee Decision</h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                
                <div className="flex space-x-3">
                  <label className={`flex-1 border rounded-lg p-3 cursor-pointer transition-all ${decision === 'APPROVED' ? 'bg-emerald-50 border-emerald-500 ring-1 ring-emerald-500' : 'hover:bg-slate-50 border-slate-200'}`}>
                    <input type="radio" name="decision" value="APPROVED" className="sr-only" onChange={(e) => setDecision(e.target.value)} />
                    <span className="block text-sm font-medium text-center text-slate-900">Approve</span>
                  </label>
                  <label className={`flex-1 border rounded-lg p-3 cursor-pointer transition-all ${decision === 'MORE_INFO' ? 'bg-blue-50 border-blue-500 ring-1 ring-blue-500' : 'hover:bg-slate-50 border-slate-200'}`}>
                    <input type="radio" name="decision" value="MORE_INFO" className="sr-only" onChange={(e) => setDecision(e.target.value)} />
                    <span className="block text-sm font-medium text-center text-slate-900">Request Info</span>
                  </label>
                  <label className={`flex-1 border rounded-lg p-3 cursor-pointer transition-all ${decision === 'REJECTED' ? 'bg-rose-50 border-rose-500 ring-1 ring-rose-500' : 'hover:bg-slate-50 border-slate-200'}`}>
                    <input type="radio" name="decision" value="REJECTED" className="sr-only" onChange={(e) => setDecision(e.target.value)} />
                    <span className="block text-sm font-medium text-center text-slate-900">Reject</span>
                  </label>
                </div>

                {hasCriticalFlags && decision === 'APPROVED' && (
                  <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-lg">
                    <label className="flex items-center space-x-2">
                      <input type="checkbox" checked={decision === 'OVERRIDE'} onChange={(e) => e.target.checked ? setDecision('OVERRIDE') : setDecision('APPROVED')} className="rounded text-rose-600 focus:ring-rose-500" />
                      <span className="text-sm font-medium text-rose-800">I am overriding a critical rule flag</span>
                    </label>
                  </div>
                )}

                {decision === 'OVERRIDE' && (
                  <div className="space-y-1">
                    <label className="block text-sm font-medium text-slate-700">Override Justification (Required) <span className="text-rose-500">*</span></label>
                    <textarea 
                      required
                      minLength={20}
                      className="w-full border-slate-300 rounded-md shadow-sm focus:ring-rose-500 focus:border-rose-500 sm:text-sm p-2 border" 
                      rows={3} 
                      placeholder="Specify the legal or medical basis for overriding the THOA rule flag..."
                      value={overrideJustification}
                      onChange={(e) => setOverrideJustification(e.target.value)}
                    />
                    <p className="text-xs text-slate-500">Must be at least 20 characters and will be permanently logged.</p>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="block text-sm font-medium text-slate-700">Internal Comment (Optional)</label>
                  <textarea 
                    className="w-full border-slate-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm p-2 border" 
                    rows={2} 
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                  />
                </div>

                <button 
                  type="submit" 
                  disabled={!decision || submitting || (decision === 'OVERRIDE' && overrideJustification.length < 20)}
                  className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-slate-900 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-900 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? 'Submitting...' : 'Submit Decision'}
                </button>
              </form>
            </div>

            {/* Audit History */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-800 mb-4 flex items-center">
                <Activity className="h-4 w-4 mr-2 text-slate-500" /> Audit History
              </h3>
              <div className="flow-root">
                <ul className="-mb-8">
                  {auditLogs.map((log, logIdx) => (
                    <li key={log.id}>
                      <div className="relative pb-8">
                        {logIdx !== auditLogs.length - 1 ? (
                          <span className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-slate-200" aria-hidden="true" />
                        ) : null}
                        <div className="relative flex space-x-3">
                          <div>
                            <span className="h-8 w-8 rounded-full bg-slate-100 flex items-center justify-center ring-8 ring-white">
                              <div className="h-2.5 w-2.5 bg-slate-400 rounded-full" />
                            </span>
                          </div>
                          <div className="min-w-0 flex-1 pt-1.5 flex justify-between space-x-4">
                            <div>
                              <p className="text-sm text-slate-500">
                                {log.action} <span className="font-medium text-slate-900">by {log.user_id}</span>
                              </p>
                              {log.detail && (
                                <p className="mt-1 text-xs text-slate-500 bg-slate-50 p-1.5 rounded">{JSON.stringify(log.detail)}</p>
                              )}
                            </div>
                            <div className="text-right text-xs whitespace-nowrap text-slate-500">
                              <time dateTime={log.created_at}>{new Date(log.created_at).toLocaleString()}</time>
                            </div>
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

          </div>
        </div>

        {/* Right Panel: Document Viewer */}
        <div className="w-1/2 bg-slate-800 flex flex-col">
          <div className="h-12 bg-slate-900 flex items-center px-4 justify-between border-b border-slate-700">
            <div className="flex items-center text-slate-300 text-sm font-medium">
              <FileText className="h-4 w-4 mr-2" />
              Document Viewer (Layout-Aware Bounding Boxes)
              {documents.length > 0 && (
                <span className="ml-2 text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded-full">{documents.length}</span>
              )}
            </div>
            {wsStatus && <div className="text-xs text-emerald-400 animate-pulse">{wsStatus}</div>}
            {documents.length > 0 && (
              <select
                className="bg-slate-800 text-slate-300 text-xs border border-slate-600 rounded px-2 py-1 max-w-[220px]"
                value={selectedDocId || ''}
                onChange={(e) => setSelectedDocId(e.target.value)}
              >
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.document_type.replace(/_/g, ' ')} — {doc.original_filename}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div className="flex-1 p-4 flex items-center justify-center overflow-auto">
            {documents.length === 0 ? (
              <div className="text-center">
                <Upload className="h-16 w-16 mx-auto text-slate-600 mb-4" />
                <p className="text-lg font-medium text-slate-400">No Documents Uploaded</p>
                <p className="text-sm text-slate-500 mt-2">Upload documents via the case creation wizard to view them here.</p>
              </div>
            ) : selectedDocId && id ? (
              (() => {
                const selectedDoc = documents.find(d => d.id === selectedDocId);
                const fileUrl = getDocumentFileUrl(id, selectedDocId);
                if (!selectedDoc) return null;

                if (selectedDoc.mime_type === 'application/pdf') {
                  return (
                    <iframe
                      src={fileUrl}
                      className="w-full h-full rounded shadow-2xl bg-white"
                      title={selectedDoc.original_filename}
                    />
                  );
                } else if (selectedDoc.mime_type?.startsWith('image/')) {
                  return (
                    <div className="relative inline-block">
                        <img
                          src={fileUrl}
                          alt={selectedDoc.original_filename}
                          className="max-w-full max-h-full object-contain rounded shadow-2xl"
                        />
                        {/* Mock Bounding Box representing OCR localization */}
                        <div className="absolute border-2 border-yellow-400 bg-yellow-400/20 pointer-events-none flex items-start justify-start" style={{ top: '25%', left: '40%', width: '150px', height: '30px' }}>
                            <span className="bg-yellow-400 text-black text-[10px] font-bold px-1 -mt-4">OCR: Aadhaar</span>
                        </div>
                        <div className="absolute border-2 border-yellow-400 bg-yellow-400/20 pointer-events-none flex items-start justify-start" style={{ top: '35%', left: '50%', width: '40px', height: '30px' }}>
                            <span className="bg-yellow-400 text-black text-[10px] font-bold px-1 -mt-4">OCR: Age</span>
                        </div>
                    </div>
                  );
                } else {
                  return (
                    <div className="text-center">
                      <FileText className="h-16 w-16 mx-auto text-slate-500 mb-4" />
                      <p className="text-sm text-slate-400">Preview not available for this file type.</p>
                      <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="mt-3 inline-block text-blue-400 text-sm hover:underline">
                        Download {selectedDoc.original_filename}
                      </a>
                    </div>
                  );
                }
              })()
            ) : null}
          </div>
        </div>

      </div>
    </div>
  );
}
