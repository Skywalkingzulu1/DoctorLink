"""
Autonomous agents that run independently on Doctors on Wheels.
Demonstrates agent-native behavior for the Somnia Agentathon.
"""
import asyncio
from datetime import datetime, timezone
from database import get_db, Appointment, Doctor, User, AppointmentStatus, EscrowStatus
from somnia.agent_service import invoke_llm_agent, get_agent_result
from somnia.escrow_service import release_escrow, refund_escrow


class AutonomousAppointmentMatcher:
    """
    Monitors the waiting room and auto-matches patients to available doctors
    based on appointment time, doctor online status, and gig mode.
    """
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval

    async def run(self):
        while True:
            db = None
            try:
                db = next(get_db())
                waiting = (
                    db.query(Appointment)
                    .filter(
                        Appointment.status == AppointmentStatus.SCHEDULED,
                        Appointment.timestamp <= datetime.now(timezone.utc),
                        Appointment.teleconsultation_status == "waiting",
                    )
                    .all()
                )

                for appt in waiting:
                    doctor = db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()
                    if doctor and doctor.is_online and doctor.gig_mode_enabled:
                        appt.status = AppointmentStatus.ACTIVE
                        appt.escrow_status = EscrowStatus.HELD
                        appt.teleconsultation_status = "active"
                        appt.started_at = datetime.now(timezone.utc)
                        db.commit()
                        print(f"[Agent] Auto-matched appointment {appt.id} to Dr. {doctor.name}")

            except Exception as e:
                print(f"[Agent] AppointmentMatcher error: {e}")
            finally:
                if db:
                    db.close()

            await asyncio.sleep(self.check_interval)


class AutonomousPrescriptionReviewer:
    """
    Automatically reviews prescriptions for drug interactions and dosage accuracy
    using Somnia's LLM Inference agent.
    """
    def __init__(self):
        self.pending_reviews: dict[int, int] = {}

    async def review_prescription(self, prescription_id: int, medications: list[str]) -> int:
        system_prompt = (
            "You are a clinical pharmacist reviewing a prescription. "
            "Check for: drug interactions, dosage accuracy, contraindications. "
            "Return: SAFE or FLAG with detailed reasons."
        )
        prompt = f"Review prescription #{prescription_id}. Medications: {', '.join(medications)}"
        request_id = await asyncio.to_thread(invoke_llm_agent, prompt, system_prompt)
        self.pending_reviews[prescription_id] = request_id
        return request_id

    async def check_review_result(self, prescription_id: int) -> dict | None:
        request_id = self.pending_reviews.get(prescription_id)
        if not request_id:
            return None
        result = get_agent_result(request_id)
        if result.status == "success":
            del self.pending_reviews[prescription_id]
            return {"prescription_id": prescription_id, "review": result.result, "safe": "SAFE" in (result.result or "").upper()}
        return None


class AutonomousFollowUpScheduler:
    """
    After consultation, generates personalized follow-up messages using
    Somnia's LLM agent.
    """
    def __init__(self, check_interval: int = 300):
        self.check_interval = check_interval
        self.processed: set[int] = set()

    async def run(self):
        while True:
            db = None
            try:
                db = next(get_db())
                # Clean old entries from processed set (keep last 1000)
                if len(self.processed) > 1000:
                    self.processed.clear()

                cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
                completed = (
                    db.query(Appointment)
                    .filter(
                        Appointment.status == AppointmentStatus.COMPLETED,
                        Appointment.ended_at >= cutoff,
                    )
                    .all()
                )

                for appt in completed:
                    if appt.id in self.processed:
                        continue
                    self.processed.add(appt.id)

                    patient = db.query(User).filter(User.id == appt.patient_id).first()
                    if patient:
                        system_prompt = (
                            "Generate a personalized follow-up message for a patient after their consultation. "
                            "Include: medication reminders, when to book follow-up, warning signs to watch for. "
                            "Keep it warm and professional."
                        )
                        prompt = (
                            f"Patient: {patient.name}. Appointment notes: {appt.notes or 'No notes'}. "
                            f"Create a follow-up message."
                        )
                        request_id = await asyncio.to_thread(invoke_llm_agent, prompt, system_prompt)
                        print(f"[Agent] Follow-up generated for patient {patient.name} (request #{request_id})")

            except Exception as e:
                print(f"[Agent] FollowUpScheduler error: {e}")
            finally:
                if db:
                    db.close()

            await asyncio.sleep(self.check_interval)


