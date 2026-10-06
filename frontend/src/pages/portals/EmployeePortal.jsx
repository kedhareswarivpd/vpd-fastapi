import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { 
  Briefcase, 
  CheckSquare, 
  Users, 
  DollarSign, 
  Headphones, 
  TrendingUp, 
  FileText, 
  Calendar,
  Layers,
  Clock,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

export const EmployeePortal = () => {
  const { user } = useAuth();
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [leads, setLeads] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [payslips, setPayslips] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEmployeeData = async () => {
      setLoading(true);
      try {
        const [projRes, taskRes, leadRes, tickRes, payRes] = await Promise.allSettled([
          api.get('/projects'),
          api.get('/tasks'),
          api.get('/leads'),
          api.get('/tickets'),
          api.get('/employees/me/payslips')
        ]);

        if (projRes.status === 'fulfilled' && projRes.value?.data) setProjects(projRes.value.data);
        if (taskRes.status === 'fulfilled' && taskRes.value?.data) setTasks(taskRes.value.data);
        if (leadRes.status === 'fulfilled' && leadRes.value?.data) setLeads(leadRes.value.data);
        if (tickRes.status === 'fulfilled' && tickRes.value?.data) setTickets(tickRes.value.data);
        if (payRes.status === 'fulfilled' && payRes.value?.data) setPayslips(payRes.value.data);
      } catch (err) {
        console.error('Error fetching employee portal data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchEmployeeData();
  }, []);

  const roleTitle = user?.role ? user.role.replace('_', ' ').toUpperCase() : 'EMPLOYEE';

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      
      {/* Header Banner */}
      <div className="glass-panel p-8 rounded-3xl border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <span className="text-xs font-bold text-sky-400 uppercase tracking-widest">{roleTitle} WORKSPACE</span>
          <h1 className="text-3xl font-extrabold text-white">Welcome back, {user?.name}</h1>
          <p className="text-xs text-slate-400">Departmental operations, task execution, and self-service portal.</p>
        </div>
        <div className="glass-card px-4 py-2 rounded-xl text-xs text-slate-300 flex items-center space-x-2">
          <Clock className="w-4 h-4 text-sky-400" />
          <span>Active Session · {user?.email}</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="glass-card p-6 rounded-2xl space-y-2">
          <Briefcase className="w-6 h-6 text-sky-400" />
          <div className="text-2xl font-bold text-white">{projects.length}</div>
          <div className="text-xs text-slate-400 font-medium">Active Client Projects</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <CheckSquare className="w-6 h-6 text-emerald-400" />
          <div className="text-2xl font-bold text-white">{tasks.length}</div>
          <div className="text-xs text-slate-400 font-medium">Assigned Tasks</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <TrendingUp className="w-6 h-6 text-indigo-400" />
          <div className="text-2xl font-bold text-white">{leads.length}</div>
          <div className="text-xs text-slate-400 font-medium">CRM Leads / Opportunities</div>
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-2">
          <Headphones className="w-6 h-6 text-purple-400" />
          <div className="text-2xl font-bold text-white">{tickets.length}</div>
          <div className="text-xs text-slate-400 font-medium">Support Tickets Queue</div>
        </div>
      </div>

      {/* Tasks & Projects Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Projects List */}
        <div className="lg:col-span-6 glass-panel p-6 rounded-3xl border border-slate-800 space-y-4">
          <h2 className="text-lg font-bold text-white">Engagements & Projects</h2>
          <div className="space-y-3">
            {projects.slice(0, 5).map((p, idx) => (
              <div key={idx} className="glass-card p-4 rounded-xl space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-white">{p.title}</h3>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 font-semibold">
                    {p.status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">{p.overview}</p>
                <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                  <div className="bg-sky-400 h-1.5 rounded-full" style={{ width: `${p.progress_percent || 60}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Assigned Tasks */}
        <div className="lg:col-span-6 glass-panel p-6 rounded-3xl border border-slate-800 space-y-4">
          <h2 className="text-lg font-bold text-white">My Active Tasks</h2>
          <div className="space-y-3">
            {tasks.slice(0, 5).map((t, idx) => (
              <div key={idx} className="glass-card p-4 rounded-xl flex items-center justify-between">
                <div className="space-y-1">
                  <h4 className="text-xs font-bold text-white">{t.title}</h4>
                  <p className="text-[11px] text-slate-400">Due: {t.due_date || 'In Progress'}</p>
                </div>
                <span className="text-[10px] px-2.5 py-1 rounded bg-slate-800 text-sky-400 font-medium">
                  {t.priority || 'Normal'}
                </span>
              </div>
            ))}
          </div>
        </div>

      </div>

    </div>
  );
};
