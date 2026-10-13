import { useEffect, useState, type FormEvent } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, CheckCircle2, Info, Activity, Upload, Download, Scan, ShieldAlert, ShieldCheck, Layers } from 'lucide-react';
import { 
  fetchCaseDetails, fetchAuditLogs, submitDecision, fetchDocuments, 
  submitCorrection, WS_BASE_URL,
  fetchRenderedDocumentPage, fetchFraudAnalysis,
  type RenderedPageResponse, type FraudAnalysisResponse
} from '../api';
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

  // Document Viewer Inspector & Fraud States
  const [viewerMode, setViewerMode] = useState<'boxes' | 'fraud'>('boxes');
  const [renderedPage, setRenderedPage] = useState<RenderedPageResponse | null>(null);
  const [fraudAnalysis, setFraudAnalysis] = useState<FraudAnalysisResponse | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const [hoveredField, setHoveredField] = useState<string | null>(null);
  const [activePage, setActivePage] = useState(0);

  useEffect(() => {
    if (id && selectedDocId) {
      setDocLoading(true);
      Promise.all([
        fetchRenderedDocumentPage(id, selectedDocId, activePage).catch(() => null),
        fetchFraudAnalysis(id, selectedDocId).catch(() => null)
      ]).then(([pageData, fraudData]) => {
        setRenderedPage(pageData);
        setFraudAnalysis(fraudData);
        setDocLoading(false);
      });
    }
  }, [id, selectedDocId, activePage]);

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
      const ws = new WebSocket(`${WS_BASE_URL}/cases/ws/${id}`);
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
    if (!id) return;
    try {
      await submitCorrection(id, field, originalValue, editValue);
      alert('Correction saved to Training Data table. The AI will learn from this!');
      setEditingField(null);
    } catch (e) {
      console.error("Failed to submit correction", e);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
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
          {wsStatus && (
            <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-1 rounded-md animate-pulse">
              {wsStatus}
            </span>
          )}
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
              <h3 className="text-sm font-semibold text-slate-800 mb-3 flex items-center justify-between">
                <span className="flex items-center">
                  <Scan className="h-4 w-4 mr-1.5 text-blue-600" />
                  Extracted Document Fields (OCR / Layout)
                </span>
                <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded font-medium">HITL Active</span>
              </h3>
              <p className="text-xs text-slate-500 mb-3">
                Hover over any extracted field to pinpoint its exact bounding box on the original statutory form.
              </p>
              <div className="space-y-2">
                {/* Donor Name */}
                <div 
                  onMouseEnter={() => setHoveredField('donor_name')}
                  onMouseLeave={() => setHoveredField(null)}
                  className={`flex justify-between items-center text-sm p-2 rounded transition-all cursor-pointer ${
                    hoveredField === 'donor_name' ? 'bg-amber-50 ring-1 ring-amber-300' : 'hover:bg-slate-50'
                  }`}
                >
                  <span className="text-slate-600 text-xs font-medium">Donor Name:</span>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900 text-xs bg-slate-100 px-2 py-0.5 rounded">
                      {caseDetail.donor.full_name}
                    </span>
                    <span className="text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">95% conf</span>
                  </div>
                </div>

                {/* Donor Aadhaar */}
                <div 
                  onMouseEnter={() => setHoveredField('aadhaar')}
                  onMouseLeave={() => setHoveredField(null)}
                  className={`flex justify-between items-center text-sm p-2 rounded transition-all cursor-pointer ${
                    hoveredField === 'aadhaar' ? 'bg-amber-50 ring-1 ring-amber-300' : 'hover:bg-slate-50'
                  }`}
                >
                  <span className="text-slate-600 text-xs font-medium">Donor Aadhaar:</span>
                  {editingField === 'donor_aadhaar' ? (
                    <div className="flex gap-2">
                      <input autoFocus value={editValue} onChange={e => setEditValue(e.target.value)} className="border rounded px-2 py-1 text-xs" />
                      <button onClick={() => handleHITLSubmit('donor_aadhaar', 'xxxx-xxxx-1234')} className="bg-emerald-500 text-white px-2 py-1 rounded text-xs">Save</button>
                      <button onClick={() => setEditingField(null)} className="text-xs text-slate-400">Cancel</button>
                    </div>
                  ) : (
                    <div className="flex gap-2 items-center">
                      <span className="font-semibold text-slate-900 text-xs bg-yellow-100 px-2 py-0.5 rounded">
                        XXXX-XXXX-1098
                      </span>
                      <button onClick={(e) => { e.stopPropagation(); setEditingField('donor_aadhaar'); setEditValue('xxxx-xxxx-1234'); }} className="text-[11px] text-blue-600 hover:underline">Fix</button>
                    </div>
                  )}
                </div>

                {/* Donor Age / DOB */}
                <div 
                  onMouseEnter={() => setHoveredField('dob')}
                  onMouseLeave={() => setHoveredField(null)}
                  className={`flex justify-between items-center text-sm p-2 rounded transition-all cursor-pointer ${
                    hoveredField === 'dob' ? 'bg-amber-50 ring-1 ring-amber-300' : 'hover:bg-slate-50'
                  }`}
                >
                  <span className="text-slate-600 text-xs font-medium">Donor Age / DOB:</span>
                  {editingField === 'donor_age' ? (
                    <div className="flex gap-2">
                      <input autoFocus value={editValue} onChange={e => setEditValue(e.target.value)} className="border rounded px-2 py-1 text-xs" />
                      <button onClick={() => handleHITLSubmit('donor_age', caseDetail.donor.age.toString())} className="bg-emerald-500 text-white px-2 py-1 rounded text-xs">Save</button>
                      <button onClick={() => setEditingField(null)} className="text-xs text-slate-400">Cancel</button>
                    </div>
                  ) : (
                    <div className="flex gap-2 items-center">
                      <span className="font-semibold text-slate-900 text-xs bg-yellow-100 px-2 py-0.5 rounded">
                        {caseDetail.donor.age} Years
                      </span>
                      <button onClick={(e) => { e.stopPropagation(); setEditingField('donor_age'); setEditValue(caseDetail.donor.age.toString()); }} className="text-[11px] text-blue-600 hover:underline">Fix</button>
                    </div>
                  )}
                </div>

                {/* Recipient Name */}
                <div 
                  onMouseEnter={() => setHoveredField('recipient_name')}
                  onMouseLeave={() => setHoveredField(null)}
                  className={`flex justify-between items-center text-sm p-2 rounded transition-all cursor-pointer ${
                    hoveredField === 'recipient_name' ? 'bg-amber-50 ring-1 ring-amber-300' : 'hover:bg-slate-50'
                  }`}
                >
                  <span className="text-slate-600 text-xs font-medium">Recipient Name:</span>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900 text-xs bg-slate-100 px-2 py-0.5 rounded">
                      {caseDetail.recipient.full_name}
                    </span>
                    <span className="text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">94% conf</span>
                  </div>
                </div>

                {/* Organ */}
                <div 
                  onMouseEnter={() => setHoveredField('organ')}
                  onMouseLeave={() => setHoveredField(null)}
                  className={`flex justify-between items-center text-sm p-2 rounded transition-all cursor-pointer ${
                    hoveredField === 'organ' ? 'bg-amber-50 ring-1 ring-amber-300' : 'hover:bg-slate-50'
                  }`}
                >
                  <span className="text-slate-600 text-xs font-medium">Organ Type:</span>
                  <span className="font-semibold text-slate-900 text-xs bg-slate-100 px-2 py-0.5 rounded">
                    {caseDetail.organ_type || 'Kidney'}
                  </span>
                </div>
              </div>
            </div>

            {/* Decision Form */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-800 mb-4">Submit Committee Decision</h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                
                <div className="flex space-x-3">
                  <label className={`flex-1 border rounded-lg p-3 cursor-pointer transition-all ${decision === 'APPROVED' || decision === 'OVERRIDE' ? 'bg-emerald-50 border-emerald-500 ring-1 ring-emerald-500' : 'hover:bg-slate-50 border-slate-200'}`}>
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

                {hasCriticalFlags && (decision === 'APPROVED' || decision === 'OVERRIDE') && (
                  <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-lg">
                    <label className="flex items-center space-x-2">
                      <input 
                        type="checkbox" 
                        checked={decision === 'OVERRIDE'} 
                        onChange={(e) => setDecision(e.target.checked ? 'OVERRIDE' : 'APPROVED')} 
                        className="rounded text-rose-600 focus:ring-rose-500" 
                      />
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

        {/* Right Panel: Document Viewer Inspector */}
        <div className="w-1/2 bg-slate-900 flex flex-col border-l border-slate-800">
          
          {/* Viewer Header with Inspection Mode Switcher */}
          <div className="h-14 bg-slate-950 flex items-center px-4 justify-between border-b border-slate-800">
            <div className="flex items-center space-x-2">
              <select
                className="bg-slate-800 text-slate-200 text-xs border border-slate-700 rounded-lg px-2.5 py-1.5 max-w-[210px] focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={selectedDocId || ''}
                onChange={(e) => { setSelectedDocId(e.target.value); setActivePage(0); }}
              >
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.document_type.replace(/_/g, ' ')} — {doc.original_filename}
                  </option>
                ))}
              </select>

              {/* Multi-page controls if applicable */}
              {renderedPage && renderedPage.page_count > 1 && (
                <div className="flex items-center text-xs text-slate-400 space-x-1 pl-2 border-l border-slate-800">
                  <button 
                    disabled={activePage <= 0}
                    onClick={() => setActivePage(p => Math.max(0, p - 1))}
                    className="px-2 py-0.5 bg-slate-800 rounded hover:bg-slate-700 disabled:opacity-40"
                  >
                    &larr;
                  </button>
                  <span>{activePage + 1}/{renderedPage.page_count}</span>
                  <button 
                    disabled={activePage >= renderedPage.page_count - 1}
                    onClick={() => setActivePage(p => Math.min(renderedPage.page_count - 1, p + 1))}
                    className="px-2 py-0.5 bg-slate-800 rounded hover:bg-slate-700 disabled:opacity-40"
                  >
                    &rarr;
                  </button>
                </div>
              )}
            </div>

            {/* Mode Switcher */}
            <div className="flex items-center bg-slate-800/80 p-0.5 rounded-lg border border-slate-700/60">
              <button
                onClick={() => setViewerMode('boxes')}
                className={`flex items-center px-3 py-1 text-xs font-medium rounded-md transition-all ${
                  viewerMode === 'boxes'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                title="Interactive Bounding Box Inspector"
              >
                <Scan className="h-3.5 w-3.5 mr-1.5" />
                OCR Boxes
              </button>
              <button
                onClick={() => setViewerMode('fraud')}
                className={`flex items-center px-3 py-1 text-xs font-medium rounded-md transition-all ${
                  viewerMode === 'fraud'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                title="Computer Vision Synthetic Tampering & Fraud Defense"
              >
                <ShieldAlert className="h-3.5 w-3.5 mr-1.5" />
                CV Tampering Defense
              </button>
            </div>
          </div>

          {/* Viewer Canvas Area */}
          <div className="flex-1 p-4 flex flex-col items-center justify-start overflow-auto bg-slate-900/60 relative">
            {docLoading ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 space-y-3 my-auto">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
                <p className="text-xs">Processing document layout & forensic analysis...</p>
              </div>
            ) : documents.length === 0 ? (
              <div className="text-center my-auto">
                <Upload className="h-16 w-16 mx-auto text-slate-700 mb-4" />
                <p className="text-lg font-medium text-slate-400">No Documents Uploaded</p>
                <p className="text-sm text-slate-600 mt-2">Upload documents to inspect bounding boxes and fraud forensics.</p>
              </div>
            ) : viewerMode === 'boxes' ? (
              /* Mode 1: Layout Bounding Box Inspector */
              <div className="flex flex-col items-center w-full max-w-2xl">
                {/* Bounding Box Legend Bar */}
                <div className="w-full mb-3 flex items-center justify-between text-[11px] text-slate-400 bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800">
                  <span className="flex items-center">
                    <span className="w-2.5 h-2.5 rounded-sm bg-sky-400 inline-block mr-1.5" />
                    Layout Entity Box
                  </span>
                  <span className="flex items-center">
                    <span className="w-2.5 h-2.5 rounded-sm bg-amber-400 inline-block mr-1.5 animate-pulse" />
                    Focused / Hovered Field
                  </span>
                  <span>{renderedPage?.bounding_boxes.length || 0} Entities Tracked</span>
                </div>

                {renderedPage?.page_image ? (
                  <div className="relative inline-block rounded-lg shadow-2xl border border-slate-700 overflow-hidden bg-white">
                    <img
                      src={renderedPage.page_image}
                      alt="Rendered Document"
                      className="max-w-full h-auto block select-none"
                    />

                    {/* Interactive Bounding Boxes Overlay */}
                    {renderedPage.bounding_boxes.map((bbox, idx) => {
                      const isHovered = hoveredField === bbox.field;
                      return (
                        <div
                          key={idx}
                          onMouseEnter={() => setHoveredField(bbox.field)}
                          onMouseLeave={() => setHoveredField(null)}
                          className={`absolute transition-all cursor-pointer ${
                            isHovered
                              ? 'border-2 border-amber-400 bg-amber-400/35 ring-4 ring-amber-400/40 z-30 shadow-lg scale-[1.01]'
                              : 'border-2 border-sky-400/75 bg-sky-400/15 hover:border-amber-300 hover:bg-amber-300/25 z-10'
                          }`}
                          style={{
                            left: `${bbox.x * 100}%`,
                            top: `${bbox.y * 100}%`,
                            width: `${bbox.w * 100}%`,
                            height: `${bbox.h * 100}%`,
                          }}
                        >
                          <span className={`absolute -top-4 left-0 text-[9px] font-bold px-1 rounded shadow-sm whitespace-nowrap transition-all ${
                            isHovered
                              ? 'bg-amber-400 text-black scale-105'
                              : 'bg-sky-600 text-white'
                          }`}>
                            {bbox.field.replace('_', ' ')} • {Math.round(bbox.confidence * 100)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center my-auto text-slate-500 text-xs">
                    Could not render document image.
                  </div>
                )}
              </div>
            ) : (
              /* Mode 2: Computer Vision Synthetic Tampering & Fraud Defense */
              <div className="flex flex-col items-center w-full max-w-2xl space-y-4">
                {fraudAnalysis ? (
                  <>
                    {/* Forensic Telemetry Bar */}
                    <div className="w-full bg-slate-950/90 rounded-xl p-4 border border-slate-800 shadow-xl space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <ShieldCheck className="h-5 w-5 text-purple-400" />
                          <span className="text-xs font-semibold text-slate-200">
                            Computer Vision Forensic Defense
                          </span>
                        </div>
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                          fraudAnalysis.risk_level === 'LOW'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                            : fraudAnalysis.risk_level === 'MEDIUM'
                            ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                            : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                        }`}>
                          {fraudAnalysis.verdict.replace(/_/g, ' ')} ({fraudAnalysis.fraud_risk_score}/100)
                        </span>
                      </div>

                      {/* Forensic Key Metrics Grid */}
                      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800/80 text-center">
                        <div className="bg-slate-900 p-2 rounded-lg">
                          <p className="text-[10px] text-slate-400">ELA Variance</p>
                          <p className="text-xs font-mono font-bold text-slate-200">{fraudAnalysis.ela_variance}</p>
                          <p className="text-[9px] text-emerald-400">Normal Range (&lt;180)</p>
                        </div>
                        <div className="bg-slate-900 p-2 rounded-lg">
                          <p className="text-[10px] text-slate-400">Splicing Seams</p>
                          <p className="text-xs font-mono font-bold text-slate-200">{fraudAnalysis.splice_boxes_count}</p>
                          <p className="text-[9px] text-slate-400">Edge Discontinuities</p>
                        </div>
                        <div className="bg-slate-900 p-2 rounded-lg">
                          <p className="text-[10px] text-slate-400">Statutory Signatures</p>
                          <p className={`text-xs font-bold ${
                            fraudAnalysis.signature_verification.signatures_detected ? 'text-emerald-400' : 'text-rose-400'
                          }`}>
                            {fraudAnalysis.signature_verification.signatures_detected ? 'Verified' : 'Missing'}
                          </p>
                          <p className="text-[9px] text-slate-400">Density: {fraudAnalysis.signature_verification.ink_density}</p>
                        </div>
                      </div>

                      {/* Anomalies List if any */}
                      {fraudAnalysis.anomalies_detected.length > 0 && (
                        <div className="space-y-1.5 pt-2 border-t border-slate-800">
                          {fraudAnalysis.anomalies_detected.map((ano, idx) => (
                            <div key={idx} className="bg-amber-950/40 border border-amber-800/50 p-2 rounded text-xs flex items-start space-x-2">
                              <AlertTriangle className="h-3.5 w-3.5 text-amber-400 mt-0.5 shrink-0" />
                              <div>
                                <span className="font-semibold text-amber-300">[{ano.code}] {ano.title}: </span>
                                <span className="text-slate-300 text-[11px]">{ano.description}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Forensic Heatmap Image */}
                    {fraudAnalysis.heatmap_image && (
                      <div className="rounded-lg shadow-2xl border border-purple-900/60 overflow-hidden bg-black max-w-full">
                        <div className="bg-purple-950 px-3 py-1.5 text-[11px] text-purple-200 flex items-center justify-between border-b border-purple-800/50">
                          <span className="flex items-center font-medium">
                            <Layers className="h-3 w-3 mr-1.5" />
                            Error Level Analysis (ELA) + Boundary Seam Heatmap
                          </span>
                          <span className="text-[9px] text-purple-300 font-mono">150 DPI Analysis</span>
                        </div>
                        <img
                          src={fraudAnalysis.heatmap_image}
                          alt="Forensic Tampering Heatmap"
                          className="max-w-full h-auto block select-none"
                        />
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center my-auto text-slate-500 text-xs">
                    Running computer vision fraud analysis...
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
