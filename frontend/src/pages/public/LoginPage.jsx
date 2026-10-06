import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { 
  Building2, 
  Lock, 
  Mail, 
  ArrowRight, 
  ShieldCheck, 
  CheckCircle2, 
  AlertCircle,
  KeyRound,
  UserCheck
} from 'lucide-react';

export const LoginPage = ({ setCurrentTab }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const demoAccounts = [
    { role: 'Super Admin', email: 'superadmin@vpdtechnologies.com', pass: 'Password123!', badge: 'System Executive', portal: 'superadmin-portal' },
    { role: 'System Admin', email: 'admin@vpdtechnologies.com', pass: 'Password123!', badge: 'Admin Panel', portal: 'admin-portal' },
    { role: 'HR Manager', email: 'hr@vpdtechnologies.com', pass: 'Password123!', badge: 'HR Operations', portal: 'employee-portal' },
    { role: 'Sales Lead', email: 'sales@vpdtechnologies.com', pass: 'Password123!', badge: 'CRM Pipeline', portal: 'employee-portal' },
    { role: 'Project Manager', email: 'pm@vpdtechnologies.com', pass: 'Password123!', badge: 'Projects & Tasks', portal: 'employee-portal' },
    { role: 'Dev Lead', email: 'developer@vpdtechnologies.com', pass: 'Password123!', badge: 'Engineering', portal: 'employee-portal' },
    { role: 'Finance Lead', email: 'finance@vpdtechnologies.com', pass: 'Password123!', badge: 'Invoices & Tax', portal: 'employee-portal' },
    { role: 'Client Portal', email: 'client@acmecorp.com', pass: 'Password123!', badge: 'Acme Corp', portal: 'client-portal' },
    { role: 'Partner Portal', email: 'partner@techpartner.com', pass: 'Password123!', badge: 'TechPartner Global', portal: 'partner-portal' },
  ];

  const handleFillCreds = (item) => {
    setEmail(item.email);
    setPassword(item.pass);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccessMsg('');

    try {
      const res = await login(email, password);
      const user = res?.data?.user;
      setSuccessMsg('Authentication successful! Loading portal...');
      
      setTimeout(() => {
        if (user) {
          switch (user.role) {
            case 'super_admin':
              setCurrentTab('superadmin-portal');
              break;
            case 'admin':
              setCurrentTab('admin-portal');
              break;
            case 'client':
              setCurrentTab('client-portal');
              break;
            case 'partner':
              setCurrentTab('partner-portal');
              break;
            default:
              setCurrentTab('employee-portal');
              break;
          }
        } else {
          setCurrentTab('employee-portal');
        }
      }, 600);
    } catch (err) {
      setError(err.message || 'Invalid email or password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left Col: Demo Credentials Helper */}
        <div className="lg:col-span-5 space-y-6">
          <div className="glass-panel p-6 rounded-3xl border border-sky-500/20 space-y-4">
            <div className="flex items-center space-x-2 text-sky-400 font-bold text-sm">
              <UserCheck className="w-5 h-5" />
              <span>Quick Demo Login Selector</span>
            </div>
            <p className="text-xs text-slate-400">
              Select any role below to automatically fill the credentials and sign in to that portal.
            </p>

            <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
              {demoAccounts.map((acc, idx) => (
                <div
                  key={idx}
                  onClick={() => handleFillCreds(acc)}
                  className="glass-card p-3 rounded-xl cursor-pointer hover:border-sky-500/50 flex items-center justify-between transition-all"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-white">{acc.role}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-800 text-sky-400 font-medium">
                        {acc.badge}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 font-mono">{acc.email}</p>
                  </div>
                  <span className="text-xs text-sky-400 font-semibold hover:underline">Autofill</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Col: Login Form */}
        <div className="lg:col-span-7">
          <div className="glass-panel p-8 sm:p-10 rounded-3xl border border-slate-800 space-y-6 shadow-2xl">
            
            <div className="space-y-2 text-center sm:text-left">
              <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-sky-500/10 text-sky-400 text-xs font-semibold border border-sky-500/20 mb-1">
                <ShieldCheck className="w-4 h-4" />
                <span>Secure Enterprise Authentication</span>
              </div>
              <h1 className="text-3xl font-bold text-white">Sign In to VPD Technologies Portal</h1>
              <p className="text-xs text-slate-400">Access your role-based dashboard, client projects, or admin control panel.</p>
            </div>

            {error && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center space-x-3">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {successMsg && (
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center space-x-3">
                <CheckCircle2 className="w-5 h-5 shrink-0" />
                <span>{successMsg}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Work Email Address</label>
                <div className="relative">
                  <Mail className="w-5 h-5 text-slate-500 absolute left-3.5 top-3" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@vpdtechnologies.com"
                    className="w-full pl-11 pr-4 py-2.5 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-sm focus:outline-none focus:border-sky-500 transition-colors"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-300">Password</label>
                  <span className="text-[11px] text-sky-400 cursor-pointer hover:underline">Forgot password?</span>
                </div>
                <div className="relative">
                  <Lock className="w-5 h-5 text-slate-500 absolute left-3.5 top-3" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full pl-11 pr-4 py-2.5 rounded-xl bg-slate-900/90 border border-slate-700 text-white text-sm focus:outline-none focus:border-sky-500 transition-colors"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 rounded-xl gradient-button text-white font-bold text-sm shadow-xl shadow-sky-500/20 flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                {loading ? (
                  <span>Authenticating...</span>
                ) : (
                  <>
                    <span>Sign In to Dashboard</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

            </form>

            <div className="pt-4 border-t border-slate-800 text-center text-xs text-slate-500">
              Need assistance? Contact support at <span className="text-sky-400 font-medium">support@vpdtechnologies.com</span>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
};
