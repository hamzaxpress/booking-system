import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.shipment import get_shipment_by_docket, should_redact_public


SYSTEM_INSTRUCTION = """You are "Logi-Copilot," the high-end, human-like AI assistant for this logistics platform.
Your goal is to be a proactive business partner for Admins and a helpful guide for Customers.

RULES OF ENGAGEMENT:
1. PERSONALITY: Professional, empathetic, and conversational. Use natural transitions like "Checking that for you..." or "I've pulled the latest records."
2. DATA ACCESS: You have access to tools (functions) to fetch Revenue, Shipment Status, and Cancellation data. NEVER invent numbers. If a tool returns no data, explain that clearly.
3. HANDLING INVALID QUERIES: If a user asks for something you cannot do (e.g., "Predict the future" or "Personal advice"), do not give a short error. Instead, say: "I can't perform predictive analysis yet, but I can show you the current trends for this week to help you plan. Would you like to see that?"
4. ROLE-BASED SUGGESTIONS: Always end a failed or broad query with 2-3 "Nearby Questions" tailored to the user's role:
   - Admin: "Try asking about today's revenue or cancellation rates."
   - Customer: "Try asking for your courier's current location or ETA."
5. FORMATTING: Use clear, plain text. No markdown symbols like ** or #. Keep responses to 2-3 fluid sentences.
"""


class CopilotError(Exception):
    pass


async def _generate_final_response(
    question: str,
    role: str,
    tool_result: Optional[Dict[str, Any]] = None,
    fallback_text: Optional[str] = None,
) -> str:
    payload_text = {
        "role": role,
        "question": question,
        "data": tool_result if tool_result is not None else None,
    }
    contents = [
        {
            "role": "user",
            "parts": [{"text": f"Context: {json.dumps(payload_text)}"}],
        }
    ]
    try:
        resp = await _call_gemini(contents, tools=None)
        text_out = _extract_text(resp)
        if text_out:
            return text_out
    except Exception:
        pass
    if fallback_text:
        return fallback_text
    return _system_error_message()


async def _call_gemini(contents: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if not settings.GOOGLE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_API_KEY is not configured on the server.",
        )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent?key={settings.GOOGLE_API_KEY}"
    )

    payload: Dict[str, Any] = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 768,
        },
    }
    if tools:
        payload["tools"] = tools
        payload["tool_config"] = {
            "function_calling_config": {
                "mode": "ANY",
            }
        }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            # Retry once without tool_config (some models reject it)
            if tools and "tool_config" in payload:
                retry_payload = dict(payload)
                retry_payload.pop("tool_config", None)
                try:
                    resp = await client.post(url, json=retry_payload)
                    resp.raise_for_status()
                    return resp.json()
                except Exception:
                    pass
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI provider error. Please try again.",
            ) from exc


def _extract_text(response: Dict[str, Any]) -> str:
    parts = response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    texts = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text")]
    return "".join(texts).strip()


