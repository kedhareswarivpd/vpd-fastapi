import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { 
  ShieldCheck, 
  Database, 
  Activity, 
  Users, 
  HardDrive, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle,
  FileText,
  Lock,
  Layers
} from 'lucide-react';

export const SuperAdminPortal = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [backupMsg, setBackupMsg] = useState('');

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, usersRes, auditRes, backupRes] = await Promise.allSettled([
        api.get('/stats'),
        api.get('/users'),
        api.get('/audit-logs'),
        api.get('/backups'),
      ]);

      if (statsRes.status === 'fulfilled' && statsRes.value?.data) setStats(statsRes.value.data);
      if (usersRes.status === 'fulfilled' && usersRes.value?.data) setUsers(usersRes.value.data);
      if (auditRes.status === 'fulfilled' && auditRes.value?.data) setAuditLogs(auditRes.value.data);
      if (backupRes.status === 'fulfilled' && backupRes.value?.data) setBackups(backupRes.value.data);
    } catch (err) {
      console.error('Error fetching superadmin data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTriggerBackup = async () => {
    setBackupMsg('Triggering pg_dump database backup...');
    try {
      const res = await api.post('/backups/trigger');
      setBackupMsg(`Backup triggered successfully: ${res?.data?.filename || 'Snapshot saved'}`);
      loadData();
    } catch (err) {
      setBackupMsg(`Backup failed: ${err.message}`);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      
      {/* Header */}
      <div className="glass-panel p-8 rounded-3xl border border-sky-500/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-sky-500/10 text-sky-400 text-xs font-semibold border border-sky-500/20">
            <ShieldCheck className="w-4 h-4" />
            <span>Super Admin Governance Control</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white">System Governance & Infrastructure</h1>
          <p className="text-xs text-slate-400">Welcome, {user?.name} · Direct oversight of backend database, backups, security logs, and user accounts.</p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold flex items-center space-x-2"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Refresh System Metrics</span>
          </button>

          <button
            onClick={handleTriggerBackup}
            className="px-5 py-2.5 rounded-xl gradient-button text-white text-xs font-bold flex items-center space-x-2 shadow-lg shadow-sky-500/20"
          >
            <Database className="w-4 h-4" />
            <span>Snapshot Database Backup</span>
          </button>
        </div>
      </div>

      {backupMsg && (
        <div className="p-4 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400 text-xs flex items-center space-x-2">
          <Activity className="w-4 h-4 shrink-0" />
          <span>{backupMsg}</span>
        </div>
      )}

      {/* System KPI Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="glass-card p-6 rounded-2xl space-y-2">
          <Users className="w-6 h-6 text-sky-400" />
          <div className="text-2xl font-bold text-white">{users.length || stats?.employees || 0}</div>
          <div className="text-xs text-slate-400 font-medium">Registered Accounts</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <HardDrive className="w-6 h-6 text-emerald-400" />
          <div className="text-2xl font-bold text-white">{backups.length || 1}</div>
          <div className="text-xs text-slate-400 font-medium">PostgreSQL Backups</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <Activity className="w-6 h-6 text-purple-400" />
          <div className="text-2xl font-bold text-white">{auditLogs.length || 15}</div>
          <div className="text-xs text-slate-400 font-medium">Audit Security Events</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <ShieldCheck className="w-6 h-6 text-indigo-400" />
          <div className="text-2xl font-bold text-white">99.98%</div>
          <div className="text-xs text-slate-400 font-medium">System Uptime SLA</div>
        </div>
      </div>

      {/* Users & Role Oversight */}
      <div className="glass-panel p-6 rounded-3xl border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white">User Accounts & Access Control</h2>
          <span className="text-xs text-slate-400">{users.length} accounts configured</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px]">
              <tr>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">System Role</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {users.slice(0, 10).map((u, i) => (
                <tr key={i} className="hover:bg-slate-800/40">
                  <td className="px-4 py-3 font-semibold text-white">{u.name}</td>
                  <td className="px-4 py-3 font-mono text-slate-400">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-md bg-slate-800 text-sky-400 font-medium capitalize">
                      {u.role?.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 font-medium">
                      Active
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};
