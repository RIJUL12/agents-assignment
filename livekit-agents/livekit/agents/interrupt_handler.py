import asyncio
import re
from typing import Callable

DEFAULT_IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "uh", "uh-huh", "mm-hmm", "right"
}

DEFAULT_INTERRUPT_WORDS = {
    "stop", "wait", "no", "cancel", "hold on"
}


class IntelligentInterruptHandler:

    def __init__(
        self,
        *,
        is_agent_speaking: Callable[[], bool],
        resume_audio: Callable[[], None],
        stop_audio: Callable[[], None],
        ignore_words=None,
        interrupt_words=None,
        decision_delay_ms: int = 150,
    ):
        self.is_agent_speaking = is_agent_speaking
        self.resume_audio = resume_audio
        self.stop_audio = stop_audio

        self.ignore_words = ignore_words or DEFAULT_IGNORE_WORDS
        self.interrupt_words = interrupt_words or DEFAULT_INTERRUPT_WORDS

        self.decision_delay_ms = decision_delay_ms
        self._pending_task = None

    def normalize(self, text: str) -> str:
        return re.sub(r"[^\w\s]", "", text.lower()).strip()

    def contains_interrupt(self, text: str) -> bool:
        for word in self.interrupt_words:
            if word in text:
                return True
        return False

    def is_only_backchannel(self, text: str) -> bool:
        words = text.split()
        return all(word in self.ignore_words for word in words)

    async def handle_user_transcript(self, text: str):
        normalized = self.normalize(text)
        if not self.is_agent_speaking():
            return "respond"

        if self.contains_interrupt(normalized):
            self.stop_audio()
            return "interrupt"

        if self.is_only_backchannel(normalized):
            self.resume_audio()
            return "ignore"

        self.stop_audio()
        return "interrupt"

    def on_vad_interrupt(self, transcript_future: asyncio.Future):
        if not self.is_agent_speaking():
            return

        async def decision():
            try:
                text = await asyncio.wait_for(
                    transcript_future,
                    timeout=self.decision_delay_ms / 1000,
                )
                await self.handle_user_transcript(text)
            except asyncio.TimeoutError:
                self.stop_audio()

        self._pending_task = asyncio.create_task(decision())
