import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { 
  Building2, 
  ShieldCheck, 
  User, 
  LogOut, 
  Menu, 
  X, 
  LayoutDashboard, 
  Sparkles,
  ChevronDown
} from 'lucide-react';

export const Navbar = ({ currentTab, setCurrentTab }) => {
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const navLinks = [
    { id: 'home', label: 'Home' },
    { id: 'services', label: 'Services' },
    { id: 'products', label: 'Products' },
    { id: 'about', label: 'About Us' },
    { id: 'careers', label: 'Careers' },
    { id: 'contact', label: 'Contact' },
  ];

  const getPortalLabel = (role) => {
    switch (role) {
      case 'super_admin': return 'Super Admin Portal';
      case 'admin': return 'Admin Panel';
      case 'client': return 'Client Portal';
      case 'partner': return 'Partner Portal';
      default: return 'Employee Portal';
    }
  };

  const getPortalTabId = (role) => {
    switch (role) {
      case 'super_admin': return 'superadmin-portal';
      case 'admin': return 'admin-portal';
      case 'client': return 'client-portal';
      case 'partner': return 'partner-portal';
      default: return 'employee-portal';
    }
  };

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          
          {/* Logo & Brand */}
          <div 
            className="flex items-center space-x-3 cursor-pointer group"
            onClick={() => setCurrentTab('home')}
          >
            <div className="w-10 h-10 rounded-xl gradient-button flex items-center justify-center shadow-lg shadow-sky-500/20 group-hover:scale-105 transition-transform">
              <Building2 className="w-6 h-6 text-white" />
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight text-white flex items-center gap-1.5">
                VPD <span className="gradient-text font-extrabold">Technologies</span>
              </span>
              <span className="block text-[10px] tracking-wider text-sky-400 font-semibold uppercase">
                Enterprise Intelligent Solutions
              </span>
            </div>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-1">
            {navLinks.map((link) => (
              <button
                key={link.id}
                onClick={() => setCurrentTab(link.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  currentTab === link.id
                    ? 'text-sky-400 bg-sky-500/10 border border-sky-500/20 shadow-sm'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/50'
                }`}
              >
                {link.label}
              </button>
            ))}
          </nav>

          {/* Right Action / Auth Buttons */}
          <div className="hidden md:flex items-center space-x-4">
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center space-x-3 px-3 py-1.5 rounded-xl glass-card border border-slate-700/60 hover:border-sky-500/50 transition-all"
                >
                  <div className="w-8 h-8 rounded-lg bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold text-sm border border-sky-500/30">
                    {user.name ? user.name[0].toUpperCase() : 'U'}
                  </div>
                  <div className="text-left">
                    <p className="text-xs font-semibold text-white leading-tight">{user.name}</p>
                    <p className="text-[10px] text-sky-400 font-medium capitalize">{user.role?.replace('_', ' ')}</p>
                  </div>
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                </button>

                {/* Dropdown Menu */}
                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 glass-panel rounded-2xl shadow-2xl py-2 border border-slate-700/80 z-50 animate-in fade-in slide-in-from-top-2">
                    <div className="px-4 py-2 border-b border-slate-800">
                      <p className="text-xs text-slate-400">Signed in as</p>
                      <p className="text-xs font-semibold text-white truncate">{user.email}</p>
                    </div>

                    <button
                      onClick={() => {
                        setCurrentTab(getPortalTabId(user.role));
                        setUserMenuOpen(false);
                      }}
                      className="w-full text-left px-4 py-2.5 text-sm text-sky-400 hover:bg-sky-500/10 flex items-center space-x-2 font-medium"
                    >
                      <LayoutDashboard className="w-4 h-4" />
                      <span>{getPortalLabel(user.role)}</span>
                    </button>

                    <button
                      onClick={() => {
                        logout();
                        setUserMenuOpen(false);
                        setCurrentTab('home');
                      }}
                      className="w-full text-left px-4 py-2.5 text-sm text-rose-400 hover:bg-rose-500/10 flex items-center space-x-2 font-medium"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setCurrentTab('login')}
                  className="px-5 py-2.5 text-sm font-semibold rounded-xl text-white gradient-button flex items-center space-x-2 shadow-lg shadow-sky-500/20"
                >
                  <User className="w-4 h-4" />
                  <span>Sign In / Portals</span>
                </button>
              </div>
            )}
          </div>

          {/* Mobile menu trigger */}
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden glass-panel border-b border-slate-800 px-4 pt-2 pb-4 space-y-1">
          {navLinks.map((link) => (
            <button
              key={link.id}
              onClick={() => {
                setCurrentTab(link.id);
                setMobileMenuOpen(false);
              }}
              className={`w-full text-left px-4 py-2.5 rounded-lg text-base font-medium ${
                currentTab === link.id
                  ? 'text-sky-400 bg-sky-500/10 border border-sky-500/20'
                  : 'text-slate-300 hover:bg-slate-800'
              }`}
            >
              {link.label}
            </button>
          ))}
          {user ? (
            <div className="pt-2 border-t border-slate-800 space-y-1">
              <button
                onClick={() => {
                  setCurrentTab(getPortalTabId(user.role));
                  setMobileMenuOpen(false);
                }}
                className="w-full text-left px-4 py-2.5 rounded-lg text-sm text-sky-400 bg-sky-500/10 font-semibold"
              >
                Go to {getPortalLabel(user.role)}
              </button>
              <button
                onClick={() => {
                  logout();
                  setMobileMenuOpen(false);
                  setCurrentTab('home');
                }}
                className="w-full text-left px-4 py-2.5 rounded-lg text-sm text-rose-400 hover:bg-rose-500/10 font-medium"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <button
              onClick={() => {
                setCurrentTab('login');
                setMobileMenuOpen(false);
              }}
              className="w-full mt-2 py-3 rounded-xl gradient-button text-white text-sm font-semibold"
            >
              Sign In to Portal
            </button>
          )}
        </div>
      )}
    </header>
  );
};
