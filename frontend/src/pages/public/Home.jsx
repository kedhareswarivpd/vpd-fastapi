import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import { 
  Building2, 
  ArrowRight, 
  Sparkles, 
  ShieldCheck, 
  Cpu, 
  Cloud, 
  Users, 
  Award, 
  CheckCircle2, 
  Star,
  ChevronRight,
  TrendingUp,
  BarChart3,
  Layers
} from 'lucide-react';

export const Home = ({ setCurrentTab }) => {
  const [stats, setStats] = useState(null);
  const [services, setServices] = useState([]);
  const [products, setProducts] = useState([]);
  const [testimonials, setTestimonials] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const statsRes = await api.get('/stats');
        if (statsRes?.data) setStats(statsRes.data);

        const servicesRes = await api.get('/services');
        if (servicesRes?.data) setServices(servicesRes.data.slice(0, 4));

        const productsRes = await api.get('/products');
        if (productsRes?.data) setProducts(productsRes.data);

        const testimonialsRes = await api.get('/testimonials');
        if (testimonialsRes?.data) setTestimonials(testimonialsRes.data.slice(0, 3));
      } catch (err) {
        console.error('Failed loading home data', err);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="space-y-20 pb-16">
      
      {/* Hero Section */}
      <section className="relative pt-12 pb-20 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-sky-900/20 via-slate-900/0 to-slate-950 pointer-events-none" />
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="text-center max-w-3xl mx-auto space-y-6">
            
            <div className="inline-flex items-center space-x-2 px-4 py-2 rounded-full glass-panel border border-sky-500/30 text-sky-400 text-xs font-semibold tracking-wide">
              <Sparkles className="w-4 h-4 animate-pulse" />
              <span>Next-Gen Enterprise Digital Transformation</span>
            </div>

            <h1 className="text-4xl sm:text-6xl font-black text-white tracking-tight leading-tight">
              Transforming Businesses Through <span className="gradient-text">Intelligent Digital Solutions</span>
            </h1>

            <p className="text-lg text-slate-300 leading-relaxed">
              VPD Technologies delivers secure, cloud-native enterprise platforms, AI-driven automation, and full-spectrum engineering to Fortune 500 & fast-growing enterprises.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
              <button
                onClick={() => setCurrentTab('login')}
                className="w-full sm:w-auto px-8 py-4 rounded-xl text-white font-bold gradient-button shadow-xl shadow-sky-500/25 flex items-center justify-center space-x-3 text-base"
              >
                <span>Access Portals</span>
                <ArrowRight className="w-5 h-5" />
              </button>

              <button
                onClick={() => setCurrentTab('services')}
                className="w-full sm:w-auto px-8 py-4 rounded-xl text-slate-200 font-semibold glass-card border border-slate-700 hover:border-sky-500/50 flex items-center justify-center space-x-2 text-base"
              >
                <span>Explore Services</span>
              </button>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
            {[
              { label: 'Employees', value: stats?.employees || '285+', icon: Users, color: 'text-sky-400' },
              { label: 'Projects Delivered', value: stats?.projects || '430+', icon: Award, color: 'text-indigo-400' },
              { label: 'Enterprise Clients', value: stats?.clients || '120+', icon: Building2, color: 'text-purple-400' },
              { label: 'Countries Served', value: stats?.countries || '18+', icon: TrendingUp, color: 'text-emerald-400' },
            ].map((stat, idx) => (
              <div key={idx} className="glass-card p-6 rounded-2xl text-center space-y-2">
                <stat.icon className={`w-8 h-8 mx-auto ${stat.color} mb-1`} />
                <div className="text-3xl font-black text-white">{stat.value}</div>
                <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Flagship Products Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto space-y-3 mb-12">
          <h2 className="text-3xl font-extrabold text-white">Flagship Enterprise Products</h2>
          <p className="text-slate-400 text-sm">Built to streamline financial operations, customer relations, and operational analytics.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            {
              title: 'VPD Technologies ERP Suite',
              tagline: 'One platform for finance, inventory & HR',
              description: 'Multi-entity financial accounting, real-time inventory tracking, procurement workflows, and automated payroll.',
              features: ['Multi-entity finance', 'Real-time inventory', 'HR & Payroll automation'],
              icon: BarChart3,
              badge: 'ERP'
            },
            {
              title: 'VPD Technologies CRM Cloud',
              tagline: 'Sell smarter, support faster',
              description: 'Unified sales pipeline management, automated marketing campaigns, and omni-channel support ticketing.',
              features: ['Pipeline automation', 'Support ticketing', 'Customer analytics'],
              icon: Users,
              badge: 'CRM'
            },
            {
              title: 'Insight Analytics Platform',
              tagline: 'Turn operational data into decisions',
              description: 'Live executive dashboards, predictive forecasting models, and continuous SLA monitoring.',
              features: ['Predictive forecasting', 'Role-based analytics', 'Real-time alerts'],
              icon: Cpu,
              badge: 'BI'
            }
          ].map((prod, i) => (
            <div key={i} className="glass-card p-8 rounded-3xl space-y-6 flex flex-col justify-between border border-slate-800">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
                    <prod.icon className="w-6 h-6" />
                  </div>
                  <span className="text-xs font-bold px-3 py-1 rounded-full bg-slate-800 text-sky-400 border border-slate-700">
                    {prod.badge}
                  </span>
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">{prod.title}</h3>
                  <p className="text-xs font-semibold text-sky-400 mt-1">{prod.tagline}</p>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">{prod.description}</p>
                
                <ul className="space-y-2 pt-2">
                  {prod.features.map((feat, fIdx) => (
                    <li key={fIdx} className="flex items-center text-xs text-slate-300 space-x-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <button 
                onClick={() => setCurrentTab('products')}
                className="w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs transition-colors flex items-center justify-center space-x-2"
              >
                <span>View Catalogue Details</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Services Overview */}
      <section className="bg-slate-900/50 border-y border-slate-800/80 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 mb-12">
            <div>
              <h2 className="text-3xl font-extrabold text-white">Core Enterprise Capabilities</h2>
              <p className="text-slate-400 text-sm mt-1">End-to-end IT services customized for high-growth & legacy enterprises.</p>
            </div>
            <button
              onClick={() => setCurrentTab('services')}
              className="px-6 py-3 rounded-xl glass-card text-sky-400 font-semibold text-xs flex items-center space-x-2 hover:bg-sky-500/10 border border-sky-500/30"
            >
              <span>View All Services</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { title: 'Cloud Native & DevOps', icon: Cloud, desc: 'Containerization, Kubernetes, CI/CD pipeline automation & cloud migrations.' },
              { title: 'AI & Data Science', icon: Cpu, desc: 'Machine learning, predictive models & automated NLP business workflows.' },
              { title: 'Cybersecurity SOC', icon: ShieldCheck, desc: 'Zero trust security, compliance management (ISO 27001) & SOC monitoring.' },
              { title: 'Custom Software Dev', icon: Layers, desc: 'Full-stack enterprise portals, high-throughput microservices & APIs.' }
            ].map((srv, idx) => (
              <div key={idx} className="glass-card p-6 rounded-2xl space-y-3">
                <srv.icon className="w-8 h-8 text-sky-400 mb-2" />
                <h3 className="text-base font-bold text-white">{srv.title}</h3>
                <p className="text-xs text-slate-400 leading-relaxed">{srv.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      {testimonials.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto space-y-3 mb-12">
            <h2 className="text-3xl font-extrabold text-white">Client Success Stories</h2>
            <p className="text-slate-400 text-sm">See how leading companies transform operations with VPD Technologies.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {testimonials.map((t, idx) => (
              <div key={idx} className="glass-card p-6 rounded-2xl space-y-4 flex flex-col justify-between">
                <div className="space-y-3">
                  <div className="flex space-x-1 text-amber-400">
                    {[...Array(t.rating || 5)].map((_, i) => (
                      <Star key={i} className="w-4 h-4 fill-amber-400" />
                    ))}
                  </div>
                  <p className="text-xs text-slate-300 italic leading-relaxed">"{t.content}"</p>
                </div>
                <div className="pt-4 border-t border-slate-800 flex items-center space-x-3">
                  <div className="w-9 h-9 rounded-full bg-sky-500/20 text-sky-400 font-bold flex items-center justify-center text-xs">
                    {t.author_name ? t.author_name[0] : 'C'}
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-white">{t.author_name}</h4>
                    <p className="text-[10px] text-slate-400">{t.author_title} · {t.company_name}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Bottom CTA Banner */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="glass-panel p-10 sm:p-14 rounded-3xl relative overflow-hidden border border-sky-500/30 text-center space-y-6">
          <div className="max-w-2xl mx-auto space-y-4">
            <h2 className="text-3xl font-extrabold text-white">Ready to Modernize Your Enterprise?</h2>
            <p className="text-sm text-slate-300 leading-relaxed">
              Contact our solutions engineering team today for a custom evaluation, demo, or proposal.
            </p>
            <div className="pt-2 flex justify-center gap-4">
              <button
                onClick={() => setCurrentTab('contact')}
                className="px-8 py-3.5 rounded-xl gradient-button text-white font-bold text-sm shadow-xl shadow-sky-500/30"
              >
                Request Proposal
              </button>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
};
