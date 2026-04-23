"""
Hermes agent management using the model catalog.

Defines agent profiles (role, provider, model, tools/capabilities, fallback chain,
and region notes) and populates best-model defaults for Hermes-relevant roles.

The agent registry is integrated into LoopState so the optimizer can inspect
and reason about role-to-model assignments.

Role buckets
------------
general, reasoning, coding, research, multi-agent, vision, rerank,
embeddings, translation, image, video, speech/asr, tts, fast-chat

Design principles
-----------------
- Profiles are populated from the provider truth store (model catalog).
- If a provider lacks a capability, the role is skipped rather than inventing models.
- All functions are pure and testable; no I/O or network access.
- The registry is exposed via a module-level singleton so the optimizer can
  call helper functions without threading state through every function.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from hermesoptimizer.sources.model_catalog import MODEL_CATALOG
from hermesoptimizer.sources.provider_truth import ProviderTruthStore


# ---------------------------------------------------------------------------
# Agent profile definition
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AgentProfile:
    """
    An agent profile describes the canonical provider+model assignment for a
    Hermes role.

    Attributes
    ----------
    role :
        The role identifier, e.g. "coding", "reasoning", "vision".
    provider :
        The provider name, e.g. "openai", "anthropic".
    model :
        The primary model name, e.g. "gpt-4o".
    capabilities :
        List of capability tags this profile satisfies, e.g. ["text", "reasoning"].
    fallback_chain :
        Ordered list of (provider, model) tuples to try if the primary fails.
        Empty list means no fallback is defined.
    region_notes :
        Free-form notes about regional availability or constraints.
    is_user_model :
        True if this is the user's explicitly configured model (preserved, not overwritten).
        User models take precedence over harness defaults.
    is_harness_default :
        True if this is the harness's internal default model.
        Harness defaults are used only when no user model is specified.
    """

    role: str
    provider: str
    model: str
    capabilities: list[str] = field(default_factory=list)
    fallback_chain: list[tuple[str, str]] = field(default_factory=list)
    region_notes: str | None = None
    is_user_model: bool = False
    is_harness_default: bool = False

    def primary(self) -> tuple[str, str]:
        """Return (provider, model) for the primary assignment."""
        return (self.provider, self.model)

    def with_fallbacks(self) -> Iterator[tuple[str, str]]:
        """Yield all (provider, model) pairs in priority order (primary first)."""
        yield self.provider, self.model
        yield from self.fallback_chain

    def is_explicitly_configured(self) -> bool:
        """Return True if this profile was explicitly configured by the user."""
        return self.is_user_model


# ---------------------------------------------------------------------------
# Default profiles — populated from real provider/model data.
# Each role maps to the best available model for that capability.
# If a provider does not offer a capability, the role is omitted.
# ---------------------------------------------------------------------------

#: Default Hermes agent profiles. Keys are role identifiers.
#: These are derived from known provider capabilities in the model catalog.
_DEFAULT_PROFILES: dict[str, AgentProfile] = {
    # ----- General / chat -----
    "general": AgentProfile(
        role="general",
        provider="openai",
        model="gpt-4o",
        capabilities=["text", "chat"],
        fallback_chain=[("anthropic", "claude-3-5-sonnet-20241022")],
        region_notes="Global; best for broad conversational tasks",
    ),
    # ----- Reasoning -----
    "reasoning": AgentProfile(
        role="reasoning",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        capabilities=["reasoning", "text"],
        fallback_chain=[("openai", "gpt-4o")],
        region_notes="Global; strongest for extended reasoning chains",
    ),
    # ----- Coding -----
    "coding": AgentProfile(
        role="coding",
        provider="openai",
        model="gpt-4o",
        capabilities=["text", "coding"],
        fallback_chain=[("anthropic", "claude-3-5-sonnet-20241022")],
        region_notes="Global; Codex models also available for specialized code tasks",
    ),
    # ----- Research -----
    "research": AgentProfile(
        role="research",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        capabilities=["reasoning", "text", "research"],
        fallback_chain=[("openai", "gpt-4o")],
        region_notes="Global; best for deep analysis and literature synthesis",
    ),
    # ----- Multi-agent coordination -----
    "multi-agent": AgentProfile(
        role="multi-agent",
        provider="openai",
        model="gpt-4o",
        capabilities=["text", "chat", "multi-agent"],
        fallback_chain=[("anthropic", "claude-3-5-sonnet-20241022")],
        region_notes="Global; gpt-4o supports multi-agent tool use patterns",
    ),
    # ----- Vision -----
    "vision": AgentProfile(
        role="vision",
        provider="openai",
        model="gpt-4o",
        capabilities=["text", "vision", "image-understanding"],
        fallback_chain=[("anthropic", "claude-3-5-sonnet-20241022")],
        region_notes="Global; gpt-4o has native vision support",
    ),
    # ----- Reranking -----
    "rerank": AgentProfile(
        role="rerank",
        provider="openai",
        model="gpt-4o",
        capabilities=["rerank", "text"],
        fallback_chain=[],
        region_notes="Global; Cohere also offers dedicated rerank models — add if provider available",
    ),
    # ----- Embeddings -----
    "embeddings": AgentProfile(
        role="embeddings",
        provider="openai",
        model="text-embedding-3-large",
        capabilities=["embeddings", "vector"],
        fallback_chain=[("cohere", "embed-english-v3")],
        region_notes="Global; OpenAI embeddings are dimension-configurable",
    ),
    # ----- Translation -----
    "translation": AgentProfile(
        role="translation",
        provider="openai",
        model="gpt-4o",
        capabilities=["text", "translation"],
        fallback_chain=[("anthropic", "claude-3-5-sonnet-20241022")],
        region_notes="Global; strong multilingual coverage",
    ),
    # ----- Image generation -----
    "image": AgentProfile(
        role="image",
        provider="openai",
        model="dall-e-3",
        capabilities=["image-generation", "image"],
        fallback_chain=[],
        region_notes="Global; DALL-E 3 for highest quality",
    ),
    # ----- Video -----
    "video": AgentProfile(
        role="video",
        provider="openai",
        model="sora",
        capabilities=["video-generation", "video"],
        fallback_chain=[],
        region_notes="Limited regions; check OpenAI availability",
    ),
    # ----- Speech / ASR -----
    "speech/asr": AgentProfile(
        role="speech/asr",
        provider="openai",
        model="whisper-1",
        capabilities=["speech-to-text", "asr", "audio"],
        fallback_chain=[],
        region_notes="Global; Whisper is the strongest open-weight ASR model",
    ),
    # ----- TTS -----
    "tts": AgentProfile(
        role="tts",
        provider="openai",
        model="tts-1",
        capabilities=["text-to-speech", "tts", "audio"],
        fallback_chain=[("cohere", "cohere-tts")],
        region_notes="Global; tts-1 hd variant available for higher quality",
    ),
    # ----- Fast chat (low-latency) -----
    "fast-chat": AgentProfile(
        role="fast-chat",
        provider="openai",
        model="gpt-4o-mini",
        capabilities=["text", "chat", "fast"],
        fallback_chain=[("anthropic", "claude-3-5-haiku-20241022")],
        region_notes="Global; gpt-4o-mini is optimized for latency and cost",
    ),
}
def _build_default_profiles_from_catalog() -> dict[str, AgentProfile]:
    """Build the default Hermes agent profiles from the model catalog."""
    role_specs: dict[str, tuple[str, str, str]] = {
        "general": ("qwen", "reasoning", "Global general-purpose reasoning and chat"),
        "reasoning": ("xai", "reasoning", "Best available deep reasoning / tool-calling model"),
        "coding": ("qwen", "coding", "Best available coding agent model"),
        "research": ("xai", "multi-agent", "Multi-agent research and synthesis"),
        "multi-agent": ("xai", "multi-agent", "Multi-agent orchestration"),
        "vision": ("qwen", "vision", "Best available multimodal vision model"),
        "rerank": ("qwen", "reranking", "Best available reranker"),
        "embeddings": ("qwen", "embedding", "Best available embedding model"),
        "translation": ("qwen", "translation", "Best available translation model"),
        "image": ("qwen", "image-generation", "Best available image-generation model"),
        "video": ("qwen", "video-generation", "Best available video-generation model"),
        "speech/asr": ("qwen", "speech-to-text", "Best available ASR model"),
        "tts": ("qwen", "text-to-speech", "Best available TTS model"),
        "fast-chat": ("xai", "fast-response", "Best available low-latency chat model"),
    }
    role_capabilities: dict[str, list[str]] = {
        "general": ["text", "reasoning"],
        "reasoning": ["text", "reasoning"],
        "coding": ["text", "reasoning", "coding"],
        "research": ["text", "reasoning", "research"],
        "multi-agent": ["text", "reasoning", "multi-agent"],
        "vision": ["text", "vision", "multimodal"],
        "rerank": ["text", "reranking"],
        "embeddings": ["embedding", "vector"],
        "translation": ["text", "translation"],
        "image": ["image-generation", "image"],
        "video": ["video-generation", "video"],
        "speech/asr": ["speech-to-text", "audio"],
        "tts": ["text-to-speech", "audio"],
        "fast-chat": ["text", "fast-response"],
    }
    fallback_specs: dict[str, tuple[str, str] | None] = {
        "general": ("xai", "reasoning"),
        "reasoning": ("qwen", "reasoning"),
        "coding": ("xai", "reasoning"),
        "research": ("qwen", "reasoning"),
        "multi-agent": ("qwen", "reasoning"),
        "vision": ("minimax", "vision"),
        "rerank": None,
        "embeddings": None,
        "translation": ("openai", "text"),
        "image": ("xai", "image-generation"),
        "video": ("minimax", "video-generation"),
        "speech/asr": ("minimax", "speech-to-text"),
        "tts": ("minimax", "text-to-speech"),
        "fast-chat": ("qwen", "text"),
    }
    profiles: dict[str, AgentProfile] = {}
    for role, (provider, capability_role, notes) in role_specs.items():
        entry = MODEL_CATALOG.best_model(role=capability_role, provider=provider)
        if entry is None:
            entry = MODEL_CATALOG.best_model(role=capability_role)
        if entry is None:
            continue
        fallback_chain: list[tuple[str, str]] = []
        fallback = fallback_specs.get(role)
        if fallback is not None:
            fb_provider, fb_role = fallback
            fb_entry = MODEL_CATALOG.best_model(role=fb_role, provider=fb_provider)
            if fb_entry is None:
                fb_entry = MODEL_CATALOG.best_model(role=fb_role)
            if fb_entry is not None and (fb_entry.provider, fb_entry.name) != (entry.provider, entry.name):
                fallback_chain.append((fb_entry.provider, fb_entry.name))
        profiles[role] = AgentProfile(
            role=role,
            provider=entry.provider,
            model=entry.name,
            capabilities=list(dict.fromkeys(role_capabilities.get(role, list(entry.capabilities)))),
            fallback_chain=fallback_chain,
            region_notes=notes,
        )
    return profiles


class HermesAgentRegistry:
    """
    Manages Hermes agent profiles and resolves role-to-model assignments
    against the provider truth store.

    The registry is a pure, in-memory object — no I/O.  It can be inspected
    by the optimizer to understand which models are assigned to which roles.
    """

    def __init__(
        self,
        profiles: dict[str, AgentProfile] | None = None,
        truth_store: ProviderTruthStore | None = None,
    ) -> None:
        self._profiles: dict[str, AgentProfile] = (
            dict(profiles) if profiles is not None else _build_default_profiles_from_catalog()
        )
        self._truth_store = truth_store or ProviderTruthStore()

    # -- Read-only access -----------------------------------------------------

    def get(self, role: str) -> AgentProfile | None:
        """Return the profile for a role, or None if the role is unknown."""
        return self._profiles.get(role)

    def all_roles(self) -> list[str]:
        """Return sorted list of known role identifiers."""
        return sorted(self._profiles.keys())

    def iter_profiles(self) -> Iterator[AgentProfile]:
        """Yield all profiles in role alphabetical order."""
        for role in self.all_roles():
            yield self._profiles[role]

    def get_agent_model(self, role: str) -> tuple[str, str] | None:
        """
        Return (provider, model) for the given role, or None if unknown.

        This is the primary helper the optimizer uses to resolve a role
        to its assigned model without exposing the full profile object.
        """
        profile = self._profiles.get(role)
        if profile is None:
            return None
        return profile.primary()

    def get_fallback_chain(self, role: str) -> list[tuple[str, str]]:
        """
        Return the ordered fallback chain for a role, or [] if none defined.
        Each entry is (provider, model).
        """
        profile = self._profiles.get(role)
        if profile is None:
            return []
        return list(profile.fallback_chain)

    def roles_for_capability(self, capability: str) -> list[str]:
        """
        Return all roles whose profile claims to support the given capability.
        This lets the optimizer find roles compatible with a given task.
        """
        capability = capability.lower()
        return sorted(
            role
            for role, profile in self._profiles.items()
            if capability in [c.lower() for c in profile.capabilities]
        )

    def best_role_for_task(self, task_capabilities: list[str]) -> str | None:
        """
        Return the role whose profile best matches the requested capabilities.

        A role is a match if it claims ALL of the requested capabilities.
        If multiple roles match, returns the one with the fewest total
        capabilities (most specialized).  Returns None if no match found.
        """
        task_set = {c.lower() for c in task_capabilities}
        if not task_set:
            return None

        candidates: list[tuple[int, str]] = []
        for role, profile in self._profiles.items():
            profile_caps = {c.lower() for c in profile.capabilities}
            if task_set <= profile_caps:
                # All requested capabilities are present in this role
                candidates.append((len(profile_caps), role))

        if not candidates:
            return None
        # Prefer most specialized (fewest total capabilities)
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    # -- Profile mutation (for testing / extension) ----------------------------

    def set_profile(self, profile: AgentProfile) -> None:
        """Add or replace a profile for a role."""
        self._profiles[profile.role] = profile

    def remove_role(self, role: str) -> None:
        """Remove a role from the registry."""
        self._profiles.pop(role, None)

    def filter_by_provider(self, provider: str) -> list[str]:
        """Return sorted list of roles whose primary provider matches."""
        return sorted(
            role
            for role, p in self._profiles.items()
            if p.provider == provider
        )


# ---------------------------------------------------------------------------
# Module-level singleton registry (visible to the optimizer)
# ---------------------------------------------------------------------------

#: The global registry instance. Initialize with init_registry() or by
#: passing a truth_store to register_agents().
_registry: HermesAgentRegistry = HermesAgentRegistry()


def init_registry(
    profiles: dict[str, AgentProfile] | None = None,
    truth_store: ProviderTruthStore | None = None,
) -> HermesAgentRegistry:
    """
    Initialize the global registry with optional custom profiles and truth store.

    If called without arguments, resets to default profiles.
    This function is idempotent and is safe to call in tests.
    """
    global _registry
    _registry = HermesAgentRegistry(profiles=profiles, truth_store=truth_store)
    return _registry


def get_registry() -> HermesAgentRegistry:
    """Return the current global registry instance."""
    return _registry


def get_profile(role: str) -> AgentProfile | None:
    """Convenience: delegate to the global registry."""
    return _registry.get(role)


def get_agent_model(role: str) -> tuple[str, str] | None:
    """Convenience: delegate to the global registry. Returns (provider, model)."""
    return _registry.get_agent_model(role)


def get_fallback_chain(role: str) -> list[tuple[str, str]]:
    """Convenience: delegate to the global registry."""
    return _registry.get_fallback_chain(role)


def all_roles() -> list[str]:
    """Convenience: delegate to the global registry."""
    return _registry.all_roles()


def iter_profiles() -> Iterator[AgentProfile]:
    """Convenience: delegate to the global registry."""
    return _registry.iter_profiles()


def roles_for_capability(capability: str) -> list[str]:
    """Convenience: delegate to the global registry."""
    return _registry.roles_for_capability(capability)


def best_role_for_task(task_capabilities: list[str]) -> str | None:
    """Convenience: delegate to the global registry."""
    return _registry.best_role_for_task(task_capabilities)
