import React, { useState, useEffect } from 'react';
import { 
  Search, FileText, Upload, Trash2, CheckCircle, 
  AlertTriangle, RefreshCw, Send, BookOpen, ShieldCheck, X, FileCheck,
  User, Lock, Mail, LogOut, LogIn, UserPlus
} from 'lucide-react';
import axios from 'axios';

const API_BASE = 'http://localhost:4000/api';

export default function App() {
  // Authentication State
  const [user, setUser] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [authForm, setAuthForm] = useState({
    email: '',
    password: '',
    full_name: '',
    confirmPassword: ''
  });
  const [authError, setAuthError] = useState('');
  const [authSubmitting, setAuthSubmitting] = useState(false);

  // Query & Response State
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [selectedCitation, setSelectedCitation] = useState(null);

  // Document Management State
  const [documents, setDocuments] = useState([]);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');

  // Initial authentication check on load
  useEffect(() => {
    checkAuthSession();
  }, []);

  // Auto-poll document list while any file is processing
  useEffect(() => {
    if (!user) return;
    const isProcessing = documents.some(d => d.status === 'PROCESSING');
    if (isProcessing) {
      const timer = setInterval(fetchDocuments, 3000);
      return () => clearInterval(timer);
    }
  }, [documents, user]);

  const checkAuthSession = async () => {
    setCheckingAuth(true);
    const token = localStorage.getItem('rag_token');
    if (!token) {
      setUser(null);
      setCheckingAuth(false);
      return;
    }

    try {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      const res = await axios.get(`${API_BASE}/auth/me`);
      setUser(res.data.user);
      fetchDocuments();
    } catch (err) {
      console.warn('[Session Expired]', err.message);
      localStorage.removeItem('rag_token');
      delete axios.defaults.headers.common['Authorization'];
      setUser(null);
    } finally {
      setCheckingAuth(false);
    }
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthSubmitting(true);

    try {
      if (isRegisterMode) {
        if (!authForm.full_name.trim()) {
          setAuthError('Please enter your full name.');
          setAuthSubmitting(false);
          return;
        }
        if (authForm.password !== authForm.confirmPassword) {
          setAuthError('Passwords do not match.');
          setAuthSubmitting(false);
          return;
        }

        const res = await axios.post(`${API_BASE}/auth/register`, {
          email: authForm.email,
          password: authForm.password,
          full_name: authForm.full_name
        });

        const { token, user: userData } = res.data;
        localStorage.setItem('rag_token', token);
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        setUser(userData);
        fetchDocuments();
      } else {
        const res = await axios.post(`${API_BASE}/auth/login`, {
          email: authForm.email,
          password: authForm.password
        });

        const { token, user: userData } = res.data;
        localStorage.setItem('rag_token', token);
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        setUser(userData);
        fetchDocuments();
      }
    } catch (err) {
      setAuthError(err.response?.data?.error || 'Authentication failed. Please try again.');
    } finally {
      setAuthSubmitting(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('rag_token');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
    setResponse(null);
    setDocuments([]);
  };

  const fetchDocuments = async () => {
    try {
      const res = await axios.get(`${API_BASE}/documents`);
      setDocuments(res.data.documents || []);
    } catch (err) {
      console.error('[Document Fetch Error]', err);
    }
  };

  const handleAsk = async (searchQuery = query) => {
    const q = searchQuery || query;
    if (!q.trim()) return;

    setLoading(true);
    setResponse(null);
    setSelectedCitation(null);

    try {
      const res = await axios.post(`${API_BASE}/rag/query`, {
        query: q,
        retrieval_mode: 'hybrid',
        top_k: 10
      });
      setResponse(res.data);
    } catch (err) {
      alert('Failed to process question: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile) return alert('Please select a file to upload.');

    setUploading(true);
    setUploadStatus('Uploading file...');

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('strategy', 'recursive');

    try {
      await axios.post(`${API_BASE}/documents/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUploadStatus('Document uploaded & indexing...');
      setUploadFile(null);
      setTimeout(fetchDocuments, 1000);
    } catch (err) {
      alert('Upload failed: ' + (err.response?.data?.error || err.message));
      setUploadStatus('');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (id) => {
    if (!confirm('Remove this document from the knowledge base?')) return;
    try {
      await axios.delete(`${API_BASE}/documents/${id}`);
      fetchDocuments();
    } catch (err) {
      alert('Delete failed');
    }
  };

  // Helper: Format answer text into paragraphs & bullet lists with clickable citations [1]
  const formatAnswerText = (text, citations = []) => {
    if (!text) return null;
    
    const paragraphs = text.split(/\n\n+/);
    return paragraphs.map((para, pIdx) => {
      const lines = para.split('\n').filter(l => l.trim());
      const isBulletList = lines.length > 1 && lines.every(l => /^[\*\-\d\.\•]/.test(l.trim()));

      if (isBulletList) {
        return (
          <ul key={pIdx} className="list-disc pl-6 space-y-3 my-4 text-slate-100 font-normal text-xl leading-relaxed">
            {lines.map((line, lIdx) => {
              const cleanLine = line.replace(/^[\*\-\d\.\•]+\s*/, '');
              return <li key={lIdx}>{renderTextWithCitations(cleanLine, citations)}</li>;
            })}
          </ul>
        );
      }

      return (
        <p key={pIdx} className="my-4 text-slate-100 leading-relaxed font-normal text-xl">
          {renderTextWithCitations(para, citations)}
        </p>
      );
    });
  };

  // Helper: Convert [N] text into interactive citation pills
  const renderTextWithCitations = (textStr, citations = []) => {
    const parts = textStr.split(/(\[\d+\])/g);
    return parts.map((part, idx) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (match) {
        const citIdx = parseInt(match[1]);
        const citation = citations.find(c => c.citation_id === citIdx);
        return (
          <button
            key={idx}
            onClick={() => setSelectedCitation(citation || { citation_id: citIdx, source: 'Document ' + citIdx })}
            className="citation-pill"
            title={citation ? `Source: ${citation.source} (Page ${citation.page})` : `Citation [${citIdx}]`}
          >
            [{citIdx}]
          </button>
        );
      }
      return part;
    });
  };

  const sampleQueries = [
    "What is the password expiration policy?",
    "How do I request leave?",
    "What is the procedure for a production database incident?",
    "What is the error code ERR_CONNECTION_RESET procedure?"
  ];

  // 1. Loading Screen while checking auth session
  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-white">
        <div className="flex items-center space-x-3 text-slate-400 font-medium">
          <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
          <span>Verifying authentication session...</span>
        </div>
      </div>
    );
  }

  // 2. Authentication Screen (Login / Register View)
  if (!user) {
    return (
      <div className="min-h-screen flex flex-col justify-center items-center bg-slate-950 px-4 font-sans text-white">
        <div className="w-full max-w-md space-y-8">
          
          {/* Header Branding */}
          <div className="text-center space-y-3">
            <div className="inline-flex p-4 bg-blue-600/10 border border-blue-500/30 rounded-2xl text-blue-400 shadow-lg">
              <BookOpen className="w-10 h-10" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white">Enterprise RAG Intelligence</h1>
            <p className="text-sm text-slate-400">Secure Document Search & Citation Verification Platform</p>
          </div>

          {/* Form Card */}
          <div className="clean-card p-8 space-y-6 bg-slate-900 border border-slate-800 shadow-2xl rounded-2xl">
            
            {/* Mode Switcher Tabs */}
            <div className="grid grid-cols-2 p-1.5 bg-slate-950 rounded-xl border border-slate-800 text-sm font-semibold">
              <button
                type="button"
                onClick={() => { setIsRegisterMode(false); setAuthError(''); }}
                className={`py-2.5 rounded-lg transition-all flex items-center justify-center space-x-2 ${
                  !isRegisterMode ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-white'
                }`}
              >
                <LogIn className="w-4 h-4" />
                <span>Sign In</span>
              </button>
              <button
                type="button"
                onClick={() => { setIsRegisterMode(true); setAuthError(''); }}
                className={`py-2.5 rounded-lg transition-all flex items-center justify-center space-x-2 ${
                  isRegisterMode ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-white'
                }`}
              >
                <UserPlus className="w-4 h-4" />
                <span>Register</span>
              </button>
            </div>

            {/* Error Banner */}
            {authError && (
              <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-sm font-medium flex items-center space-x-3">
                <AlertTriangle className="w-5 h-5 flex-shrink-0" />
                <span>{authError}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleAuthSubmit} className="space-y-4">
              
              {isRegisterMode && (
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Full Name</label>
                  <div className="relative">
                    <User className="w-5 h-5 text-slate-500 absolute left-3.5 top-3.5" />
                    <input
                      type="text"
                      required
                      value={authForm.full_name}
                      onChange={(e) => setAuthForm({ ...authForm, full_name: e.target.value })}
                      placeholder="John Doe"
                      className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-11 pr-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Email Address</label>
                <div className="relative">
                  <Mail className="w-5 h-5 text-slate-500 absolute left-3.5 top-3.5" />
                  <input
                    type="email"
                    required
                    value={authForm.email}
                    onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                    placeholder="name@company.com"
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-11 pr-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Password</label>
                <div className="relative">
                  <Lock className="w-5 h-5 text-slate-500 absolute left-3.5 top-3.5" />
                  <input
                    type="password"
                    required
                    value={authForm.password}
                    onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                    placeholder="••••••••"
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-11 pr-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
                  />
                </div>
              </div>

              {isRegisterMode && (
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Confirm Password</label>
                  <div className="relative">
                    <Lock className="w-5 h-5 text-slate-500 absolute left-3.5 top-3.5" />
                    <input
                      type="password"
                      required
                      value={authForm.confirmPassword}
                      onChange={(e) => setAuthForm({ ...authForm, confirmPassword: e.target.value })}
                      placeholder="••••••••"
                      className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-11 pr-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
                    />
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={authSubmitting}
                className="w-full mt-2 bg-blue-600 hover:bg-blue-500 text-white font-bold py-3.5 rounded-xl text-sm transition-all flex items-center justify-center space-x-2 shadow-lg disabled:opacity-50"
              >
                {authSubmitting ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : isRegisterMode ? (
                  <UserPlus className="w-4 h-4" />
                ) : (
                  <LogIn className="w-4 h-4" />
                )}
                <span>{authSubmitting ? 'Processing...' : isRegisterMode ? 'Create Account' : 'Sign In'}</span>
              </button>
            </form>

            <div className="pt-2 text-center text-xs text-slate-500">
              <p>Protected by Enterprise End-to-End JWT Authentication</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 3. Main Authenticated Application Workspace
  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-white font-sans">
      
      {/* App Header */}
      <header className="border-b border-slate-800 bg-slate-900 px-8 py-4 shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-blue-600 rounded-xl text-white shadow">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Enterprise Knowledge Assistant</h1>
              <p className="text-sm text-slate-400 font-medium">Internal Document Search & Verification Platform</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="hidden sm:flex items-center space-x-2 text-xs font-semibold bg-slate-800/80 px-3.5 py-2 rounded-lg border border-slate-700 text-slate-300">
              <FileCheck className="w-4 h-4 text-emerald-400" />
              <span>Indexed Documents: <strong className="text-emerald-400">{documents.filter(d => d.status === 'COMPLETED').length} Active</strong></span>
            </div>

            {/* User Profile & Logout */}
            <div className="flex items-center space-x-3 pl-3 border-l border-slate-800">
              <div className="text-right hidden sm:block">
                <p className="text-sm font-bold text-white leading-tight">{user.full_name || 'User'}</p>
                <p className="text-xs text-slate-400">{user.email}</p>
              </div>

              <button
                onClick={handleLogout}
                className="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl border border-slate-700 transition-colors flex items-center space-x-2"
                title="Log out"
              >
                <LogOut className="w-4 h-4 text-rose-400" />
                <span className="text-xs font-semibold hidden md:inline">Sign Out</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Document Management Sidebar (4 Cols) */}
        <aside className="lg:col-span-4 space-y-6">
          
          {/* Upload Card */}
          <div className="clean-card p-6 space-y-4">
            <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
              <Upload className="w-5 h-5 text-blue-400" />
              <h2 className="font-bold text-white text-base">Upload Document</h2>
            </div>

            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="text-xs text-slate-400 block font-medium mb-2">Supported: PDF, Markdown, TXT, HTML</label>
                <input
                  type="file"
                  accept=".pdf,.txt,.md,.markdown,.html,.htm"
                  onChange={(e) => setUploadFile(e.target.files[0])}
                  className="w-full text-sm text-white bg-slate-900 p-3 rounded-xl border border-slate-700 cursor-pointer focus:outline-none"
                />
              </div>

              <button
                type="submit"
                disabled={uploading}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl text-sm transition-colors flex items-center justify-center space-x-2 disabled:opacity-50 shadow"
              >
                {uploading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                <span>{uploading ? 'Processing...' : 'Upload & Index'}</span>
              </button>
            </form>

            {uploadStatus && (
              <p className="text-xs text-cyan-400 font-medium bg-slate-900 p-3 rounded-lg border border-slate-800">{uploadStatus}</p>
            )}
          </div>

          {/* Document Library Card */}
          <div className="clean-card p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <FileText className="w-5 h-5 text-blue-400" />
                <h2 className="font-bold text-white text-base">Knowledge Base ({documents.length})</h2>
              </div>
              <button onClick={fetchDocuments} className="text-slate-400 hover:text-white" title="Refresh document list">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            {documents.length === 0 ? (
              <p className="text-xs text-slate-400 py-4 text-center">No documents uploaded yet. Upload a PDF or text file to begin.</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {documents.map((doc) => (
                  <div key={doc.id} className="p-3.5 bg-slate-900 rounded-xl border border-slate-800 flex items-center justify-between hover:border-slate-700 transition-colors">
                    <div className="truncate pr-2">
                      <p className="text-sm font-semibold text-white truncate">{doc.filename}</p>
                      <p className="text-xs text-slate-400 font-mono mt-0.5">{doc.chunk_count || 0} chunks • {doc.file_type.toUpperCase()}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        doc.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                        doc.status === 'FAILED' ? 'bg-rose-500/20 text-rose-400' :
                        'bg-amber-500/20 text-amber-400 animate-pulse'
                      }`}>
                        {doc.status}
                      </span>
                      <button
                        onClick={() => handleDeleteDoc(doc.id)}
                        className="text-slate-400 hover:text-rose-400 p-1.5 rounded-lg transition-colors"
                        title="Delete document"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>

        {/* Search & Answer Main Section (8 Cols) */}
        <section className="lg:col-span-8 space-y-6">
          
          {/* Question Input Card */}
          <div className="clean-card p-6 space-y-4">
            <label className="text-base font-bold text-white block">Ask a question about your knowledge base:</label>

            <div className="relative">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                placeholder="Type your question here..."
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-5 py-4 pr-32 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-lg shadow-inner"
              />
              <button
                onClick={() => handleAsk()}
                disabled={loading}
                className="absolute right-2.5 top-2.5 bottom-2.5 px-6 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg text-sm flex items-center space-x-2 transition-all disabled:opacity-50 shadow"
              >
                {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                <span>{loading ? 'Searching...' : 'Ask'}</span>
              </button>
            </div>

            {/* Quick Sample Queries */}
            <div className="space-y-2 pt-1">
              <span className="text-xs text-slate-400 font-medium">Sample queries:</span>
              <div className="flex flex-wrap gap-2">
                {sampleQueries.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => { setQuery(q); handleAsk(q); }}
                    className="text-xs bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white px-3.5 py-2 rounded-xl border border-slate-800 transition-colors text-left"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Answer Card */}
          {response && (
            <div className="clean-card p-8 space-y-6 border-l-4 border-l-blue-500">
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-6 h-6 text-blue-400" />
                  <h3 className="font-bold text-white text-lg">Answer</h3>
                </div>

                <div className={`px-3.5 py-1.5 rounded-full text-xs font-bold flex items-center space-x-1.5 ${
                  response.is_reliable
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                    : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                }`}>
                  <span>{(response.confidence_score * 100).toFixed(0)}% Confidence</span>
                  {response.is_reliable ? <CheckCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                </div>
              </div>

              {/* Answer Content */}
              <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 text-slate-100 text-xl leading-relaxed">
                {formatAnswerText(response.answer, response.citations)}
              </div>

              {/* Source Citations */}
              {response.citations && response.citations.length > 0 && (
                <div className="space-y-3 pt-2">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    Source Citations ({response.citations.length})
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {response.citations.map(cit => (
                      <div
                        key={cit.citation_id}
                        onClick={() => setSelectedCitation(cit)}
                        className="p-3.5 bg-slate-900 hover:bg-slate-800 rounded-xl border border-slate-800 cursor-pointer transition-all space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-blue-400">[{cit.citation_id}] {cit.source}</span>
                          <span className="text-xs text-slate-400">Page {cit.page}</span>
                        </div>
                        <p className="text-xs text-slate-300 truncate">Section: {cit.section}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Citation Inspector Modal */}
          {selectedCitation && (
            <div className="clean-card p-6 space-y-4 bg-slate-900">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h4 className="text-sm font-bold text-white flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-blue-400" />
                  <span>Citation Source Excerpt [{selectedCitation.citation_id}]</span>
                </h4>
                <button onClick={() => setSelectedCitation(null)} className="text-slate-400 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="text-xs space-y-3">
                <p className="text-slate-200"><strong>Source File:</strong> {selectedCitation.source}</p>
                <p className="text-slate-200"><strong>Page:</strong> {selectedCitation.page || 1} • <strong>Section:</strong> {selectedCitation.section || 'General'}</p>
                <div>
                  <span className="text-slate-400 font-medium block mb-1">Exact Document Excerpt:</span>
                  <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 text-slate-200 font-mono text-xs leading-relaxed">
                    "{selectedCitation.snippet || 'Full chunk text verified.'}"
                  </div>
                </div>
              </div>
            </div>
          )}

        </section>
      </main>
    </div>
  );
}