class AutonomousEscrowAgent:
    """
    Monitors appointment lifecycle and auto-releases/refunds escrow on-chain
    based on appointment status changes.
    """
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval

    async def run(self):
        while True:
            db = None
            try:
                db = next(get_db())
                held_appointments = (
                    db.query(Appointment)
                    .filter(Appointment.escrow_status == EscrowStatus.HELD)
                    .all()
                )

                for appt in held_appointments:
                    if appt.status == AppointmentStatus.COMPLETED:
                        try:
                            await asyncio.to_thread(release_escrow, appt.id)
                            appt.escrow_status = EscrowStatus.RELEASED
                            db.commit()
                            print(f"[Agent] Auto-released escrow for appointment {appt.id}")
                        except Exception as e:
                            print(f"[Agent] Escrow release failed for {appt.id}: {e}")

                    elif appt.status == AppointmentStatus.CANCELLED:
                        try:
                            await asyncio.to_thread(refund_escrow, appt.id)
                            appt.escrow_status = EscrowStatus.REFUNDED
                            db.commit()
                            print(f"[Agent] Auto-refunded escrow for appointment {appt.id}")
                        except Exception as e:
                            print(f"[Agent] Escrow refund failed for {appt.id}: {e}")

            except Exception as e:
                print(f"[Agent] EscrowAgent error: {e}")
            finally:
                if db:
                    db.close()

            await asyncio.sleep(self.check_interval)


class AutonomousAIDoctorAgent:
    """
    An agentic doctor that autonomously handles consultations.
    When an appointment is booked with the AI Doctor, this agent:
    1. Monitors for the appointment to become ACTIVE.
    2. Uses Somnia LLM to generate a consultation summary based on the patient's reason.
    3. Completes the appointment on-chain and triggers escrow release.
    """
    def __init__(self, check_interval: int = 20):
        self.check_interval = check_interval
        self.ai_doctor_user_email = "ai@somnia.network"

    async def run(self):
        while True:
            db = None
            try:
                db = next(get_db())
                # Find the AI doctor profile
                ai_doc = db.query(Doctor).join(User).filter(User.email == self.ai_doctor_user_email).first()
                if not ai_doc:
                    await asyncio.sleep(self.check_interval)
                    continue

                # Find appointments for the AI doctor that are ACTIVE
                # or SCHEDULED but already started (for immediate processing)
                active_appts = (
                    db.query(Appointment)
                    .filter(
                        Appointment.doctor_id == ai_doc.id,
                        Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.ACTIVE])
                    )
                    .all()
                )

                for appt in active_appts:
                    print(f"[AI Doctor] Handling appointment {appt.id} for patient...")
                    
                    # 1. Use Somnia LLM to provide consultation
                    system_prompt = (
                        "You are the Somnia AI Doctor, an autonomous medical agent. "
                        "Provide a professional medical observation and advice based on the patient's reason for visit. "
                        "Be concise, empathetic, and clear. Suggest if they need a human follow-up."
                    )
                    prompt = f"Patient reason for visit: {appt.reason or 'General check-up'}"
                    
                    try:
                        # Invoke Somnia LLM
                        request_id = await asyncio.to_thread(invoke_llm_agent, prompt, system_prompt)
                        print(f"[AI Doctor] LLM request #{request_id} sent.")
                        
                        # Wait for result (in a real scenario we'd do this async, but for the demo we'll wait a bit)
                        await asyncio.sleep(5) 
                        result = get_agent_result(request_id)
                        
                        if result.status == "success" and result.result:
                            appt.notes = f"AI Consultation Result: {result.result}"
                            appt.somnia_agent_results = result.result
                            appt.status = AppointmentStatus.COMPLETED
                            appt.ended_at = datetime.now(timezone.utc)
                            
                            # Update escrow status for the EscrowAgent to pick up
                            if appt.escrow_status == EscrowStatus.HELD or appt.somnia_tx_hash:
                                # Trigger immediate release via the escrow service
                                try:
                                    await asyncio.to_thread(release_escrow, appt.id)
                                    appt.escrow_status = EscrowStatus.RELEASED
                                    print(f"[AI Doctor] On-chain payment released for appt {appt.id}")
                                except Exception as ee:
                                    print(f"[AI Doctor] Escrow release failed: {ee}")
                            
                            db.commit()
                            print(f"[AI Doctor] Consultation {appt.id} completed successfully.")
                        else:
                            print(f"[AI Doctor] LLM still processing for appt {appt.id}")
                            
                    except Exception as e:
                        print(f"[AI Doctor] Error processing appt {appt.id}: {e}")

            except Exception as e:
                print(f"[AI Doctor] Global agent error: {e}")
            finally:
                if db:
                    db.close()

            await asyncio.sleep(self.check_interval)
