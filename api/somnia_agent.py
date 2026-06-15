"""
Somnia Agent API endpoints for Doctors on Wheels.
Provides AI-powered medical features via Somnia Agentic L1.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel
from typing import Optional

from auth import get_current_user
from database import User, get_db
from sqlalchemy.orm import Session

from somnia.agent_service import (
    invoke_llm_agent,
    invoke_llm_agent_for_user,
    invoke_json_api_agent,
    invoke_website_parser_agent,
    get_agent_result,
    _check_sponsor_balance,
    AI_CREDIT_COSTS,
    check_t800_balance,
    get_t800_fee,
    get_router_stt_balance,
    get_stt_invocation_cost,
    invoke_with_stt,
    t800_token,
    INFER_STRING_SELECTOR,
    FETCH_STRING_SELECTOR,
    AGENT_ID_LLM,
    AGENT_ID_JSON,
)
from eth_abi import encode
from web3 import Web3
from somnia.client import somnia

router = APIRouter(prefix="/api/somnia/agent", tags=["somnia-agents"])


class SymptomCheckRequest(BaseModel):
    symptoms: str
    age: Optional[int] = None
    gender: Optional[str] = None


class DrugInteractionRequest(BaseModel):
    medications: list[str]


class GenerateSummaryRequest(BaseModel):
    consultation_notes: str
    diagnosis: Optional[str] = None


class AgentInvokeRequest(BaseModel):
    agent_type: str
    prompt: str
    system_prompt: Optional[str] = None
    url: Optional[str] = None


class AgentStatusResponse(BaseModel):
    request_id: int
    status: str
    result: Optional[str] = None


@router.post("/symptom-check")
def symptom_check(
    request: SymptomCheckRequest,
    current_user: User = Depends(get_current_user),
):
    """AI symptom pre-screening before booking a doctor."""
    system_prompt = (
        "You are a medical triage assistant. Analyze the patient's symptoms and recommend: "
        "1) urgency level (low/medium/high), "
        "2) which type of specialist to see, "
        "3) any immediate actions. "
        "Always include a disclaimer that this is not a diagnosis."
    )
    prompt = (
        f"Patient symptoms: {request.symptoms}. "
        f"Age: {request.age or 'unknown'}. Gender: {request.gender or 'unknown'}. "
        f"Provide triage assessment."
    )

    try:
        request_id = invoke_llm_agent_for_user(current_user.id, prompt, "symptom_check", system_prompt)
    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))
    return {
        "request_id": request_id,
        "credits_cost": AI_CREDIT_COSTS["symptom_check"],
        "message": "Symptom check submitted. Poll /result/{request_id} for results.",
    }


@router.post("/drug-interaction")
def drug_interaction_check(
    request: DrugInteractionRequest,
    current_user: User = Depends(get_current_user),
):
    """Check drug interactions before creating a prescription. Costs 5 credits."""
    system_prompt = (
        "You are a clinical pharmacist. Check for drug interactions, contraindications, "
        "and dosage concerns. List each interaction with severity level (low/medium/high). "
        "Provide recommendations."
    )
    medications = ", ".join(request.medications)
    prompt = f"Check interactions between these medications: {medications}"

    try:
        request_id = invoke_llm_agent_for_user(current_user.id, prompt, "drug_interaction", system_prompt)
    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))
    return {
        "request_id": request_id,
        "credits_cost": AI_CREDIT_COSTS["drug_interaction"],
        "message": "Drug interaction check submitted.",
    }


@router.post("/generate-summary")
def generate_visit_summary(
    request: GenerateSummaryRequest,
    current_user: User = Depends(get_current_user),
):
    """Auto-generate a structured medical visit summary. Costs 5 credits."""
    system_prompt = (
        "You are a medical scribe. Convert consultation notes into a structured summary with: "
        "Chief Complaint, History, Examination Findings, Assessment/Diagnosis, Plan, "
        "Follow-up recommendations. Use professional medical terminology."
    )
    prompt = f"Consultation notes: {request.consultation_notes}"
    if request.diagnosis:
        prompt += f"\nDiagnosis: {request.diagnosis}"

    try:
        request_id = invoke_llm_agent_for_user(current_user.id, prompt, "visit_summary", system_prompt)
    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))
    return {
        "request_id": request_id,
        "credits_cost": AI_CREDIT_COSTS["visit_summary"],
        "message": "Summary generation submitted.",
    }


@router.post("/invoke")
def invoke_agent(
    request: AgentInvokeRequest,
    current_user: User = Depends(get_current_user),
):
    """Generic agent invocation endpoint."""
    try:
        if request.agent_type == "llm":
            feature = request.system_prompt or "general"
            prompt = request.prompt
            sp = request.system_prompt or "You are a helpful assistant."
            request_id = invoke_llm_agent_for_user(current_user.id, prompt, feature, sp)
        elif request.agent_type == "json_api":
            if not request.url:
                raise HTTPException(status_code=400, detail="URL required")
            request_id = invoke_json_api_agent(request.url)
        elif request.agent_type == "parse_website":
            if not request.url:
                raise HTTPException(status_code=400, detail="URL required")
            request_id = invoke_website_parser_agent(request.url, request.prompt)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown agent type: {request.agent_type}")
    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))

    return {"request_id": request_id, "agent_type": request.agent_type}


async def run_all_triage_tools(triage_data_json: str) -> dict:
    """
    Run 10 specialized AI medical tools on patient triage data.
    Each tool invokes the Somnia LLM Inference agent on-chain with a protocol-grounded prompt.
    Falls back to a timeout placeholder if the agent result is not yet available.
    """
    import json
    data = json.loads(triage_data_json)
    patient_summary = json.dumps(data, indent=2)

    tools = {
        "1. Triage Classification (NICE/CDC)": {
            "sp": (
                "You are an emergency medicine triage assistant. "
                "Classify the patient's acuity level (low/medium/high/urgent) using "
                "NICE Clinical Knowledge Summaries and CDC Emergency Triage Standards. "
                "Provide the classification and 2-3 sentences of justification."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nPerform triage classification.",
        },
        "2. Red Flag Screening (Mayo Clinic)": {
            "sp": (
                "You are an emergency medicine clinician. "
                "Screen for life-threatening 'Red Flags' using Mayo Clinic Emergency Medicine Protocols. "
                "List any positive red flags found with a brief justification for each."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nScreen for red flags.",
        },
        "3. Differential Diagnosis (BMJ/Medscape)": {
            "sp": (
                "You are a clinical diagnostician. "
                "Provide evidence-based differential diagnoses using BMJ Best Practice / Medscape Reference. "
                "List top 3 differentials by probability with brief rationale."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nProvide differential diagnoses.",
        },
        "4. Protocol-based Care Plan (WHO)": {
            "sp": (
                "You are a clinical care coordinator. "
                "Suggest a care plan following WHO Integrated Management of Adult Illness (IMAI) guidelines. "
                "Include immediate actions, monitoring interval, and referral threshold."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nSuggest a care plan.",
        },
        "5. Medication Safety (FDA/Drugs.com)": {
            "sp": (
                "You are a clinical pharmacist. "
                "Check for contraindications and safety concerns using FDA safety databases. "
                "Flag any interactions with severity (low/medium/high) and recommend action."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nCheck medication safety.",
        },
        "6. Diagnostic Script (EM Practice)": {
            "sp": (
                "You are a clinician preparing for a home visit. "
                "Provide a scripted set of diagnostic questions for the examination, "
                "following Clinical Examination Standards (Bates/Talley & O'Connor)."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nCreate a diagnostic script for the home visit.",
        },
        "7. Vital Sign Interpretation (NEWS2)": {
            "sp": (
                "You are a vital signs specialist. "
                "Interpret the patient's vitals using the National Early Warning Score (NEWS2) standards "
                "from the Royal College of Physicians. Report the score, risk category, and recommended response time."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nInterpret vitals using NEWS2.",
        },
        "8. Patient Education Script (Health Literacy)": {
            "sp": (
                "You are a patient education specialist. "
                "Generate a patient-facing script grounded in health literacy standards (AHRQ). "
                "Use simple, clear language suitable for a general audience."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nCreate a patient education script.",
        },
        "9. Clinical Note Framework (SOAP)": {
            "sp": (
                "You are a medical scribe. "
                "Generate a structured SOAP note (Subjective, Objective, Assessment, Plan) "
                "for clinical documentation. Use professional medical terminology and ICD-10 codes where applicable."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nGenerate a SOAP note.",
        },
        "10. Disposition Logic (UpToDate/CDC)": {
            "sp": (
                "You are a care coordinator. "
                "Provide disposition logic (Stay vs. Transfer) using CDC Disposition Algorithms and UpToDate clinical logic. "
                "State the criteria that determine each disposition and the recommended action for this patient."
            ),
            "prompt": f"Patient data:\n{patient_summary}\n\nProvide disposition logic.",
        },
    }

    results = {}
    for name, tool in tools.items():
        request_id = None
        try:
            request_id = await asyncio.to_thread(invoke_llm_agent, tool["prompt"], tool["sp"])
            result = get_agent_result(request_id, wait=True, timeout=15)
            if result and result.result and len(result.result.strip()) > 0:
                results[name] = result.result
            else:
                results[name] = f"[Agent response pending for request {request_id}]"
        except Exception as e:
            if request_id:
                results[name] = f"[Agent error (request {request_id}): {e}]"
            else:
                results[name] = f"[Agent error: {e}]"

    return results


class EmailRequest(BaseModel):
    recipient: str
    subject: str
    body: str

@router.post("/email")
async def send_email_simulation(request: EmailRequest):
    """Simulate sending an email with clinical script or triage data."""
    try:
        from email_validator import validate_email, EmailNotValidError
        validate_email(request.recipient)
        
        # Simulate background email task
        print(f"[EMAIL] To: {request.recipient}")
        print(f"[EMAIL] Subject: {request.subject}")
        print(f"[EMAIL] Body: {request.body[:100]}...")
        
        return {"success": True, "message": f"Email sent to {request.recipient}"}
    except EmailNotValidError:
        raise HTTPException(status_code=400, detail="Invalid email address")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/result/{request_id}", response_model=AgentStatusResponse)
def get_result(
    request_id: int,
    current_user: User = Depends(get_current_user),
):
    """Poll for agent result."""
    try:
        result = get_agent_result(request_id, wait=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get result: {e}")
    return AgentStatusResponse(
        request_id=result.request_id,
        status=result.status,
        result=result.result,
    )


@router.post("/verify-doctor")
def verify_doctor_credentials(
    hpcsa_number: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
):
    """Verify doctor HPCSA registration via external API. Costs 3 credits."""
    try:
        url = f"https://www.hpcsa.co.za/verify/{hpcsa_number}"
        prompt = f"Fetch and verify doctor registration from {url}. Return the registration status."
        request_id = invoke_llm_agent_for_user(current_user.id, prompt, "doctor_verification",
            "You are a medical credential verification assistant.")
    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))
    return {
        "request_id": request_id,
        "credits_cost": AI_CREDIT_COSTS["doctor_verification"],
        "message": "Doctor verification submitted.",
    }


@router.post("/health-tips")
def generate_health_tips(
    data: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Generate patient education content using LLM. Costs 3 credits."""
    topic = data.get("topic", "")
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")
    system_prompt = (
        "You are a patient education specialist. Create clear, accessible health tips "
        "about the given topic. Include: what it is, symptoms, prevention, when to see a doctor. "
        "Use simple language suitable for general audience."
    )
    try:
        request_id = invoke_llm_agent_for_user(current_user.id, 
            f"Create health education content about: {topic}", "health_tips", system_prompt)
    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))
    return {
        "request_id": request_id,
        "credits_cost": AI_CREDIT_COSTS["health_tips"],
        "message": "Health tips generation submitted.",
    }


