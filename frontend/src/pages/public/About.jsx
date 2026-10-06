import React, { useState, useEffect } from 'react';
import api from '../../api/client';
import { ShieldCheck, Award, MapPin, Building2, Users, Target, Eye } from 'lucide-react';

export const About = () => {
  const [leadership, setLeadership] = useState([]);
  const [offices, setOffices] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const leadRes = await api.get('/leadership');
        if (leadRes?.data) setLeadership(leadRes.data);

        const offRes = await api.get('/offices');
        if (offRes?.data) setOffices(offRes.data);
      } catch (err) {
        console.error('Error fetching about data', err);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-12 space-y-16">
      
      {/* Company Header */}
      <div className="text-center max-w-3xl mx-auto space-y-4">
        <h1 className="text-4xl font-extrabold text-white">About <span className="gradient-text">VPD Technologies</span></h1>
        <p className="text-sm text-slate-300 leading-relaxed">
          Founded in 2020, VPD Technologies Private Limited is a premier digital transformation and enterprise engineering organization headquartered in New Delhi with offices across Bangalore, Hyderabad, Pune, Mumbai, Dubai, and Singapore.
        </p>
      </div>

      {/* Vision & Mission */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="glass-card p-8 rounded-3xl space-y-4 border border-slate-800">
          <div className="w-12 h-12 rounded-2xl bg-sky-500/10 text-sky-400 flex items-center justify-center">
            <Eye className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-white">Our Vision</h2>
          <p className="text-xs text-slate-300 leading-relaxed">
            To become one of Asia's most trusted Digital Transformation companies by building secure, scalable, and intelligent enterprise software solutions.
          </p>
        </div>

        <div className="glass-card p-8 rounded-3xl space-y-4 border border-slate-800">
          <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
            <Target className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-white">Our Mission</h2>
          <p className="text-xs text-slate-300 leading-relaxed">
            Deliver world-class enterprise technology solutions through continuous innovation, engineering excellence, security first practices, and customer-centric development.
          </p>
        </div>
      </div>

      {/* Leadership */}
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-white text-center">Executive Leadership</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6">
          {(leadership.length > 0 ? leadership : [
            { name: 'Dr. Vikram Nair', title: 'Founder & CEO' },
            { name: 'Sara Cheng', title: 'Chief Technology Officer' },
            { name: 'Arjun Mehta', title: 'COO, Global Operations' },
            { name: 'Elena Rossi', title: 'Chief Experience Officer' },
          ]).map((leader, i) => (
            <div key={i} className="glass-card p-6 rounded-2xl text-center space-y-3">
              <div className="w-16 h-16 rounded-full bg-sky-500/20 text-sky-400 font-bold text-xl flex items-center justify-center mx-auto border border-sky-500/30">
                {leader.name ? leader.name[0] : 'L'}
              </div>
              <h3 className="text-base font-bold text-white">{leader.name}</h3>
              <p className="text-xs text-sky-400 font-medium">{leader.title}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Offices */}
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-white text-center">Global Locations & Centers of Excellence</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 md:grid-cols-6 gap-4">
          {(offices.length > 0 ? offices : [
            { city: 'Bangalore', description: 'HQ & Innovation Lab' },
            { city: 'Dubai', description: 'MENA Regional Office' },
            { city: 'Singapore', description: 'SEA Hub' },
            { city: 'Mumbai', description: 'Delivery Center' },
            { city: 'Hyderabad', description: 'Cybersecurity CoE' },
            { city: 'Pune', description: 'AI & Data Science' },
          ]).map((off, i) => (
            <div key={i} className="glass-card p-4 rounded-xl text-center space-y-1">
              <MapPin className="w-5 h-5 text-sky-400 mx-auto" />
              <h4 className="text-sm font-bold text-white">{off.city}</h4>
              <p className="text-[11px] text-slate-400">{off.description}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
