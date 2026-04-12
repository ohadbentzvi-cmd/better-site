"""Claude prompts, versioned as Python modules.

Every prompt that includes lead-supplied content MUST wrap that content in
``<UNTRUSTED_DATA>...</UNTRUSTED_DATA>`` tags and explicitly instruct the
model to treat the wrapped text as data, never as instructions.

See CLAUDE.md "Prompt injection hardening" for the canonical pattern.
"""
