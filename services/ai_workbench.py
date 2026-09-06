import os
import json
import time
import urllib.request
import urllib.error
from services.base import BaseService

# Pricing per million tokens (USD)
RATES = {
    # Anthropic
    "claude-3-5-sonnet-20241022": {"prompt": 3.00, "completion": 15.00},
    "claude-3-5-sonnet": {"prompt": 3.00, "completion": 15.00},
    "claude-3-haiku-20240307": {"prompt": 0.25, "completion": 1.25},
    "claude-3-haiku": {"prompt": 0.25, "completion": 1.25},
    "claude-3-opus-20240229": {"prompt": 15.00, "completion": 75.00},
    "claude-3-opus": {"prompt": 15.00, "completion": 75.00},
    # OpenAI
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "o1-preview": {"prompt": 15.00, "completion": 60.00},
    "o1-mini": {"prompt": 3.00, "completion": 12.00},
}

DEFAULT_WORKFLOWS = [
    {
        "id": "wf-readme",
        "title": "Repo README Architect",
        "category": "ENGINEERING",
        "provider_recommendation": "claude",
        "model": "claude-3-5-sonnet",
        "description": "Transforms raw code structures or repo summaries into high-impact, production READMEs with system architecture diagrams.",
        "system_prompt": "You are a Principal Software Architect. Write a production-grade, authoritative README in GitHub markdown. Maintain strict technical rigor, clean ASCII/mermaid topology, clear CLI commands, and an Archivo/JetBrains style.",
        "sample_prompt": "Generate a comprehensive README.md for a high-performance local macOS business operating system feeder built in Python (threaded HTTP on 127.0.0.1:8787) feeding a near-black #08090B slab UI."
    },
    {
        "id": "wf-classifier",
        "title": "Financial Transaction Classifier",
        "category": "FINANCE",
        "provider_recommendation": "openai",
        "model": "gpt-4o",
        "description": "Classifies raw bank and card ledger rows into tax-deductible categories, vendor entities, and audit notes.",
        "system_prompt": "You are a CPA and corporate controller. Given raw banking transaction strings, parse and classify each into: Category (SaaS, Travel, Payroll, Equipment, Legal), Deductibility (100%, 50%, 0%), and Flag (Clear / Needs Review). Return clean JSON format.",
        "sample_prompt": "Classify these 4 transactions:\n1. 2026-09-02 GSUITE_GOOGLE*SVCS $36.00\n2. 2026-09-03 DELTA AIR 00674129 $540.20\n3. 2026-09-04 AWS CLOUD SERVICES $1,842.11\n4. 2026-09-05 BLUE BOTTLE COFFEE $14.50"
    },
    {
        "id": "wf-outreach",
        "title": "Executive Outreach Synthesizer",
        "category": "OPERATIONS",
        "provider_recommendation": "claude",
        "model": "claude-3-5-sonnet",
        "description": "Crafts hyper-concise, high-converting B2B outreach emails tailored to Fortune 500 tech leadership.",
        "system_prompt": "You are an expert executive communications director. Write compelling, zero-fluff emails directly to CTOs and VP Operations. Never use marketing clichés, buzzwords, or passive requests. Under 110 words.",
        "sample_prompt": "Write a 90-word outreach email to the VP of Engineering at an enterprise logistics firm introducing our automated local telemetry dashboard that cuts server triage time by 75%."
    },
    {
        "id": "wf-briefing",
        "title": "Executive Daily Briefing",
        "category": "INTELLIGENCE",
        "provider_recommendation": "openai",
        "model": "gpt-4o",
        "description": "Synthesizes multi-source telemetry, market oracles, and news headlines into a 3-point daily executive briefing.",
        "system_prompt": "You are Chief of Staff to the CEO. Parse complex news, market swings, and internal server health metrics into: 1. Critical Pulse (Macro & Markets), 2. Internal Operations Health, 3. Immediate Action Items for Today.",
        "sample_prompt": "Synthesize today's briefing: BTC $92,400 (+4.2%), SPY $575.20 (-0.3%), Server load 0.38 / 100% uptime, 3 pending accounts payable totaling $1,340."
    },
    {
        "id": "wf-sec-audit",
        "title": "Code Security & Secret Scanner",
        "category": "SECURITY",
        "provider_recommendation": "claude",
        "model": "claude-3-5-sonnet",
        "description": "Performs static vulnerability analysis on code snippets, detecting hardcoded secrets, injection vectors, and privilege leaks.",
        "system_prompt": "You are a Senior Application Security Auditor. Inspect the provided source code for: 1. Hardcoded secrets/tokens, 2. Injection flaws (SQL, command, XSS), 3. Reentrancy/concurrency bugs, 4. Remediation diffs.",
        "sample_prompt": "Audit this snippet:\ndef query_user(username):\n    cursor.execute(f\"SELECT * FROM users WHERE user = '{username}'\")\n    return cursor.fetchall()"
    }
]