def _extract_function_call(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    parts = response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    for p in parts:
        if isinstance(p, dict) and p.get("functionCall"):
            return p.get("functionCall")
    return None


def _safe_args(args: Any) -> Dict[str, Any]:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            return json.loads(args)
        except Exception:
            return {}
    return {}


def _role_to_suggestions(role: str) -> str:
    if role == "admin":
        return "today's revenue, cancellation rates today, delivered vs returned this month"
    if role == "staff":
        return "today's bookings, in-transit shipments, pickup scheduled count"
    return "courier location, estimated delivery time, status meaning"


def _system_error_message() -> str:
    return (
        "I'm having a momentary trouble connecting to our tracking system. "
        "Please give me a second and try again."
    )


def _build_history(messages: Optional[List[Dict[str, str]]], question: str) -> List[Dict[str, Any]]:
    contents: List[Dict[str, Any]] = []
    if messages:
        for m in messages[-5:]:
            role = "user" if m.get("role") == "user" else "model"
            text = (m.get("text") or "").strip()
            if text:
                contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": question}]})
    return contents


def _tool_declarations_for_role(role: str) -> List[Dict[str, Any]]:
    declarations = []
    if role in {"admin", "staff", "customer"}:
        declarations.append({
            "name": "get_shipment_details",
            "description": "Get shipment status, latest location, and ETA for a docket number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "docket_id": {"type": "string", "description": "Shipment docket number"}
                },
                "required": ["docket_id"],
            },
        })
        declarations.append({
            "name": "get_status_definition",
            "description": "Explain what a shipment status means.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_code": {
                        "type": "string",
                        "enum": [
                            "BOOKED",
                            "PICKUP_SCHEDULED",
                            "PICKED_UP",
                            "AT_ORIGIN_HUB",
                            "IN_TRANSIT",
                            "AT_DESTINATION_HUB",
                            "OUT_FOR_DELIVERY",
                            "DELIVERED",
                            "DELIVERY_ATTEMPTED",
                            "CANCELLED",
                            "RETURNED_TO_HUB",
                            "LOST",
                            "DAMAGED",
                        ],
                        "description": "Shipment status code",
                    }
                },
                "required": ["status_code"],
            },
        })
        declarations.append({
            "name": "get_tracking_summary",
            "description": "Get a concise summary of the current shipment and latest tracking info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "docket_id": {"type": "string", "description": "Shipment docket number"}
                },
                "required": ["docket_id"],
            },
        })
    if role in {"admin", "staff"}:
        declarations.append({
            "name": "get_kpi_summary",
            "description": "Get counts of delivered, cancelled, and in-transit shipments.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        })
        declarations.append({
            "name": "get_status_count",
            "description": "Get count of shipments for a specific status code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_code": {
                        "type": "string",
                        "enum": [
                            "BOOKED",
                            "PICKUP_SCHEDULED",
                            "PICKED_UP",
                            "AT_ORIGIN_HUB",
                            "IN_TRANSIT",
                            "AT_DESTINATION_HUB",
                            "OUT_FOR_DELIVERY",
                            "DELIVERED",
                            "DELIVERY_ATTEMPTED",
                            "CANCELLED",
                            "RETURNED_TO_HUB",
                            "LOST",
                            "DAMAGED",
                        ],
                        "description": "Shipment status code",
                    }
                },
                "required": ["status_code"],
            },
        })
    if role == "admin":
        declarations.append({
            "name": "get_financial_metrics",
            "description": "Get revenue totals for a given time period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_period": {
                        "type": "string",
                        "enum": ["today", "this_week", "this_month", "all_time"],
                        "description": "Time period for revenue totals",
                    }
                },
                "required": ["time_period"],
            },
        })
    return [{"function_declarations": declarations}]


def _get_shipment_details(db: Session, docket_id: str, redact: bool) -> Dict[str, Any]:
    shipment = get_shipment_by_docket(db, docket_id)
    redact = redact or should_redact_public(shipment)
    history = shipment.history
    latest = max(history, key=lambda h: h.event_time) if history else None
    return {
        "docket_number": shipment.docket_number,
        "status_code": shipment.status.code,
        "status_label": shipment.status.label,
        "eta": shipment.estimated_delivery,
        "latest_location": "REDACTED" if redact else (latest.location if latest else None),
        "latest_update_time": latest.event_time if latest else None,
    }


def _get_financial_metrics(db: Session, time_period: str) -> Dict[str, Any]:
    if time_period == "today":
        sql = "SELECT SUM(total_amount) AS total_revenue FROM shipments WHERE date(booking_date) = date('now')"
    elif time_period == "this_week":
        sql = "SELECT SUM(total_amount) AS total_revenue FROM shipments WHERE date(booking_date) >= date('now','-6 days')"
    elif time_period == "this_month":
        sql = "SELECT SUM(total_amount) AS total_revenue FROM shipments WHERE date(booking_date) >= date('now','start of month')"
    else:
        sql = "SELECT SUM(total_amount) AS total_revenue FROM shipments"

    result = db.execute(text(sql)).fetchone()
    total = result[0] if result and result[0] is not None else 0
    return {"time_period": time_period, "total_revenue": total}


def _get_kpi_summary(db: Session) -> Dict[str, Any]:
    sql = """
    SELECT ss.code, COUNT(*) AS count
    FROM shipments s JOIN shipment_status ss ON ss.id = s.status_id
    WHERE ss.code IN ('DELIVERED','CANCELLED','IN_TRANSIT')
    GROUP BY ss.code
    """
    rows = db.execute(text(sql)).fetchall()
    counts = {row[0]: row[1] for row in rows}
    return {
        "delivered": counts.get("DELIVERED", 0),
        "cancelled": counts.get("CANCELLED", 0),
        "in_transit": counts.get("IN_TRANSIT", 0),
    }


