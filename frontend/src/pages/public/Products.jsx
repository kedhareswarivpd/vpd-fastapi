import React from 'react';
import { BarChart3, Users, Cpu, CheckCircle2, ArrowRight } from 'lucide-react';

export const Products = ({ setCurrentTab }) => {
  const products = [
    {
      id: 'erp',
      title: 'VPD Technologies ERP Suite',
      tagline: 'Modular Enterprise Resource Planning Platform',
      overview: 'Covering multi-entity finance accounting, automated inventory tracking, vendor procurement workflows, and full HR payroll calculation.',
      modules: ['Financial Accounting', 'Inventory & Warehouse Management', 'Procurement & Purchase Orders', 'HR & Automated Payroll'],
      stack: ['Python', 'PostgreSQL', 'React', 'FastAPI'],
      badge: 'Flagship ERP'
    },
    {
      id: 'crm',
      title: 'VPD Technologies CRM Cloud',
      tagline: 'Unified Sales Pipeline & Support Workspace',
      overview: 'Automates B2B sales pipeline management, targeted marketing campaign workflows, and omni-channel customer support ticketing.',
      modules: ['Sales Pipeline Automation', 'Omni-channel Support Tickets', 'Marketing Campaign Manager', 'Customer 360 Analytics'],
      stack: ['FastAPI', 'PostgreSQL', 'Redis', 'React'],
      badge: 'CRM Platform'
    },
    {
      id: 'bi',
      title: 'Insight Analytics Platform',
      tagline: 'Real-time Business Intelligence & Forecasting',
      overview: 'Transforms live operational data into interactive executive dashboards, anomaly alerts, and predictive business forecasts.',
      modules: ['Live Executive Dashboards', 'Predictive Forecasting Models', 'Custom KPI Alerts', 'Role-Based Access Control'],
      stack: ['Python', 'TensorFlow', 'PostgreSQL', 'React'],
      badge: 'BI & AI'
    }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-12 space-y-12">
      <div className="text-center max-w-3xl mx-auto space-y-4">
        <h1 className="text-4xl font-extrabold text-white">VPD Technologies <span className="gradient-text">Product Catalogue</span></h1>
        <p className="text-sm text-slate-300 leading-relaxed">
          Modular, cloud-ready software suites engineered for enterprise reliability, performance, and seamless backend integration.
        </p>
      </div>

      <div className="space-y-8">
        {products.map((p, idx) => (
          <div key={idx} className="glass-panel p-8 sm:p-10 rounded-3xl border border-slate-800 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
              <div>
                <span className="text-xs font-bold text-sky-400 uppercase tracking-wider">{p.badge}</span>
                <h2 className="text-2xl font-bold text-white mt-1">{p.title}</h2>
                <p className="text-xs text-slate-400 font-medium">{p.tagline}</p>
              </div>
              <button
                onClick={() => setCurrentTab('contact')}
                className="px-6 py-3 rounded-xl gradient-button text-white font-semibold text-xs flex items-center space-x-2 shrink-0"
              >
                <span>Request Product Demo</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed">{p.overview}</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">Core Functional Modules</h3>
                <ul className="space-y-2">
                  {p.modules.map((m, mIdx) => (
                    <li key={mIdx} className="flex items-center space-x-2 text-xs text-slate-300">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>{m}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="space-y-3">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">Technology Stack</h3>
                <div className="flex flex-wrap gap-2">
                  {p.stack.map((tech, tIdx) => (
                    <span key={tIdx} className="px-3 py-1.5 rounded-lg bg-slate-800 text-sky-400 text-xs font-mono border border-slate-700">
                      {tech}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