class AIWorkbenchService(BaseService):
    def __init__(self, config):
        super().__init__("ai_workbench", config)
        self.missing_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
        
        # Telemetry counters
        self.usage = {
            "claude": {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0
            },
            "openai": {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0
            }
        }
        self.history = []
        self.saved_workflows = list(DEFAULT_WORKFLOWS)
        self.canva_assets = [
            {
                "id": "cnv-101",
                "title": "Command Center Executive Deck",
                "dimensions": "1920x1080",
                "type": "Presentation",
                "updated_at": "2026-09-05 14:20",
                "status": "Ready",
                "preview_color": "#0E1015"
            },
            {
                "id": "cnv-102",
                "title": "Product Launch Announcement Slab",
                "dimensions": "1080x1350",
                "type": "Social (IG/X)",
                "updated_at": "2026-09-04 09:12",
                "status": "Draft",
                "preview_color": "#181D26"
            }
        ]

    def _calculate_cost(self, model, prompt_tokens, completion_tokens):
        rate = RATES.get(model) or RATES.get("gpt-4o")
        prompt_cost = (prompt_tokens / 1_000_000.0) * rate["prompt"]
        completion_cost = (completion_tokens / 1_000_000.0) * rate["completion"]
        return round(prompt_cost + completion_cost, 6)

    def poll(self):
        openai_key = self.config.get("integrations", {}).get("openai", {}).get("api_key", "").strip()
        claude_key = self.config.get("integrations", {}).get("anthropic", {}).get("api_key", "").strip()
        canva_key = self.config.get("integrations", {}).get("canva", {}).get("api_key", "").strip()

        missing = []
        if not claude_key:
            missing.append("ANTHROPIC_API_KEY")
        if not openai_key:
            missing.append("OPENAI_API_KEY")

        configured = bool(openai_key or claude_key)

        with self.lock:
            self.configured = configured
            self.status = "active" if configured else "unconfigured"
            self.missing_keys = missing

            total_tokens = self.usage["claude"]["total_tokens"] + self.usage["openai"]["total_tokens"]
            total_cost = round(self.usage["claude"]["cost_usd"] + self.usage["openai"]["cost_usd"], 4)

            self.data = {
                "providers": {
                    "claude": {
                        "configured": bool(claude_key),
                        "model": "claude-3-5-sonnet",
                        "available_models": [
                            "claude-3-5-sonnet",
                            "claude-3-haiku",
                            "claude-3-opus"
                        ],
                        "tokens_today": self.usage["claude"]["total_tokens"] if (claude_key or self.usage["claude"]["total_tokens"] > 0) else None,
                        "prompt_tokens": self.usage["claude"]["prompt_tokens"],
                        "completion_tokens": self.usage["claude"]["completion_tokens"],
                        "cost_today_usd": self.usage["claude"]["cost_usd"] if (claude_key or self.usage["claude"]["cost_usd"] > 0) else None,
                        "requests_count": self.usage["claude"]["requests"],
                        "key_status": "AUTHENTICATED" if claude_key else "UNCONFIGURED"
                    },
                    "openai": {
                        "configured": bool(openai_key),
                        "model": "gpt-4o",
                        "available_models": [
                            "gpt-4o",
                            "gpt-4o-mini",
                            "o1-preview"
                        ],
                        "tokens_today": self.usage["openai"]["total_tokens"] if (openai_key or self.usage["openai"]["total_tokens"] > 0) else None,
                        "prompt_tokens": self.usage["openai"]["prompt_tokens"],
                        "completion_tokens": self.usage["openai"]["completion_tokens"],
                        "cost_today_usd": self.usage["openai"]["cost_usd"] if (openai_key or self.usage["openai"]["cost_usd"] > 0) else None,
                        "requests_count": self.usage["openai"]["requests"],
                        "key_status": "AUTHENTICATED" if openai_key else "UNCONFIGURED"
                    },
                    "canva": {
                        "configured": bool(canva_key),
                        "status": "READY" if canva_key else "UNCONFIGURED",
                        "key_status": "AUTHENTICATED" if canva_key else "UNCONFIGURED",
                        "asset_count": len(self.canva_assets)
                    }
                },
                "total_tokens_today": total_tokens if configured or total_tokens > 0 else None,
                "total_cost_today_usd": total_cost if configured or total_cost > 0 else None,
                "saved_workflows": self.saved_workflows,
                "canva_assets": self.canva_assets,
                "recent_history": self.history[:15],
                "connect_instructions": "Add ANTHROPIC_API_KEY and OPENAI_API_KEY in Settings to enable frontier LLM completions."
            }
            self.last_updated = time.time()

    def _execute_claude(self, key, model, prompt, system_prompt, max_tokens=1024):
        # Full real HTTPS call to Anthropic API
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        if system_prompt:
            body["system"] = system_prompt

        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                latency_ms = int((time.time() - start_time) * 1000)
                
                content_blocks = data.get("content", [])
                text_out = "".join([b.get("text", "") for b in content_blocks if b.get("type") == "text"])
                
                usage = data.get("usage", {})
                p_tokens = usage.get("input_tokens", 0)
                c_tokens = usage.get("output_tokens", 0)
                t_tokens = p_tokens + c_tokens
                cost = self._calculate_cost(model, p_tokens, c_tokens)

                return {
                    "success": True,
                    "provider": "claude",
                    "model": model,
                    "text": text_out,
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "total_tokens": t_tokens,
                    "cost_usd": cost,
                    "latency_ms": latency_ms
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                err_msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                err_msg = err_body
            return {"success": False, "error": f"Anthropic API Error ({e.code}): {err_msg}"}
        except Exception as e:
            return {"success": False, "error": f"Anthropic Connection Error: {str(e)}"}

    def _execute_openai(self, key, model, prompt, system_prompt, max_tokens=1024):
        # Full real HTTPS call to OpenAI API
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens
        }

        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                latency_ms = int((time.time() - start_time) * 1000)
                
                choices = data.get("choices", [])
                text_out = choices[0].get("message", {}).get("content", "") if choices else ""
                
                usage = data.get("usage", {})
                p_tokens = usage.get("prompt_tokens", 0)
                c_tokens = usage.get("completion_tokens", 0)
                t_tokens = usage.get("total_tokens", p_tokens + c_tokens)
                cost = self._calculate_cost(model, p_tokens, c_tokens)

                return {
                    "success": True,
                    "provider": "openai",
                    "model": model,
                    "text": text_out,
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "total_tokens": t_tokens,
                    "cost_usd": cost,
                    "latency_ms": latency_ms
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                err_msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                err_msg = err_body
            return {"success": False, "error": f"OpenAI API Error ({e.code}): {err_msg}"}
        except Exception as e:
            return {"success": False, "error": f"OpenAI Connection Error: {str(e)}"}

    def _execute_mock_sandbox(self, provider, model, prompt, system_prompt):
        """Simulates a fast local test execution if keys are unconfigured or testing in sandbox mode."""
        start_time = time.time()
        time.sleep(0.12)  # realistic micro-delay
        latency_ms = int((time.time() - start_time) * 1000) + 120

        p_tokens = max(len(prompt.split()) * 2, 18)
        
        if "readme" in prompt.lower() or "architect" in str(system_prompt).lower():
            c_text = (
                f"# COMMAND CENTER // {model.upper()}\n\n"
                f"> High-performance macOS Business Operating System\n\n"
                f"```bash\n"
                f"$ python3 server.py --host 127.0.0.1 --port 8787\n"
                f"[OK] Feeder active. Shared state synchronized.\n"
                f"```\n\n"
                f"### System Architecture\n"
                f"- **Core Feeder**: Threaded Python server bound strictly to localhost\n"
                f"- **UI Layer**: Dark gold `#E9B44C` on near-black `#08090B` slab grid\n"
                f"- **Telemetry**: Dual LLM expenditure tracking, real-time oracles, zero-dummy policy."
            )
        elif "classif" in prompt.lower() or "transaction" in prompt.lower():
            c_text = (
                "[\n"
                "  {\"date\": \"2026-09-02\", \"vendor\": \"Google GSuite\", \"category\": \"SaaS / Infrastructure\", \"deductible\": \"100%\", \"flag\": \"CLEARED\"},\n"
                "  {\"date\": \"2026-09-03\", \"vendor\": \"Delta Airlines\", \"category\": \"Executive Travel\", \"deductible\": \"100%\", \"flag\": \"RECEIPT_VERIFIED\"},\n"
                "  {\"date\": \"2026-09-04\", \"vendor\": \"AWS Cloud Services\", \"category\": \"Cloud Computing\", \"deductible\": \"100%\", \"flag\": \"CLEARED\"},\n"
                "  {\"date\": \"2026-09-05\", \"vendor\": \"Blue Bottle Coffee\", \"category\": \"Meals & Entertainment\", \"deductible\": \"50%\", \"flag\": \"AUDIT_FLAG\"}\n"
                "]"
            )
        elif "briefing" in prompt.lower():
            c_text = (
                "## EXECUTIVE PULSE REPORT // COMMAND CENTER\n\n"
                "1. **MACRO & ASSETS**: BTC holding strongly above $92k (+4.2%). Equities flat heading into Fed announcement.\n"
                "2. **SYSTEM HEALTH**: 127.0.0.1 daemon running 100% stable; 0 deadlocks across 9 modular feeder threads.\n"
                "3. **IMMEDIATE DIRECTIVE**: Review pending Stripe settlements and approve Q3 SaaS billing commitments."
            )
        else:
            c_text = (
                f"[{model.upper()} COMPLETION RESULT]\n\n"
                f"Analyzed query: \"{prompt[:140]}...\"\n\n"
                f"System synthesis executed under {model} parameters. Context evaluated with zero hallucination constraints. "
                f"All output tokens adhere strictly to Command Center high-rigor telemetry standards."
            )

        c_tokens = len(c_text.split()) * 2
        t_tokens = p_tokens + c_tokens
        cost = self._calculate_cost(model, p_tokens, c_tokens)

        return {
            "success": True,
            "provider": provider,
            "model": model,
            "text": c_text,
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "total_tokens": t_tokens,
            "cost_usd": cost,
            "latency_ms": latency_ms,
            "sandbox_simulated": True
        }

    def dispatch_action(self, action, payload=None):
        payload = payload or {}

        if action == "run_prompt":
            provider = payload.get("provider", "claude").lower()
            model = payload.get("model", "claude-3-5-sonnet" if provider == "claude" else "gpt-4o")
            prompt = payload.get("prompt", "").strip()
            system_prompt = payload.get("system_prompt", "").strip()
            sandbox = payload.get("sandbox", False)

            if not prompt:
                return {"success": False, "error": "Prompt cannot be empty"}

            claude_key = self.config.get("integrations", {}).get("anthropic", {}).get("api_key", "").strip()
            openai_key = self.config.get("integrations", {}).get("openai", {}).get("api_key", "").strip()

            result = None

            if provider == "claude":
                if claude_key and not sandbox:
                    result = self._execute_claude(claude_key, model, prompt, system_prompt)
                elif sandbox:
                    result = self._execute_mock_sandbox("claude", model, prompt, system_prompt)
                else:
                    return {
                        "success": False,
                        "error": "ANTHROPIC_API_KEY is not configured in config.json. Set your API key in Settings or enable Sandbox Test mode."
                    }

            elif provider == "openai":
                if openai_key and not sandbox:
                    result = self._execute_openai(openai_key, model, prompt, system_prompt)
                elif sandbox:
                    result = self._execute_mock_sandbox("openai", model, prompt, system_prompt)
                else:
                    return {
                        "success": False,
                        "error": "OPENAI_API_KEY is not configured in config.json. Set your API key in Settings or enable Sandbox Test mode."
                    }

            elif provider == "both":
                # Concurrently or sequentially run both
                claude_res = None
                openai_res = None

                if claude_key and not sandbox:
                    claude_res = self._execute_claude(claude_key, "claude-3-5-sonnet", prompt, system_prompt)
                else:
                    claude_res = self._execute_mock_sandbox("claude", "claude-3-5-sonnet", prompt, system_prompt)

                if openai_key and not sandbox:
                    openai_res = self._execute_openai(openai_key, "gpt-4o", prompt, system_prompt)
                else:
                    openai_res = self._execute_mock_sandbox("openai", "gpt-4o", prompt, system_prompt)

                # Update state for both
                with self.lock:
                    for res, p_name in [(claude_res, "claude"), (openai_res, "openai")]:
                        if res and res.get("success"):
                            self.usage[p_name]["requests"] += 1
                            self.usage[p_name]["prompt_tokens"] += res["prompt_tokens"]
                            self.usage[p_name]["completion_tokens"] += res["completion_tokens"]
                            self.usage[p_name]["total_tokens"] += res["total_tokens"]
                            self.usage[p_name]["cost_usd"] += res["cost_usd"]
                            self.history.insert(0, {
                                "id": f"run-{int(time.time()*1000)}-{p_name}",
                                "timestamp": time.time(),
                                "provider": p_name,
                                "model": res["model"],
                                "prompt": prompt[:80] + ("..." if len(prompt) > 80 else ""),
                                "prompt_tokens": res["prompt_tokens"],
                                "completion_tokens": res["completion_tokens"],
                                "cost_usd": res["cost_usd"],
                                "latency_ms": res["latency_ms"],
                                "simulated": res.get("sandbox_simulated", False)
                            })

                self.add_event("ai_dual_dispatched", f"Dual prompt evaluated across Claude 3.5 & GPT-4o")
                self.poll()
                return {
                    "success": True,
                    "dual": True,
                    "claude": claude_res,
                    "openai": openai_res
                }

            else:
                return {"success": False, "error": f"Unsupported provider: {provider}"}

            if result and result.get("success"):
                with self.lock:
                    self.usage[provider]["requests"] += 1
                    self.usage[provider]["prompt_tokens"] += result["prompt_tokens"]
                    self.usage[provider]["completion_tokens"] += result["completion_tokens"]
                    self.usage[provider]["total_tokens"] += result["total_tokens"]
                    self.usage[provider]["cost_usd"] += result["cost_usd"]
                    self.history.insert(0, {
                        "id": f"run-{int(time.time()*1000)}-{provider}",
                        "timestamp": time.time(),
                        "provider": provider,
                        "model": result["model"],
                        "prompt": prompt[:80] + ("..." if len(prompt) > 80 else ""),
                        "prompt_tokens": result["prompt_tokens"],
                        "completion_tokens": result["completion_tokens"],
                        "cost_usd": result["cost_usd"],
                        "latency_ms": result["latency_ms"],
                        "simulated": result.get("sandbox_simulated", False)
                    })
                    if len(self.history) > 30:
                        self.history.pop()

                self.add_event("ai_prompt_executed", f"{provider.upper()} ({model}) executed: {result['total_tokens']} tokens, ${result['cost_usd']:.5f}")
                self.poll()
                return result
            else:
                return result or {"success": False, "error": "Execution failed"}

        elif action == "reset_telemetry":
            with self.lock:
                self.usage = {
                    "claude": {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
                    "openai": {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
                }
                self.history.clear()
            self.poll()
            return {"success": True, "message": "Telemetry counters reset"}

        elif action == "canva_create_asset":
            title = payload.get("title", "Untitled Asset").strip()
            dim = payload.get("dimensions", "1920x1080")
            asset_type = payload.get("type", "Social")

            canva_key = self.config.get("integrations", {}).get("canva", {}).get("api_key", "").strip()

            new_asset = {
                "id": f"cnv-{int(time.time())}",
                "title": title or "Executive Briefing Slide",
                "dimensions": dim,
                "type": asset_type,
                "updated_at": time.strftime("%Y-%m-%d %H:%M"),
                "status": "Ready" if canva_key else "Draft (Local)",
                "preview_color": "#181D26",
                "api_authenticated": bool(canva_key)
            }
            with self.lock:
                self.canva_assets.insert(0, new_asset)
                if len(self.canva_assets) > 20:
                    self.canva_assets.pop()

            self.add_event("canva_asset_created", f"Canva asset draft registered: {new_asset['title']} ({dim})")
            self.poll()
            return {"success": True, "asset": new_asset}

        elif action == "save_workflow":
            wf_id = f"wf-{int(time.time())}"
            new_wf = {
                "id": wf_id,
                "title": payload.get("title", "Custom Workflow"),
                "category": payload.get("category", "CUSTOM"),
                "provider_recommendation": payload.get("provider", "claude"),
                "model": payload.get("model", "claude-3-5-sonnet"),
                "description": payload.get("description", ""),
                "system_prompt": payload.get("system_prompt", ""),
                "sample_prompt": payload.get("sample_prompt", "")
            }
            with self.lock:
                self.saved_workflows.append(new_wf)
            self.poll()
            return {"success": True, "workflow": new_wf}

        return super().dispatch_action(action, payload)
