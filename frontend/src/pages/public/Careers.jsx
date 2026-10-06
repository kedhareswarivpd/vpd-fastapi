import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import { Briefcase, MapPin, Clock, ArrowRight, CheckCircle2 } from 'lucide-react';

export const Careers = () => {
  const [careers, setCareers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCareers = async () => {
      try {
        const res = await api.get('/careers');
        if (res?.data) setCareers(res.data);
      } catch (err) {
        console.error('Error loading careers', err);
      } finally {
        setLoading(false);
      }
    };
    fetchCareers();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-12 space-y-12">
      <div className="text-center max-w-3xl mx-auto space-y-4">
        <h1 className="text-4xl font-extrabold text-white">Join <span className="gradient-text">VPD Technologies</span></h1>
        <p className="text-sm text-slate-300 leading-relaxed">
          We are building the future of enterprise software. Explore open roles across engineering, design, product management, and business operations.
        </p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading open positions...</div>
      ) : (
        <div className="space-y-4 max-w-4xl mx-auto">
          {careers.map((c, idx) => (
            <div key={idx} className="glass-card p-6 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 border border-slate-800">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <h3 className="text-lg font-bold text-white">{c.title}</h3>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-sky-500/10 text-sky-400 font-semibold border border-sky-500/20">
                    {c.department}
                  </span>
                </div>
                <div className="flex items-center space-x-4 text-xs text-slate-400 pt-1">
                  <div className="flex items-center space-x-1">
                    <MapPin className="w-3.5 h-3.5 text-slate-500" />
                    <span>{c.location}</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    <span className="capitalize">{c.employment_type?.replace('_', ' ')}</span>
                  </div>
                  <span>Exp: {c.experience_required || 'Relevant'}</span>
                </div>
              </div>

              <button
                onClick={() => alert(`Application form for ${c.title} initialized.`)}
                className="px-5 py-2.5 rounded-xl gradient-button text-white text-xs font-semibold flex items-center space-x-2 shrink-0"
              >
                <span>Apply Position</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
