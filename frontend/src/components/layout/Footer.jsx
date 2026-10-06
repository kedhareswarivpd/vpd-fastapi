import React from 'react';
import { Building2, Mail, Phone, MapPin, Globe, Shield, ExternalLink } from 'lucide-react';

export const Footer = ({ setCurrentTab }) => {
  return (
    <footer className="bg-slate-950 border-t border-slate-800/80 text-slate-400 text-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          
          {/* Col 1: Brand & Tagline */}
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl gradient-button flex items-center justify-center shadow-lg shadow-sky-500/20">
                <Building2 className="w-6 h-6 text-white" />
              </div>
              <span className="text-xl font-bold text-white tracking-tight">
                VPD <span className="gradient-text">Technologies</span>
              </span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Transforming businesses through intelligent enterprise digital solutions, cloud native platforms, and security-first engineering.
            </p>
            <div className="flex items-center space-x-3 text-xs text-sky-400 font-medium">
              <Shield className="w-4 h-4" />
              <span>ISO 9001 & ISO 27001 Certified Enterprise</span>
            </div>
          </div>

          {/* Col 2: Quick Links */}
          <div>
            <h3 className="text-white font-semibold mb-4 text-base">Quick Links</h3>
            <ul className="space-y-2.5">
              {['home', 'services', 'products', 'about', 'careers', 'contact'].map((link) => (
                <li key={link}>
                  <button
                    onClick={() => setCurrentTab(link)}
                    className="hover:text-sky-400 transition-colors capitalize text-xs"
                  >
                    {link === 'home' ? 'Home' : link}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Col 3: Enterprise Solutions */}
          <div>
            <h3 className="text-white font-semibold mb-4 text-base">Flagship Products</h3>
            <ul className="space-y-2.5 text-xs">
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
                <span>VPD Technologies ERP Suite</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
                <span>VPD Technologies CRM Cloud</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
                <span>Insight Analytics Platform</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span>Cybersecurity SOC Framework</span>
              </li>
            </ul>
          </div>

          {/* Col 4: Contact & Locations */}
          <div className="space-y-3 text-xs">
            <h3 className="text-white font-semibold mb-4 text-base">Global Head Office</h3>
            <div className="flex items-start space-x-2.5">
              <MapPin className="w-4 h-4 text-sky-400 mt-0.5 shrink-0" />
              <span>Connaught Place, New Delhi 110001, India</span>
            </div>
            <div className="flex items-center space-x-2.5">
              <Mail className="w-4 h-4 text-sky-400 shrink-0" />
              <span>contact@vpdtechnologies.com</span>
            </div>
            <div className="flex items-center space-x-2.5">
              <Phone className="w-4 h-4 text-sky-400 shrink-0" />
              <span>+91 (011) 4567-8900</span>
            </div>
            <div className="flex items-center space-x-2.5">
              <Globe className="w-4 h-4 text-sky-400 shrink-0" />
              <span>Offices: Delhi, Bangalore, Dubai, Singapore</span>
            </div>
          </div>
        </div>

        <div className="mt-12 pt-6 border-t border-slate-900 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500">
          <p>© {new Date().getFullYear()} VPD Technologies Private Limited. All rights reserved.</p>
          <div className="flex space-x-6 mt-4 sm:mt-0">
            <span className="hover:text-slate-400 cursor-pointer">Privacy Policy</span>
            <span className="hover:text-slate-400 cursor-pointer">Terms of Service</span>
            <span className="hover:text-slate-400 cursor-pointer">Security Portal</span>
          </div>
        </div>
      </div>
    </footer>
  );
};
