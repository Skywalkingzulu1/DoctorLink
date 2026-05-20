# DoctorLink - South Africa's Healthcare Platform

DoctorLink is a hybrid Web2/Web3 healthcare platform designed for the South African market. It features real-time telehealth consultations, a "gig economy" model for healthcare providers, and autonomous agents integrated with the **Somnia Agentic L1** blockchain.

## 🚀 Key Features

- **Gig Economy for Doctors**: Doctors can toggle "Gig Mode," set custom pricing, and manage their availability.
- **On-Chain Escrow**: Patient payments are held in a Somnia smart contract and released only upon successful consultation.
- **Autonomous Agents**: 
    - **Appointment Matcher**: Automatically connects patients in the waiting room with available doctors.
    - **Prescription Reviewer**: Uses AI (Somnia LLM Inference) to audit prescriptions for safety.
    - **Follow-Up Scheduler**: Generates personalized AI follow-ups post-consultation.
    - **Escrow Agent**: Manages the automated release or refund of funds on the blockchain.
- **Telehealth Suite**: Integrated video calling (Socket.io), medical records, and digital prescriptions.
- **Hybrid Storage**: Uses Supabase for structured data and Filebase (S3) for medical records/avatars.

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: SQLite (Local) / Supabase Postgres (Production)
- **Blockchain**: Somnia Agentic L1 (Testnet)
- **Real-time**: Socket.io / WebSockets
- **Frontend**: Vanilla HTML5, CSS3, and JavaScript

## 📋 Prerequisites

- Python 3.10+
- [Somnia Testnet Wallet](https://somnia.network/) with STT tokens.
- [Supabase](https://supabase.com/) account (optional for local SQLite dev).

## ⚙️ Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd DoctorLink
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file based on `.env.example`.
   ```bash
   cp .env.example .env
   ```
   Ensure you fill in the following:
   - `SOMNIA_PRIVATE_KEY`: Your wallet's private key.
   - `SOMNIA_ESCROW_CONTRACT`: Leave blank initially (will be filled by deploy script).

## ⛓️ Smart Contract Deployment (Somnia Testnet)

We have automated the compilation and deployment process:

1. **Compile Contracts**:
   ```bash
   python compile_contracts.py
   ```
   This generates `somnia/compiled_contracts.json`.

2. **Deploy to Testnet**:
   ```bash
   python deploy.py
   ```
   This will deploy the `DoctorLinkEscrow` contract to Somnia Testnet and automatically update your `.env` file with the new contract address.

## 🖥️ Running the Application

1. **Start the Backend Server**:
   ```bash
   python main.py
   ```
   The API will be available at `http://localhost:8000`.

2. **Run the Frontend**:
   You can serve the `static/` folder using any web server. For convenience, a simple server is provided:
   ```bash
   python server.py
   ```
   Open your browser at `http://localhost:9000`.

## 🤖 Autonomous Agents

The agents run as background tasks within the FastAPI app. They are initialized in `main.py` and defined in `somnia/autonomous_agents.py`. They leverage Somnia's on-chain agentic capabilities for:
- Auto-matching patients.
- Safe-guarding payments.
- AI-driven medical assistance.

## 📂 Project Structure

- `api/`: FastAPI route handlers.
- `somnia/`: Smart contracts, compilation artifacts, and agent logic.
- `static/`: Frontend HTML/JS/CSS.
- `remix_contracts/`: Clean Solidity files for manual deployment via Remix.
- `database.py`: SQLAlchemy models and DB configuration.
- `deploy.py`: Deployment automation script.

---
*Developed for the Somnia Agentathon.*