def _get_status_count(db: Session, status_code: str) -> Dict[str, Any]:
    sql = """
    SELECT COUNT(*) AS count
    FROM shipments s JOIN shipment_status ss ON ss.id = s.status_id
    WHERE ss.code = :status_code
    """
    result = db.execute(text(sql), {"status_code": status_code}).fetchone()
    count = result[0] if result and result[0] is not None else 0
    return {"status_code": status_code, "count": count}


def _get_status_definition(db: Session, status_code: str) -> Dict[str, Any]:
    sql = """
    SELECT code, label, description
    FROM shipment_status
    WHERE code = :status_code
    """
    row = db.execute(text(sql), {"status_code": status_code}).fetchone()
    if not row:
        return {"status_code": status_code, "label": status_code, "description": None}
    return {"status_code": row[0], "label": row[1], "description": row[2]}


def _get_tracking_summary(db: Session, docket_id: str) -> Dict[str, Any]:
    shipment = get_shipment_by_docket(db, docket_id)
    redact = should_redact_public(shipment)
    history = shipment.history or []
    latest = max(history, key=lambda h: h.event_time) if history else None
    return {
        "docket_number": shipment.docket_number,
        "status_label": shipment.status.label,
        "eta": shipment.estimated_delivery,
        "origin_city": "REDACTED" if redact else shipment.sender.city,
        "destination_city": "REDACTED" if redact else shipment.receiver.city,
        "last_event_label": latest.status.label if latest else None,
        "last_event_time": latest.event_time if latest else None,
        "last_event_location": "REDACTED" if redact else (latest.location if latest else None),
        "events_count": len(history),
    }

def _extract_status_code_from_question(question: str) -> Optional[str]:
    q = question.lower()
    mapping = {
        "pickup scheduled": "PICKUP_SCHEDULED",
        "booked": "BOOKED",
        "picked up": "PICKED_UP",
        "at origin hub": "AT_ORIGIN_HUB",
        "in transit": "IN_TRANSIT",
        "at destination hub": "AT_DESTINATION_HUB",
        "out for delivery": "OUT_FOR_DELIVERY",
        "delivery attempted": "DELIVERY_ATTEMPTED",
        "delivered": "DELIVERED",
        "cancelled": "CANCELLED",
        "canceled": "CANCELLED",
        "returned to hub": "RETURNED_TO_HUB",
        "lost": "LOST",
        "damaged": "DAMAGED",
    }
    for phrase, code in mapping.items():
        if phrase in q:
            return code
    return None


def _is_logistics_question(question: str) -> bool:
    q = question.lower()
    keywords = [
        "shipment", "courier", "delivery", "tracking", "docket", "status",
        "in transit", "pickup", "booked", "delivered", "cancelled", "hub",
        "eta", "estimated delivery", "out for delivery", "return", "lost", "damaged",
    ]
    return any(k in q for k in keywords)


def _is_tracking_summary_request(question: str) -> bool:
    q = question.lower()
    return any(x in q for x in ["summary", "details", "whole page", "full details", "all details", "courier details"])


def _is_full_details_request(question: str) -> bool:
    q = question.lower()
    return any(x in q for x in ["full details", "all details", "complete details", "everything", "whole page"])


def _fallback_tool_from_question(question: str, role: str, tracking_docket: Optional[str]) -> Optional[Dict[str, Any]]:
    q = question.lower()
    if _is_tracking_summary_request(question) and tracking_docket:
        return {"tool": "get_tracking_summary", "args": {"docket_id": tracking_docket}}
    if "mean" in q or "meaning" in q or "what does" in q:
        code = _extract_status_code_from_question(question)
        if code:
            return {"tool": "get_status_definition", "args": {"status_code": code}}
    if role == "admin" and "revenue" in q:
        if "today" in q:
            return {"tool": "get_financial_metrics", "args": {"time_period": "today"}}
        if "week" in q:
            return {"tool": "get_financial_metrics", "args": {"time_period": "this_week"}}
        if "month" in q:
            return {"tool": "get_financial_metrics", "args": {"time_period": "this_month"}}
        return {"tool": "get_financial_metrics", "args": {"time_period": "all_time"}}

    if role in {"admin", "staff"}:
        if "in transit" in q:
            return {"tool": "get_status_count", "args": {"status_code": "IN_TRANSIT"}}
        if "delivered" in q:
            return {"tool": "get_status_count", "args": {"status_code": "DELIVERED"}}
        if "cancelled" in q or "canceled" in q:
            return {"tool": "get_status_count", "args": {"status_code": "CANCELLED"}}
        if "pickup scheduled" in q:
            return {"tool": "get_status_count", "args": {"status_code": "PICKUP_SCHEDULED"}}
        if "booked" in q:
            return {"tool": "get_status_count", "args": {"status_code": "BOOKED"}}
        if "out for delivery" in q:
            return {"tool": "get_status_count", "args": {"status_code": "OUT_FOR_DELIVERY"}}
        if "returned" in q:
            return {"tool": "get_status_count", "args": {"status_code": "RETURNED_TO_HUB"}}
        if "lost" in q:
            return {"tool": "get_status_count", "args": {"status_code": "LOST"}}
        if "damaged" in q:
            return {"tool": "get_status_count", "args": {"status_code": "DAMAGED"}}

    if role == "customer" and tracking_docket:
        return {"tool": "get_shipment_details", "args": {"docket_id": tracking_docket}}

    return None


