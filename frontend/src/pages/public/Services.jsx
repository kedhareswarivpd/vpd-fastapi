import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import { Cloud, Cpu, ShieldCheck, Layers, ArrowRight, CheckCircle, Sparkles } from 'lucide-react';

export const Services = ({ setCurrentTab }) => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchServices = async () => {
      try {
        const res = await api.get('/services');
        if (res?.data) setServices(res.data);
      } catch (err) {
        console.error('Error fetching services', err);
      } finally {
        setLoading(false);
      }
    };
    fetchServices();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-12 space-y-12">
      <div className="text-center max-w-3xl mx-auto space-y-4">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-sky-500/10 text-sky-400 text-xs font-semibold border border-sky-500/20">
          <Sparkles className="w-4 h-4" />
          <span>Enterprise Services & Solutions</span>
        </div>
        <h1 className="text-4xl font-extrabold text-white">Full-Spectrum IT & Software Engineering Services</h1>
        <p className="text-sm text-slate-300 leading-relaxed">
          From cloud-native migrations to AI pipeline automation and ISO 27001 compliant SOC infrastructure, VPD Technologies powers enterprise digital evolution.
        </p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading service catalogue...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {services.map((srv, idx) => (
            <div key={idx} className="glass-card p-8 rounded-3xl space-y-6 flex flex-col justify-between border border-slate-800">
              <div className="space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-sky-500/10 text-sky-400 flex items-center justify-center font-bold">
                  <Cloud className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">{srv.name}</h3>
                  <p className="text-xs text-sky-400 font-medium mt-1">{srv.overview}</p>
                </div>
                {srv.features && (
                  <ul className="space-y-2 pt-2">
                    {srv.features.slice(0, 4).map((f, i) => (
                      <li key={i} className="flex items-center space-x-2 text-xs text-slate-300">
                        <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <button
                onClick={() => setCurrentTab('contact')}
                className="w-full py-3 rounded-xl gradient-button text-white font-semibold text-xs flex items-center justify-center space-x-2 shadow-lg shadow-sky-500/10"
              >
                <span>Request Engagement Proposal</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
