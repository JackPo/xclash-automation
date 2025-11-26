"""
Flows - Action handlers triggered by icon detection.

Each flow handles a specific icon detection event.
Flows are executed in separate threads to avoid blocking the daemon.
"""

from .handshake_flow import handshake_flow
from .treasure_map_flow import treasure_map_flow

__all__ = ['handshake_flow', 'treasure_map_flow']
