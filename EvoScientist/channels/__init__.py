"""Communication channels for EvoScientist.

This module provides an extensible interface for different messaging channels
(iMessage, Telegram, Discord, Slack, WeChat, DingTalk, Feishu, Email, QQ, Signal) to communicate with the EvoScientist agent.
"""

from .base import Channel, IncomingMessage, OutgoingMessage, RawIncoming, chunk_text
from .bus import InboundMessage, MessageBus, OutboundMessage
from .capabilities import ChannelCapabilities
from .channel_manager import (
    ChannelManager,
    available_channels,
    create_channel,
    register_channel,
)
from .consumer import InboundConsumer
from .formatter import UnifiedFormatter
from .middleware import TypingManager
from .plugin import ChannelMeta, ChannelPlugin, ReloadPolicy
from .standalone import run_standalone

# Backward compat: ChannelServer is now Channel itself
ChannelServer = Channel

__all__ = [
    "Channel",
    "ChannelServer",
    "ChannelManager",
    "MessageBus",
    "RawIncoming",
    "IncomingMessage",
    "OutgoingMessage",
    "InboundMessage",
    "OutboundMessage",
    "InboundConsumer",
    "run_standalone",
    "register_channel",
    "create_channel",
    "available_channels",
    # New modules
    "ChannelCapabilities",
    "UnifiedFormatter",
    "TypingManager",
    "chunk_text",
    # Plugin architecture
    "ChannelPlugin",
    "ChannelMeta",
    "ReloadPolicy",
]
