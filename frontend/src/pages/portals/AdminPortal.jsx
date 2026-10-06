import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { 
  Users, 
  Settings, 
  FileText, 
  Plus, 
  Edit3, 
  Trash2, 
  CheckCircle, 
  Search,
  SlidersHorizontal
} from 'lucide-react';

export const AdminPortal = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('users');
  const [users, setUsers] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [uRes, sRes] = await Promise.allSettled([
          api.get('/users'),
          api.get('/services')
        ]);
        if (uRes.status === 'fulfilled' && uRes.value?.data) setUsers(uRes.value.data);
        if (sRes.status === 'fulfilled' && sRes.value?.data) setServices(sRes.value.data);
      } catch (err) {
        console.error('Admin portal data fetch error', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      
      <div className="glass-panel p-8 rounded-3xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-white">System Administration Panel</h1>
          <p className="text-xs text-slate-400 mt-1">Logged in as {user?.name} ({user?.email}) · Management of users, roles, and CMS content.</p>
        </div>

        <div className="flex space-x-2 bg-slate-900 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('users')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'users' ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/20' : 'text-slate-400 hover:text-white'
            }`}
          >
            User Directory
          </button>
          <button
            onClick={() => setActiveTab('cms')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'cms' ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/20' : 'text-slate-400 hover:text-white'
            }`}
          >
            CMS Content & Services
          </button>
        </div>
      </div>

      {activeTab === 'users' ? (
        <div className="glass-panel p-6 rounded-3xl border border-slate-800 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <h2 className="text-lg font-bold text-white">User Accounts ({users.length})</h2>
            <button className="px-4 py-2 rounded-xl gradient-button text-white text-xs font-bold flex items-center space-x-2">
              <Plus className="w-4 h-4" />
              <span>Create User Account</span>
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px]">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-slate-300">
                {users.map((u, i) => (
                  <tr key={i} className="hover:bg-slate-800/40">
                    <td className="px-4 py-3 font-semibold text-white">{u.name}</td>
                    <td className="px-4 py-3 font-mono text-slate-400">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-sky-400 font-medium capitalize">
                        {u.role?.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium">
                        Active
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button className="text-slate-400 hover:text-sky-400"><Edit3 className="w-4 h-4 inline" /></button>
                      <button className="text-slate-400 hover:text-rose-400"><Trash2 className="w-4 h-4 inline" /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="glass-panel p-6 rounded-3xl border border-slate-800 space-y-4">
          <h2 className="text-lg font-bold text-white">Public Services Catalogue ({services.length})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {services.map((s, idx) => (
              <div key={idx} className="glass-card p-4 rounded-xl space-y-2">
                <h3 className="text-sm font-bold text-white">{s.name}</h3>
                <p className="text-xs text-slate-400">{s.overview}</p>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
};