@router.get("/sponsor-balance")
def get_sponsor_balance():
    """Check sponsor contract STT balance."""
    bal = _check_sponsor_balance()
    return {"sponsor_balance_stt": bal}


@router.get("/credit-costs")
def get_credit_costs():
    """Return AI feature credit costs."""
    return AI_CREDIT_COSTS


class SttInvokeRequest(BaseModel):
    agent_type: str
    prompt: str
    system_prompt: Optional[str] = None
    url: Optional[str] = None


@router.get("/stt/cost")
def get_stt_cost():
    """Return STT cost per agent invocation (1 STT = 30 T800 rate)."""
    cost = get_stt_invocation_cost()
    deposit = float(somnia.w3.from_wei(_get_deposit_direct(), "ether"))
    return {
        "total_stt": cost,
        "deposit_stt": deposit,
        "fee_stt": max(0, cost - deposit),
        "t800_per_invocation": 10,
        "rate": "1 STT = 30 T800",
    }


def _get_deposit_direct() -> int:
    """Direct deposit fetch for the cost endpoint (avoids circular import)."""
    from web3 import Web3
    from somnia.client import somnia
    from config import settings
    PLATFORM_ABI_SIMPLE = [
        {"inputs": [], "name": "getRequestDeposit", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    ]
    platform = somnia.w3.eth.contract(address=somnia.platform_contract_address, abi=PLATFORM_ABI_SIMPLE)
    floor = platform.functions.getRequestDeposit().call()
    per_agent = somnia.w3.to_wei(0.07, "ether")
    return floor + per_agent * 3


@router.post("/stt/invoke")
def invoke_stt_paid(
    request: SttInvokeRequest,
    current_user: User = Depends(get_current_user),
):
    """Invoke an agent with STT payment (deployer wallet pays, 1 STT = 30 T800)."""
    if request.agent_type == "llm":
        sp = request.system_prompt or "You are a helpful assistant."
        prompt = request.prompt
        payload = INFER_STRING_SELECTOR + encode(
            ["string", "string", "bool", "string[]"],
            [prompt, sp, False, []],
        )
        request_id = invoke_with_stt(AGENT_ID_LLM, payload)

    elif request.agent_type == "json_api":
        if not request.url:
            raise HTTPException(status_code=400, detail="URL required")
        payload = FETCH_STRING_SELECTOR + encode(
            ["string", "string"],
            [request.url, ""],
        )
        request_id = invoke_with_stt(AGENT_ID_JSON, payload)

    else:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {request.agent_type}")

    cost = get_stt_invocation_cost()
    return {
        "request_id": request_id,
        "stt_cost": cost,
        "message": f"Agent invoked. Cost: {cost:.4f} STT. Poll /result/{request_id} for results.",
    }


@router.get("/t800/balance")
def get_t800_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check user's off-chain T800 balance."""
    user = db.query(User).filter(User.id == current_user.id).first()
    off_chain_bal = user.t800_balance if user else 0
    on_chain_bal = check_t800_balance(current_user.somnia_address or "")
    fee = get_t800_fee()
    return {
        "t800_balance": off_chain_bal,
        "on_chain_balance": on_chain_bal,
        "t800_fee_per_invocation": fee / 10**18 if fee else 0,
        "router_stt_balance": get_router_stt_balance(),
    }


@router.get("/t800/info")
def get_t800_info():
    """Return T800 token contract info and router status."""
    from config import settings
    return {
        "t800_contract": settings.T800_CONTRACT_ADDRESS or "",
        "router_contract": settings.ROUTER_CONTRACT_ADDRESS or "",
        "dex_contract": settings.DEX_CONTRACT_ADDRESS or "",
        "router_stt_pool_stt": get_router_stt_balance(),
        "t800_fee_per_invocation": get_t800_fee() / 10**18 if get_t800_fee() else 0,
    }


@router.post("/t800/faucet")
def t800_faucet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Credit 5000 T800 to the user's off-chain balance (one claim per user for demo)."""
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.t800_balance and user.t800_balance > 0:
            return {
                "message": "Already claimed T800",
                "t800_balance": user.t800_balance,
            }
        user.t800_balance = (user.t800_balance or 0) + 5000
        db.commit()
        return {
            "message": "5000 T800 credited to your account",
            "t800_balance": user.t800_balance,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
