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

SCORER_SYSTEM_PROMPT = """\
You are evaluating a response to an enquiry.
Rate your confidence in the response and extract its key points."""

DISAGREEMENT_SYSTEM_PROMPT = """\
You are evaluating whether models in a consensus process have converged.
Identify any remaining disagreements between the responses."""

FINAL_SUMMARIZER_SYSTEM_PROMPT = """\
You are producing the final consensus answer.
Given the responses from all models that have reached agreement,
synthesize them into a single, comprehensive, definitive answer."""


def build_responder_prompt(enquiry: str) -> str:
    return f"Please answer the following enquiry:\n\n{enquiry}"


def build_critic_prompt(
    enquiry: str,
    responses: list[dict[str, str]],
    disagreements: list[str] | None = None,
) -> str:
    parts = [f"Original enquiry:\n{enquiry}\n"]
    parts.append("Responses from all models:\n")
    for r in responses:
        parts.append(f"--- {r['model_name']} ---\n{r['response']}\n")
    if disagreements:
        parts.append("Disagreements identified in the previous round:\n")
        for d in disagreements:
            parts.append(f"- {d}\n")
    return "\n".join(parts)


def build_scorer_prompt(enquiry: str, response: str) -> str:
    return (
        f"Original enquiry:\n{enquiry}\n\n"
        f"Response to evaluate:\n{response}"
    )


def build_disagreement_prompt(
    enquiry: str, responses: list[dict[str, str]]
) -> str:
    parts = [f"Original enquiry:\n{enquiry}\n"]
    parts.append("Responses from all models:\n")
    for r in responses:
        parts.append(f"--- {r['model_name']} ---\n{r['response']}\n")
    return "\n".join(parts)


def build_final_summary_prompt(
    enquiry: str, responses: list[dict[str, str]]
) -> str:
    parts = [f"Original enquiry:\n{enquiry}\n"]
    parts.append("Final agreed responses from all models:\n")
    for r in responses:
        parts.append(f"--- {r['model_name']} ---\n{r['response']}\n")
    parts.append(
        "\nSynthesize these into a single definitive answer."
    )
    return "\n".join(parts)
