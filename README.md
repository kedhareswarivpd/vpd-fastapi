# VPD Technologies — Full-Stack Enterprise Platform

A production-ready full-stack enterprise web application built for **VPD Technologies Private Limited**. Powered by a high-performance **FastAPI (Python)** backend and a state-of-the-art **React + Vite + TailwindCSS** frontend.

---

## 🚀 Key Features & Architectural Highlights

- **7 Tailored Role-Based Dashboards & Portals**:
  1. **Public Corporate Website**: Dynamic landing page, enterprise services catalogue, flagship products, case studies, open career positions, and inquiry form.
  2. **Super Admin Governance Portal**: Real-time system metrics, security audit log stream, user account controls, and **1-click PostgreSQL database snapshot trigger**.
  3. **Admin Panel**: Role-based access control (RBAC), user directory management, and CMS content editor.
  4. **Sales / CRM Portal**: Lead qualification pipeline, proposal quote builder, contract management, and 1-click client provisioning.
  5. **HR Portal**: Employee onboarding lifecycle, departmental staffing, and leave management.
  6. **Project / Delivery (PM) Portal**: Project portfolio health, milestone progress tracker, developer sprint task boards, and final deliverable sign-offs.
  7. **Employee, Client & Partner Portals**: Task execution, client invoice tracking, support ticket queues, and partner collateral downloads.

- **Authentication & Security**:
  - Fully self-owned opaque session authentication (Argon2id password hashing, cookie-based session management, rate-limiting, and optional MFA).
  - Pre-seeded role credentials for seamless testing.

- **Database & Storage Architecture**:
  - **Database**: PostgreSQL (Managed Supabase or local instance) powered by Async SQLAlchemy 2.0 & Alembic migrations.
  - **Seeder**: Idempotent automated database seeder (`seeds.py`) populating all 26+ tables with VPD Technologies sample data.

---

## 🛠️ Technology Stack

| Component | Technologies Used |
| :--- | :--- |
| **Backend API** | FastAPI (Python 3.12+), Pydantic v2, Uvicorn, SlowAPI Rate Limiter |
| **Database & ORM** | PostgreSQL, AsyncSQLAlchemy, Asyncpg, Alembic Migrations |
| **Frontend Web App** | React 19, Vite, TailwindCSS v4, Lucide Icons, Axios |
| **Caching & Mail** | Upstash Redis / Redis, Brevo Transactional HTTP Email API |

---

## 📂 Project Directory Structure

```text
VPD-Technologies-Platform/
├── backend/                  # FastAPI Python Backend
│   ├── alembic/              # Alembic Database Migration Scripts
│   ├── app/
│   │   ├── core/             # Database, Config, Security, Logger & Middleware
│   │   ├── models/           # SQLAlchemy Data Models (26+ Tables)
│   │   ├── routers/          # REST API Route Controllers (/api/v1/*)
│   │   ├── schemas/          # Pydantic Request/Response Validation Schemas
│   │   └── seeders/          # CMS & User Seeder Logic
│   ├── docker/               # Dockerfile & Production Nginx Setup
│   ├── tests/                # Automated Pytest Suite
│   ├── seeds.py              # Master Seeder Script
│   └── requirements.txt      # Python Dependencies
├── frontend/                 # React + Vite Frontend Application
│   ├── src/
│   │   ├── api/              # Axios API Client with Interceptors
│   │   ├── components/       # Layouts (Navbar, Footer) & Glassmorphism UI
│   │   ├── context/          # AuthContext & Session Management
│   │   ├── pages/
│   │   │   ├── public/       # Home, Services, Products, About, Careers, Contact, Login
│   │   │   └── portals/      # Super Admin, Admin, Employee, Client, Partner Dashboards
│   │   ├── App.jsx           # Tab State Router & Main App Wrapper
│   │   ├── index.css         # Glassmorphism & Custom Gradient System
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js        # Vite Configuration with API Proxy
├── docker-compose.yml        # Docker Compose Deployment Stack
└── README.md                 # Project Documentation
```

---

## ⚙️ Local Development Setup

### Prerequisites
- **Python**: 3.12+
- **Node.js**: v18+ & npm
- **PostgreSQL**: Managed Supabase instance or local PostgreSQL container.

---

### 1. Backend Setup (FastAPI)

1. Navigate to the backend folder:
   ```powershell
   cd backend
   ```

2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install required Python packages:
   ```powershell
   pip install -r requirements.txt
   ```

4. Configure environment variables in `backend/.env`:
   ```env
   ENV=development
   DB_HOST=db.yxkrdhrcunxqhwkgqhex.supabase.co
   DB_PORT=5432
   DB_NAME=postgres
   DB_USER=postgres
   DB_PASS=VPDTechnlogies%40
   ```

5. Run Alembic Database Migrations & Seed Sample Data:
   ```powershell
   alembic upgrade head
   python seeds.py
   ```

6. Start the FastAPI backend server:
   ```powershell
   uvicorn app.main:app --reload
   ```
   *The backend server will run on **`http://127.0.0.1:8000`** (Swagger docs available at [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs)).*

---

### 2. Frontend Setup (React + Vite)

1. Open a new terminal and navigate to the `frontend` folder:
   ```powershell
   cd frontend
   ```

2. Install dependencies:
   ```powershell
   npm install
   ```

3. Start the Vite development server:
   ```powershell
   npm run dev
   ```
   *The frontend application will be available at **`http://localhost:5173`**.*

---

## 🔑 Seeded Demo Credentials

Default Password for **ALL** seeded accounts: **`Password123!`**

| Role / Portal | Login Email | Purpose / Department |
| :--- | :--- | :--- |
| **Super Admin** | `superadmin@vpdtechnologies.com` | Full System & Backup Governance |
| **System Admin** | `admin@vpdtechnologies.com` | User Access & CMS Management |
| **HR Lead** | `hr@vpdtechnologies.com` | Staffing & Onboarding |
| **Sales Lead** | `sales@vpdtechnologies.com` | CRM Leads & Proposals |
| **Project Manager** | `pm@vpdtechnologies.com` | Project Delivery & Tasks |
| **Developer Lead** | `developer@vpdtechnologies.com` | Sprint Engineering |
| **QA Lead** | `qa@vpdtechnologies.com` | Quality Assurance |
| **Support Agent** | `support@vpdtechnologies.com` | Customer Support Queue |
| **Finance Lead** | `finance@vpdtechnologies.com` | Invoices & Tax Payroll |
| **Client Portal** | `client@acmecorp.com` | Acme Corporation Client Portal |
| **Partner Portal** | `partner@techpartner.com` | TechPartner Global Partner Hub |

---

## 🔒 Security & Code Standards

- **Argon2id Hashing**: High-security password derivation preventing GPU brute-force attacks.
- **CSRF & CORS Controls**: Dynamic origin canonicalization and cookie-level credentials protection.
- **Fail-Open Rate Limiting**: Redis-backed API rate limiting for API endpoint safety.

---

## 📜 License & Ownership

Copyright © 2026 **VPD Technologies Private Limited**. All rights reserved.