def _format_tool_answer(tool_name: str, tool_result: Dict[str, Any], role: str) -> str:
    if tool_name == "get_financial_metrics":
        period = tool_result.get("time_period", "all_time").replace("_", " ")
        total = tool_result.get("total_revenue", 0)
        return f"I've pulled the latest records — revenue for {period} is INR {total}. Try asking: {_role_to_suggestions(role)}."
    if tool_name == "get_status_count":
        status_code = tool_result.get("status_code", "STATUS")
        status = status_code.replace("_", " ").title()
        count = tool_result.get("count", 0)
        if status_code == "DELIVERED":
            return f"Checking that for you - {count} shipments were delivered today."
        return f"Checking that for you - {count} shipments are in {status}. Try asking: {_role_to_suggestions(role)}."
    if tool_name == "get_kpi_summary":
        d = tool_result.get("delivered", 0)
        c = tool_result.get("cancelled", 0)
        t = tool_result.get("in_transit", 0)
        return f"I've pulled the latest totals — Delivered {d}, Cancelled {c}, In Transit {t}. Try asking: {_role_to_suggestions(role)}."
    if tool_name == "get_shipment_details":
        status = tool_result.get("status_label") or tool_result.get("status_code")
        eta = tool_result.get("eta")
        return f"I've checked that for you — current status is {status}. ETA: {eta or 'not available yet'}."
    if tool_name == "get_status_definition":
        label = tool_result.get("label") or tool_result.get("status_code")
        desc = tool_result.get("description")
        status_code = tool_result.get("status_code")
        if status_code == "PICKUP_SCHEDULED":
            return (
                "Pickup Scheduled means we've received the pickup request, but the package hasn't been collected yet. "
                "The driver has it on their route, and it's still at the sender's location. "
                "If it stays here for more than 24-48 hours, it could be a missed pickup, a manifest delay, "
                "or a scan that will update at the next hub."
            )
        if desc:
            return f"{label} means {desc}."
        return f"{label} means the shipment is currently in that stage of the journey."
    if tool_name == "get_tracking_summary":
        status = tool_result.get("status_label")
        eta = tool_result.get("eta") or "not available yet"
        origin = tool_result.get("origin_city")
        dest = tool_result.get("destination_city")
        last_label = tool_result.get("last_event_label")
        last_time = tool_result.get("last_event_time")
        last_loc = tool_result.get("last_event_location")
        events = tool_result.get("events_count")
        return (
            f"Here’s a quick summary — status is {status}, ETA {eta}, route {origin} to {dest}. "
            f"Latest update: {last_label or 'not available'} at {last_loc or 'unknown location'} "
            f"({last_time or 'time not available'}). {events} tracking events so far."
        )
    return "I've pulled the latest records for you. Try asking: " + _role_to_suggestions(role) + "."


async def _run_tool(db: Session, tool_name: str, args: Dict[str, Any], role: str, tracking_docket: Optional[str]) -> Dict[str, Any]:
    if tool_name == "get_shipment_details":
        docket = args.get("docket_id") or tracking_docket
        if not docket:
            raise CopilotError("Missing docket number.")
        redact = role == "customer"
        return _get_shipment_details(db, docket, redact)

    if tool_name == "get_financial_metrics":
        if role != "admin":
            raise CopilotError("Financial metrics are restricted to admins.")
        time_period = args.get("time_period", "all_time")
        return _get_financial_metrics(db, time_period)

    if tool_name == "get_kpi_summary":
        return _get_kpi_summary(db)
    if tool_name == "get_status_count":
        status_code = args.get("status_code")
        if not status_code:
            raise CopilotError("Missing status code.")
        return _get_status_count(db, status_code)
    if tool_name == "get_status_definition":
        status_code = args.get("status_code")
        if not status_code:
            raise CopilotError("Missing status code.")
        return _get_status_definition(db, status_code)
    if tool_name == "get_tracking_summary":
        docket = args.get("docket_id") or tracking_docket
        if not docket:
            raise CopilotError("Missing docket number.")
        return _get_tracking_summary(db, docket)

    raise CopilotError("Unknown tool requested.")


