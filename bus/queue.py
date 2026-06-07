"""Async message queue for decoupled channel-agent communication."""

import asyncio
import logging

from bus.events import InboundMessage, OutboundMessage

logger = logging.getLogger("assistant.bus")


class MessageBus:
    """Simple async message bus that decouples chat channels from the agent."""

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=100)
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=200)

    async def publish_inbound(self, msg: InboundMessage) -> None:
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        if self.outbound.full():
            self.outbound.get_nowait()  # drop oldest
        await self.outbound.put(msg)
