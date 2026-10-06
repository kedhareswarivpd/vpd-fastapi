import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { Handshake, FileText, Headphones, TrendingUp, Award, Download } from 'lucide-react';

export const PartnerPortal = () => {
  const { user } = useAuth();
  const [tickets, setTickets] = useState([]);
  const [downloads, setDownloads] = useState([]);

  useEffect(() => {
    const fetchPartnerData = async () => {
      try {
        const [tRes, dRes] = await Promise.allSettled([
          api.get('/tickets'),
          api.get('/downloads')
        ]);
        if (tRes.status === 'fulfilled' && tRes.value?.data) setTickets(tRes.value.data);
        if (dRes.status === 'fulfilled' && dRes.value?.data) setDownloads(dRes.value.data);
      } catch (err) {
        console.error('Partner portal error', err);
      }
    };
    fetchPartnerData();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      
      <div className="glass-panel p-8 rounded-3xl border border-sky-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <span className="text-xs font-bold text-sky-400 uppercase tracking-widest">PARTNER NETWORK PORTAL</span>
          <h1 className="text-3xl font-extrabold text-white">TechPartner Global Hub</h1>
          <p className="text-xs text-slate-400">Welcome, {user?.name} · Partner account status, joint delivery tickets, and co-marketing resources.</p>
        </div>
        <div className="glass-card px-4 py-2 rounded-xl text-xs text-emerald-400 font-semibold border border-emerald-500/30">
          Status: Certified Strategic Partner
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-card p-6 rounded-2xl space-y-2">
          <Handshake className="w-6 h-6 text-sky-400" />
          <div className="text-2xl font-bold text-white">Active</div>
          <div className="text-xs text-slate-400 font-medium">Partner Agreement Status</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <Headphones className="w-6 h-6 text-indigo-400" />
          <div className="text-2xl font-bold text-white">{tickets.length || 1}</div>
          <div className="text-xs text-slate-400 font-medium">Shared Service Tickets</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <Download className="w-6 h-6 text-purple-400" />
          <div className="text-2xl font-bold text-white">{downloads.length || 5}</div>
          <div className="text-xs text-slate-400 font-medium">Partner Collateral & Downloads</div>
        </div>
      </div>

      <div className="glass-panel p-6 rounded-3xl border border-slate-800 space-y-4">
        <h2 className="text-lg font-bold text-white">Partner Downloads & Technical Whitepapers</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {downloads.slice(0, 4).map((d, i) => (
            <div key={i} className="glass-card p-4 rounded-xl flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-white">{d.title}</h4>
                <p className="text-[11px] text-slate-400">{d.category || 'Documentation'}</p>
              </div>
              <button className="px-3 py-1.5 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 text-xs font-medium flex items-center space-x-1">
                <Download className="w-3.5 h-3.5" />
                <span>PDF</span>
              </button>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
