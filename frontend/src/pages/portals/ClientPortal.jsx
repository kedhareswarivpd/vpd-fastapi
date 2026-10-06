import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { 
  Building2, 
  Briefcase, 
  FileText, 
  CreditCard, 
  Headphones, 
  Download, 
  CheckCircle2, 
  Clock
} from 'lucide-react';

export const ClientPortal = () => {
  const { user } = useAuth();
  const [projects, setProjects] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchClientData = async () => {
      setLoading(true);
      try {
        const [pRes, iRes, tRes] = await Promise.allSettled([
          api.get('/projects'),
          api.get('/invoices'),
          api.get('/tickets')
        ]);
        if (pRes.status === 'fulfilled' && pRes.value?.data) setProjects(pRes.value.data);
        if (iRes.status === 'fulfilled' && iRes.value?.data) setInvoices(iRes.value.data);
        if (tRes.status === 'fulfilled' && tRes.value?.data) setTickets(tRes.value.data);
      } catch (err) {
        console.error('Error fetching client portal data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchClientData();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      
      <div className="glass-panel p-8 rounded-3xl border border-sky-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <span className="text-xs font-bold text-sky-400 uppercase tracking-widest">CLIENT PORTAL</span>
          <h1 className="text-3xl font-extrabold text-white">Acme Corporation Workspace</h1>
          <p className="text-xs text-slate-400">Welcome, {user?.name} · Track active software deliverables, project milestones, invoices, and support tickets.</p>
        </div>
        <div className="glass-card px-4 py-2 rounded-xl text-xs text-sky-400 font-semibold border border-sky-500/30">
          Account Manager: Assigned
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-card p-6 rounded-2xl space-y-2">
          <Briefcase className="w-6 h-6 text-sky-400" />
          <div className="text-2xl font-bold text-white">{projects.length || 1}</div>
          <div className="text-xs text-slate-400 font-medium">Active Software Projects</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <CreditCard className="w-6 h-6 text-emerald-400" />
          <div className="text-2xl font-bold text-white">{invoices.length || 2}</div>
          <div className="text-xs text-slate-400 font-medium">Issued Invoices</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <Headphones className="w-6 h-6 text-indigo-400" />
          <div className="text-2xl font-bold text-white">{tickets.length || 1}</div>
          <div className="text-xs text-slate-400 font-medium">Active Support Requests</div>
        </div>
      </div>

      {/* Projects Overview */}
      <div className="glass-panel p-6 rounded-3xl border border-slate-800 space-y-4">
        <h2 className="text-lg font-bold text-white">Project Deliverables & Progress</h2>
        <div className="space-y-4">
          {projects.slice(0, 3).map((p, idx) => (
            <div key={idx} className="glass-card p-6 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white">{p.title}</h3>
                <span className="text-xs px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 font-semibold">
                  {p.status || 'In Progress'}
                </span>
              </div>
              <p className="text-xs text-slate-300">{p.overview}</p>
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-slate-400">
                  <span>Milestone Completion</span>
                  <span>{p.progress_percent || 75}%</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                  <div className="bg-gradient-to-r from-sky-400 to-indigo-500 h-2 rounded-full" style={{ width: `${p.progress_percent || 75}%` }}></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