async def _generate_answer_with_tools(
    db: Session,
    question: str,
    role: str,
    history: Optional[List[Dict[str, str]]] = None,
    tracking_docket: Optional[str] = None,
) -> Dict[str, Any]:
    contents = _build_history(history, question)
    tools = _tool_declarations_for_role(role)

    try:
        if role == "customer" and not _is_logistics_question(question) and not _is_tracking_summary_request(question):
            fallback = (
                "I can only help with your shipment and tracking details here. "
                "Try asking about your courier's location, ETA, or status meaning."
            )
            answer = await _generate_final_response(question, role, None, fallback)
            return {"answer": answer}

        # If user asks for status meaning, answer directly with status definition
        if "mean" in question.lower() or "meaning" in question.lower() or "what does" in question.lower():
            code = _extract_status_code_from_question(question)
            if not code and tracking_docket:
                detail = _get_shipment_details(db, tracking_docket, role == "customer")
                code = detail.get("status_code")
            if code:
                tool_result = _get_status_definition(db, code)
                fallback = _format_tool_answer("get_status_definition", tool_result, role)
                answer = await _generate_final_response(question, role, tool_result, fallback)
                return {"answer": answer, "data": tool_result}

        if _is_tracking_summary_request(question) and tracking_docket:
            tool_result = _get_tracking_summary(db, tracking_docket)
            if _is_full_details_request(question):
                fallback = _format_tool_answer("get_tracking_summary", tool_result, role)
                answer = await _generate_final_response(question, role, tool_result, fallback)
                return {"answer": answer, "data": tool_result}
            full = _format_tool_answer("get_tracking_summary", tool_result, role)
            short = full.split(". ")[0] + "."
            answer = await _generate_final_response(question, role, tool_result, short)
            return {"answer": answer, "data": tool_result}

        first = await _call_gemini(contents, tools=tools)
        function_call = _extract_function_call(first)
        if not function_call:
            # One retry nudging the model to use tools
            contents.append({"role": "user", "parts": [{"text": "Please use the available tools to answer."}]})
            first = await _call_gemini(contents, tools=tools)
            function_call = _extract_function_call(first)
            if not function_call:
                fallback = (
                    "I can't find the right data for that yet. "
                    f"Try asking: {_role_to_suggestions(role)}."
                )
                answer = await _generate_final_response(question, role, None, fallback)
                return {"answer": answer}

        tool_name = function_call.get("name")
        args = _safe_args(function_call.get("args") or {})
        tool_result = await _run_tool(db, tool_name, args, role, tracking_docket)
        fallback = _format_tool_answer(tool_name, tool_result, role)
        answer = await _generate_final_response(question, role, tool_result, fallback)
        return {"answer": answer, "data": tool_result}
    except CopilotError as exc:
        fallback = (
            "I can't perform that request right now, but I can help with something else. "
            f"Try asking: {_role_to_suggestions(role)}."
        )
        answer = await _generate_final_response(question, role, None, fallback)
        return {"answer": answer}
    except Exception:
        fallback = _fallback_tool_from_question(question, role, tracking_docket)
        if fallback:
            tool_name = fallback["tool"]
            tool_result = await _run_tool(db, tool_name, fallback["args"], role, tracking_docket)
            formatted = _format_tool_answer(tool_name, tool_result, role)
            answer = await _generate_final_response(question, role, tool_result, formatted)
            return {"answer": answer, "data": tool_result}
        answer = await _generate_final_response(question, role, None, _system_error_message())
        return {"answer": answer}


async def answer_admin_question(
    db: Session,
    question: str,
    role: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    return await _generate_answer_with_tools(db, question, role, history=history)


async def answer_tracking_question(
    db: Session,
    docket: str,
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    return await _generate_answer_with_tools(db, question, "customer", history=history, tracking_docket=docket)
