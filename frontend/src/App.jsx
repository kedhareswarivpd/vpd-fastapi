import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/layout/Navbar';
import { Footer } from './components/layout/Footer';

// Public pages
import { Home } from './pages/public/Home';
import { Services } from './pages/public/Services';
import { Products } from './pages/public/Products';
import { About } from './pages/public/About';
import { Careers } from './pages/public/Careers';
import { Contact } from './pages/public/Contact';
import { LoginPage } from './pages/public/LoginPage';

// Portal pages
import { SuperAdminPortal } from './pages/portals/SuperAdminPortal';
import { AdminPortal } from './pages/portals/AdminPortal';
import { EmployeePortal } from './pages/portals/EmployeePortal';
import { ClientPortal } from './pages/portals/ClientPortal';
import { PartnerPortal } from './pages/portals/PartnerPortal';

const AppContent = () => {
  const [currentTab, setCurrentTab] = useState('home');
  const { user } = useAuth();

  const renderContent = () => {
    switch (currentTab) {
      case 'home':
        return <Home setCurrentTab={setCurrentTab} />;
      case 'services':
        return <Services setCurrentTab={setCurrentTab} />;
      case 'products':
        return <Products setCurrentTab={setCurrentTab} />;
      case 'about':
        return <About />;
      case 'careers':
        return <Careers />;
      case 'contact':
        return <Contact />;
      case 'login':
        return <LoginPage setCurrentTab={setCurrentTab} />;

      // Portals
      case 'superadmin-portal':
        return <SuperAdminPortal />;
      case 'admin-portal':
        return <AdminPortal />;
      case 'employee-portal':
        return <EmployeePortal />;
      case 'client-portal':
        return <ClientPortal />;
      case 'partner-portal':
        return <PartnerPortal />;

      default:
        return <Home setCurrentTab={setCurrentTab} />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#0b0f19] text-slate-100 font-sans selection:bg-sky-500 selection:text-white">
      <Navbar currentTab={currentTab} setCurrentTab={setCurrentTab} />
      <main className="flex-1">
        {renderContent()}
      </main>
      <Footer setCurrentTab={setCurrentTab} />
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
