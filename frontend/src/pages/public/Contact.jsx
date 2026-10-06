import React, { useState } from 'react';
import api from '../../api/client';
import { Mail, Phone, MapPin, Send, CheckCircle2, AlertCircle } from 'lucide-react';

export const Contact = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [phone, setPhone] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await api.post('/contact', {
        contact_name: name,
        email: email,
        company: company,
        phone: phone,
        notes: notes,
      });
      setSubmitted(true);
    } catch (err) {
      setError(err.message || 'Failed sending contact inquiry.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left Column */}
        <div className="lg:col-span-5 space-y-6">
          <div>
            <h1 className="text-3xl font-extrabold text-white">Get in Touch</h1>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Have a question about our enterprise software suites, cloud migrations, or cybersecurity solutions? Speak directly with our engineering leadership.
            </p>
          </div>

          <div className="space-y-4">
            <div className="glass-card p-4 rounded-xl flex items-start space-x-3">
              <MapPin className="w-5 h-5 text-sky-400 mt-0.5 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-white">Global Head Office</h4>
                <p className="text-[11px] text-slate-400">Connaught Place, New Delhi 110001, India</p>
              </div>
            </div>

            <div className="glass-card p-4 rounded-xl flex items-center space-x-3">
              <Mail className="w-5 h-5 text-sky-400 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-white">Email Us</h4>
                <p className="text-[11px] text-slate-400">contact@vpdtechnologies.com</p>
              </div>
            </div>

            <div className="glass-card p-4 rounded-xl flex items-center space-x-3">
              <Phone className="w-5 h-5 text-sky-400 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-white">Call Us</h4>
                <p className="text-[11px] text-slate-400">+91 (011) 4567-8900</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Form */}
        <div className="lg:col-span-7">
          <div className="glass-panel p-8 rounded-3xl border border-slate-800 space-y-6">
            <h2 className="text-xl font-bold text-white">Request Enterprise Proposal / Demo</h2>

            {submitted ? (
              <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-center space-y-2">
                <CheckCircle2 className="w-10 h-10 mx-auto" />
                <h3 className="text-base font-bold">Inquiry Submitted Successfully!</h3>
                <p className="text-xs text-slate-300">Our solutions engineering team will respond within one business day.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center space-x-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-300">Your Full Name</label>
                    <input
                      type="text"
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Jane Doe"
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:border-sky-500"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-300">Work Email</label>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="jane@company.com"
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:border-sky-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-300">Company Name</label>
                    <input
                      type="text"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      placeholder="Acme Corp"
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:border-sky-500"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-300">Phone Number</label>
                    <input
                      type="text"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="+1 (555) 000-0000"
                      className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:border-sky-500"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Project Requirements / Notes</label>
                  <textarea
                    rows={4}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Tell us about your project timeline, requirements, or desired scope..."
                    className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-white text-xs focus:outline-none focus:border-sky-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-xl gradient-button text-white font-bold text-xs shadow-lg shadow-sky-500/20 flex items-center justify-center space-x-2"
                >
                  {loading ? (
                    <span>Submitting...</span>
                  ) : (
                    <>
                      <span>Submit Inquiry</span>
                      <Send className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
