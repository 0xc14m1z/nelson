RESPONDER_SYSTEM_PROMPT = """\
You are a knowledgeable expert participating in a multi-model consensus process.
Answer the following enquiry thoroughly and accurately.
Identify the key points of your response and rate your confidence level.
Be specific and substantive in your answer."""

CRITIC_SYSTEM_PROMPT = """\
You are a critical analyst in a multi-model consensus process.
You will receive the original enquiry, a summary of prior discussion rounds,
and the latest responses from all participating models.

Your task:
1. Evaluate all responses for accuracy, completeness, and reasoning quality.
2. Identify any remaining disagreements between the models.
3. Produce a revised response that incorporates valid points from all models.
4. Set has_disagreements to false ONLY if you believe all models have converged
   on a substantially similar answer."""

SUMMARIZER_SYSTEM_PROMPT = """\
You are a concise summarizer. Given a set of model responses from a consensus round,
produce a brief summary capturing:
- Key agreements between models
- Remaining disagreements
- What shifted from the previous round (if applicable)
Keep the summary under 200 words."""


def build_responder_prompt(enquiry: str) -> str:
    return f"Please answer the following enquiry:\n\n{enquiry}"


def build_critic_prompt(
    enquiry: str, prior_summary: str | None, responses: list[dict[str, str]]
) -> str:
    parts = [f"Original enquiry:\n{enquiry}\n"]
    if prior_summary:
        parts.append(f"Summary of prior rounds:\n{prior_summary}\n")
    parts.append("Latest responses from all models:\n")
    for r in responses:
        parts.append(f"--- {r['model_name']} ---\n{r['response']}\n")
    return "\n".join(parts)


def build_summarizer_prompt(responses: list[dict[str, str]]) -> str:
    parts = ["Summarize the following model responses from this consensus round:\n"]
    for r in responses:
        parts.append(f"--- {r['model_name']} ---\n{r['response']}\n")
    return "\n".join(parts)
